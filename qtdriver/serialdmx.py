import logging
import platform
import serial
try:
  from serial.tools import list_ports
except:
  list_ports = None
import time

def ListPorts():
  system = platform.system()
  if system == 'Windows':
    ports = []
    for i in xrange(8):
      try:
        s = serial.Serial(i)
        s.close()
        ports.append('COM' + str(i + 1))
      except serial.SerialException:
        pass
    return ports
  elif system == 'Linux' and list_ports:
    return sorted([t[0] for t in list_ports.comports()])
  else:
    return []

class SerialDmx(object):
  def __init__(self, port=None, set_dtr=True):
    self._set_dtr = set_dtr
    self._port = serial.Serial(port=port, dsrdtr=set_dtr)
    if set_dtr:
      self._port.setDTR(True)
    logging.info("Opened %s for writing DMX data", port)

  def Close(self):
    if self._set_dtr:
      self._port.setDTR(False)
    self._port.close()
    logging.info("Closed DMX output serial port")

  def SendChannels(self, channels, universe=1):
    universe_byte = bytes(chr(universe - 1))
    logging.debug("universe byte: %s", ord(universe_byte))
    assert len(channels) == 512
    logging.debug("channels: %d %s", len(channels), [ord(c) for c in channels])
    self._port.write(universe_byte + channels)

  def SendUniverses(self, universes):
    buf = bytes()
    for universe, channels in universes.iteritems():
      universe_byte = bytes(chr(universe - 1))
      logging.debug("universe byte: %s", ord(universe_byte))
      buf += universe_byte
      assert len(channels) == 512
      logging.debug("channels: %d %s", len(channels),
                    [ord(c) for c in channels])
      buf += channels
    self._port.write(buf)

  def OutWaiting(self):
    if hasattr(self._port, 'outWaiting'):
      return self._port.outWaiting()
    else:
      return 0

if __name__ == "__main__":
  import os
  from ctypes import *

  serial_dmx = SerialDmx(port="/dev/ptmx", set_dtr=False)
  master_fd = serial_dmx._port.fileno()

  libc = CDLL("libc.so.6")
  libc.unlockpt(master_fd)
  libc.ptsname.restype = c_char_p
  ptsname = libc.ptsname(master_fd)
  slave = os.open(ptsname, os.O_RDONLY)

  serial_dmx.SendChannels(bytearray([2,4,6,8]))
  serial_dmx.SendChannels(bytearray([10,11,12,17]))

  try:
    while True:
      bytes = os.read(slave, 16)
      if len(bytes) > 0:
        for c in bytes:
          print "%x " % ord(c),
        print
  finally:
    os.close(slave)
    serial_dmx.Close()
