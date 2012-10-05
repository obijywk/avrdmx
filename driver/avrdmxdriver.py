import logging
import sacn
import serialdmx
import sys
import time

if __name__ == "__main__":
  from ctypes import *
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  serial_dmx = serialdmx.SerialDmx(port="/dev/ttyACM0", set_dtr=True)
  master_fd = serial_dmx._port.fileno()
  libc = CDLL("libc.so.6")
  libc.unlockpt(master_fd)

  universe_fps = {}
  def Callback(universe, channels):
    universe_fps[universe] = universe_fps.get(universe, 0) + 1
    serial_dmx.SendChannels(channels, universe=universe)
  sacn_listener = sacn.SACNListener(universes=[1,2,3,4], callback=Callback)

  try:
    while True:
      time.sleep(1)
      logging.info('FPS: %s', str(universe_fps))
      universe_fps.clear()
  finally:
    sacn_listener.Close()
    serial_dmx.Close()
