import logging
import platform
import sacn
import serialdmx
import sys
import threading
import time

if __name__ == '__main__':
  from ctypes import *
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  universes = [1,2,3,4]
  send_frame_rate = 33

  system = platform.system()
  if system == 'Windows':
    serial_dmx = serialdmx.SerialDmx(port='COM3', set_dtr=True)
  elif system == 'Linux':
    serial_dmx = serialdmx.SerialDmx(port='/dev/ttyACM0', set_dtr=True)
    master_fd = serial_dmx._port.fileno()
    libc = CDLL("libc.so.6")
    libc.unlockpt(master_fd)

  universe_data = {}
  receive_fps = {}
  send_fps = {}

  def ReceiveChannels(universe, channels):
    receive_fps[universe] = receive_fps.get(universe, 0) + 1
    universe_data[universe] = channels

  sacn_listener = sacn.SACNListener(universes=universes,
                                    callback=ReceiveChannels)

  def SendChannels():
    t = threading.Timer(1.0 / send_frame_rate, SendChannels)
    t.daemon = True
    t.start()

    for universe, channels in universe_data.iteritems():
      serial_dmx.SendChannels(channels, universe=universe)
      send_fps[universe] = send_fps.get(universe, 0) + 1

  SendChannels()

  try:
    while True:
      time.sleep(1)
      logging.info('recv FPS: %s', str(receive_fps))
      logging.info('send FPS: %s', str(send_fps))
      receive_fps.clear()
      send_fps.clear()
  finally:
    sacn_listener.Close()
    serial_dmx.Close()
