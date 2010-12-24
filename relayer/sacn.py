# Based on http://sacnview.cvs.sourceforge.net/viewvc/sacnview/SACNView/src/StreamingACN.pas?view=markup

import array
import logging
import socket
import struct
import sys
import threading

class SACNListener(object):
  def __init__(self, universe=1):
    self._universe = universe
    self._channels = array.array('B', [0] * 512)

    self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
      pass
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
    self._sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
    self._sock.bind(("", 5568))
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
    logging.debug("Listening to sACN universe %d on %s:5568",
                  self._universe, self._universe_ip)

    self._active = True
    self._read_thread = threading.Thread(target=self._Read)
    self._read_thread.start()

  def Stop(self):
    self._active = False
    self._sock.close()
    logging.debug("Stopped listening to sACN universe %d", self._universe)

  def GetChannels(self):
    return self._channels

  def _Read(self):
    packet = array.array('B', [0] * 4096)
    while self._active:
      try:
        bytes_received = self._sock.recv_into(packet, 4096)
        logging.debug("Received %d bytes for sACN universe %d",
                      bytes_received, self._universe)

        # TODO: also handle v3 packet format?
        preamble_size = struct.unpack("!H", packet[0:2])[0]
        assert preamble_size == 0x0010
        postamble_size = struct.unpack("!H", packet[2:4])[0]
        assert postamble_size == 0x0000
        identifier = struct.unpack("12s", packet[4:16])[0]
        assert identifier == "ASC-E1.17\0\0\0"
        rlp_flags = struct.unpack("!H", packet[16:18])[0]
        pdu_length = rlp_flags & 0x0FFF
        assert (rlp_flags & 0xF000) >> 12 == 0x7
        vector = struct.unpack("!I", packet[18:22])[0]
        assert vector == 0x00000003
        cid = struct.unpack("!IHHH6s", packet[22:38])
        fl_flags = struct.unpack("!H", packet[38:40])[0]
        fl_vector = struct.unpack("!I", packet[40:44])[0]
        assert fl_vector == 0x00000002
        source_name = struct.unpack("32s", packet[44:76])[0]
        priority = packet[76]
        sequence_number = packet[77]
        universe = struct.unpack("!H", packet[78:80])[0]
        assert universe == self._universe - 1
        dmp_flags = struct.unpack("!H", packet[80:82])[0]
        dmp_vector = packet[82]
        assert dmp_vector == 0x02
        dmp_addr_type = packet[83]
        assert dmp_addr_type == 0xA1
        start_code = struct.unpack("!H", packet[84:86])[0]
        assert start_code == 0x0000
        address_increment = struct.unpack("!H", packet[86:88])[0]
        assert address_increment == 0x0001
        dmx_length = struct.unpack("!H", packet[88:90])[0]
        self._channels = packet[90:90+dmx_length]
        logging.debug(self._channels[0:8])

      except socket.timeout:
        continue
      except socket.error, e:
        logging.debug("sACN read aborting: %s", e)
        break

if __name__ == "__main__":
  logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
  sacn_listener = SACNListener()
  try:
    while True:
      pass
  finally:
    sacn_listener.Stop()
