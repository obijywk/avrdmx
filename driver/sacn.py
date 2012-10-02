# sACN protocol definition based on http://sacnview.cvs.sourceforge.net
#   /viewvc/sacnview/SACNView/src/StreamingACN.pas?view=markup

import array
import logging
import socket
import struct
import sys
import threading
import time

class PacketParseError(Exception):
  """Failed to parse a packet."""

class ArraySliceIterator(object):
  def __init__(self, arr):
    self._arr = arr
    self._i = 0

  def next(self):
    result = self._arr[self._i]
    self._i += 1
    return result

  def take(self, n):
    result = self._arr[self._i:self._i + n]
    self._i += n
    return result

class SACNListener(object):
  PROTOCOL_V2, PROTOCOL_V3 = range(2)
  _PORT = 5568

  def __init__(self, universes=[1], callback=None, protocol=None,
               console_universe_offset=0):
    self._universes = universes
    self._callback = callback
    self._protocol = protocol
    self._console_universe_offset = console_universe_offset
    self._channels = dict([(universe, array.array('B', [0] * 512).tostring())
                           for universe in universes])

    self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
      pass
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
    self._sock.bind(("", self._PORT))
    intf = socket.gethostbyname(socket.gethostname())
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF,
                          socket.inet_aton(intf))
    for universe in universes:
      hi = (universe & 0xFF00) >> 8
      lo = universe & 0xFF
      universe_ip = "239.255.%d.%d" % (hi, lo)
      self._sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                            socket.inet_aton(universe_ip) +
                            socket.inet_aton(intf))
      logging.info("Listening to sACN universe %d on %s:%d",
                   universe, universe_ip, self._PORT)
    self._sock.settimeout(1)

    self._active = True
    self._read_thread = threading.Thread(target=self._Read)
    self._read_thread.start()

  def Close(self):
    self._active = False
    self._sock.close()
    self._read_thread.join()
    logging.info("Stopped listening to sACN universes %s", self._universes)

  def GetChannels(self, universe=1):
    return self._channels[universe]

  def _ParsePacket(self, packet):
    def ExpectEq(expected, actual, field=None):
      if expected != actual:
        raise PacketParseError("Expected %s but got %s for field %s" %
                               (str(expected), str(actual), field))

    it = ArraySliceIterator(packet)

    ExpectEq(0x0010, struct.unpack("!H", it.take(2))[0], "PreambleSize")
    ExpectEq(0x0000, struct.unpack("!H", it.take(2))[0], "PostambleSize")
    ExpectEq("ASC-E1.17\0\0\0", struct.unpack("12s", it.take(12))[0],
             "Identifier")
    rlp_flags = struct.unpack("!H", it.take(2))[0]
    pdu_length = rlp_flags & 0x0FFF
    ExpectEq(0x7, (rlp_flags & 0xF000) >> 12, "RLPFlags")

    vector = struct.unpack("!I", it.take(4))[0]
    if self._protocol:
      protocol = self._protocol
    elif vector == 0x03:
      protocol = self.PROTOCOL_V2
    elif vector == 0x04:
      protocol = self.PROTOCOL_V3
    else:
      raise PacketParseError("Unknown protocol vector %d", vector)

    unused_cid = struct.unpack("!IHHH6s", it.take(16))[0]

    unused_fl_flags = struct.unpack("!H", it.take(2))[0]
    ExpectEq(0x00000002, struct.unpack("!I", it.take(4))[0], "FLVector")
    if protocol == self.PROTOCOL_V2:
      unused_source_name = struct.unpack("32s", it.take(32))[0]
      unused_priority = it.next()
      unused_sequence_number = it.next()
    elif protocol == self.PROTOCOL_V3:
      unused_source_name = struct.unpack("64s", it.take(64))[0]
      unused_priority = it.next()
      unused_reserved = struct.unpack("!H", it.take(2))[0]
      unused_sequence_number = it.next()
      unuesd_options = it.next()
    universe = struct.unpack("!H", it.take(2))[0]
    universe += self._console_universe_offset

    unused_dmp_flags = struct.unpack("!H", it.take(2))[0]
    ExpectEq(0x02, it.next(), "DMPVector")
    ExpectEq(0xA1, it.next(), "DMPAddrType")
    if protocol == self.PROTOCOL_V2:
      start_code = struct.unpack("!H", it.take(2))[0]
      ExpectEq(0x0001, struct.unpack("!H", it.take(2))[0], "AddressIncrement")
      dmx_length = struct.unpack("!H", it.take(2))[0]
    elif protocol == self.PROTOCOL_V3:
      ExpectEq(0x0000, struct.unpack("!H", it.take(2))[0], "DMPFirstPropAddr")
      ExpectEq(0x0001, struct.unpack("!H", it.take(2))[0], "AddressIncrement")
      dmx_length = struct.unpack("!H", it.take(2))[0]
      start_code = it.next()
    if start_code != 0:
      return -1
    self._channels[universe] = (
      it.take(min(512, dmx_length)) +
      array.array('B', [0] * max(512 - dmx_length, 0))).tostring()
    return universe

  def _Read(self):
    packet = array.array('B', [0] * 1024)
    while self._active:
      try:
        bytes_received = self._sock.recv_into(packet, 1024)
        universe = self._ParsePacket(packet)
        logging.debug("sACN listener received %d bytes for universe %d",
                      bytes_received, universe)
        if universe != -1:
          if self._callback:
            self._callback(universe, self._channels[universe])
      except PacketParseError, e:
        logging.error("Packet parse failed: %s", e)
        continue
      except socket.timeout:
        continue
      except socket.error, e:
        logging.error("sACN read aborting: %s", e)
        break

if __name__ == "__main__":
  logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
  def Callback(universe, channels):
    logging.debug("U%d: %s", universe, channels[0:8].encode("string-escape"))
  sacn_listener = SACNListener(universes=[1,2,3,4], callback=Callback)
  try:
    while True:
      time.sleep(1)
  finally:
    sacn_listener.Close()
