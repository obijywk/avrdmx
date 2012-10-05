import logging
import serial
import time

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
