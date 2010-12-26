import logging
import sacn
import serialdmx
import sys
import time

if __name__ == "__main__":
  from ctypes import *
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  serial_dmx = serialdmx.SerialDmx(port="/dev/ptmx", set_dtr=False)
  master_fd = serial_dmx._port.fileno()
  libc = CDLL("libc.so.6")
  libc.unlockpt(master_fd)

  def Callback(universe, channels):
    serial_dmx.SendChannels(channels, universe=universe)
  sacn_listener = sacn.SACNListener(universes=range(1,5), callback=Callback)

  try:
    while True:
      time.sleep(1)
  finally:
    sacn_listener.Close()
    serial_dmx.Close()
