import array
import copy
import socket
import struct


class SerializeError(Exception):
  """Failed to serialize data."""


class PDU(object):
  _FLAG_VECTOR = 4
  _FLAG_HEADER = 2
  _FLAG_DATA = 1

  def __init__(self):
    self._vector = None
    self._vector_type = None  # 'B': byte  'H': short  'I': int
    self._header = None
    self._data = None

  def SetVector(self, vector, vector_type='B'):
    self._vector = vector
    self._vector_type = vector_type

  def SetHeader(self, header):
    self._header = header

  def SetData(self, data):
    self._data = data

  def Serialize(self, last_pdu=None):
    p = array.array('B')
    flags = 0

    # placeholder for flags, LengthH and LengthL (LengthX not supported)
    p.fromstring(struct.pack('!xx'))

    if last_pdu:
      if self._vector_type != last_pdu._vector_type:
        raise SerializeError('Different vector lengths in same PDU block')
    if last_pdu and self._vector == last_pdu._vector:
      # don't emit vector
      pass
    else:
      flags |= PDU._FLAG_VECTOR
      p.fromstring(struct.pack('!' + self._vector_type, self._vector))

    if self._header:
      if last_pdu and self._header == last_pdu._header:
        # don't emit header
        pass
      else:
        flags |= PDU._FLAG_HEADER
        p.fromstring(self._header)

    if self._data:
      if last_pdu and self._data == last_pdu._data:
        # don't emit data
        pass
      else:
        flags |= PDU._FLAG_DATA
        p.fromstring(self._data)

    if len(p) >= 4096:
      raise SerializeError('PDU too large: %d bytes' % len(p))
    p[0] = (flags << 4) | (len(p) >> 8)
    p[1] = len(p) & 0xFF

    return p


class RootLayerPacket(object):
  _PREAMBLE = struct.pack('!HH12s', 16, 0, 'ASC-E1.17')

  def __init__(self):
    self._pdu_block = []

  def AddPDU(self, pdu):
    self._pdu_block.append(pdu)

  def Serialize(self):
    p = array.array('B')
    p.fromstring(RootLayerPacket._PREAMBLE)
    last_pdu = None
    for pdu in self._pdu_block:
      p.extend(pdu.Serialize(last_pdu=last_pdu))
      last_pdu = pdu
    return p


class UDPSender(object):
  def __init__(self, addr='239.192.1.100', port=5569):
    self._addr = addr
    self._port = port
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)

  def Send(self, data):
    self._socket.sendto(data, (self._addr, self._port))


if __name__ == '__main__':
  pdu = PDU()
  pdu.SetVector(0x01, 'I')
  pdu.SetHeader(array.array('B', [65, 66]))
  pdu.SetData(array.array('B', [67, 68]))
  print pdu.Serialize()

  pdu2 = copy.deepcopy(pdu)
  pdu2.SetData(array.array('B', [75, 76, 77, 78]))
  print pdu2.Serialize(last_pdu=pdu)

  root_layer_packet = RootLayerPacket()
  root_layer_packet.AddPDU(pdu)
  print root_layer_packet.Serialize()
