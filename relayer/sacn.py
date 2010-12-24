# Based on http://sacnview.cvs.sourceforge.net/viewvc/sacnview/SACNView/src/StreamingACN.pas?view=markup

import array
import logging
import socket
import struct
import sys
import threading

class PacketParseError(Exception):
  """Failed to parse a packet."""

class ArraySliceIterator(object):
  def __init__(self, arr):
    self._arr = arr
    self._i = 0

  def next(self):
    value = self._arr[self._i]
    self._i += 1
    return value

  def take(self, n):
    view = self._arr[self._i:self._i + n]
    self._i += n
    return view

class SACNListener(object):
  PROTOCOL_V2, PROTOCOL_V3 = range(2)
  _PORT = 5568

  def __init__(self, universe=1, callback=None, protocol=PROTOCOL_V2):
    self._universe = universe
    self._callback = callback
    self._protocol = protocol
    self._channels = array.array('B', [0] * 512)

    self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
      pass
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
    self._sock.bind(("", self._PORT))
    hi = (universe & 0xFF00) >> 8
    lo = universe & 0xFF
    self._universe_ip = "239.255.%d.%d" % (hi, lo)
    intf = socket.gethostbyname(socket.gethostname())
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF,
                          socket.inet_aton(intf))
    self._sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                          socket.inet_aton(self._universe_ip) +
                          socket.inet_aton(intf))
    self._sock.settimeout(1)
    logging.debug("Listening to sACN universe %d on %s:%d",
                  self._universe, self._universe_ip, self._PORT)

    self._active = True
    self._read_thread = threading.Thread(target=self._Read)
    self._read_thread.start()

  def Stop(self):
    self._active = False
    self._sock.close()
    logging.debug("Stopped listening to sACN universe %d", self._universe)

  def GetChannels(self):
    return self._channels

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
    ExpectEq(0x00000003, struct.unpack("!I", it.take(4))[0], "Vector")
    unused_cid = struct.unpack("!IHHH6s", it.take(16))[0]

    unused_fl_flags = struct.unpack("!H", it.take(2))[0]
    ExpectEq(0x00000002, struct.unpack("!I", it.take(4))[0], "FLVector")
    if self._protocol == self.PROTOCOL_V2:
      unused_source_name = struct.unpack("32s", it.take(32))[0]
      unused_priority = it.next()
      unused_sequence_number = it.next()
    elif self._protocol == self.PROTOCOL_V3:
      unused_source_name = struct.unpack("64s", it.take(64))[0]
      unused_priority = it.next()
      unused_reserved = struct.unpack("!H", it.take(2))[0]
      unused_sequence_number = it.next()
      unuesd_options = it.next()
    ExpectEq(self._universe - 1, struct.unpack("!H", it.take(2))[0], "Universe")

    unused_dmp_flags = struct.unpack("!H", it.take(2))[0]
    ExpectEq(0x02, it.next(), "DMPVector")
    ExpectEq(0xA1, it.next(), "DMPAddrType")
    if self._protocol == self.PROTOCOL_V2:
      ExpectEq(0x0000, struct.unpack("!H", it.take(2))[0], "StartCode")
      ExpectEq(0x0001, struct.unpack("!H", it.take(2))[0], "AddressIncrement")
      dmx_length = struct.unpack("!H", it.take(2))[0]
    elif self._protocol == self.PROTOCOL_V3:
      ExpectEq(0x0000, struct.unpack("!H", it.take(2))[0], "DMPFirstPropAddr")
      ExpectEq(0x0001, struct.unpack("!H", it.take(2))[0], "AddressIncrement")
      dmx_length = struct.unpack("!H", it.take(2))[0]
      ExpectEq(0x00, it.next(), "StartCode")
    self._channels = it.take(dmx_length)

  def _Read(self):
    packet = array.array('B', [0] * 1024)
    while self._active:
      try:
        bytes_received = self._sock.recv_into(packet, 1024)
        logging.debug("Received %d bytes for sACN universe %d",
                      bytes_received, self._universe)
        self._ParsePacket(packet)
        if self._callback:
          self._callback(self._channels)
      except PacketParseError, e:
        logging.debug("Packet parse failed: %s", e)
        continue
      except socket.timeout:
        continue
      except socket.error, e:
        logging.debug("sACN read aborting: %s", e)
        break

if __name__ == "__main__":
  logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
  def Callback(channels):
    logging.debug(channels[0:8])
  sacn_listener = SACNListener(universe=1, callback=Callback)
  try:
    while True:
      pass
  finally:
    sacn_listener.Stop()
