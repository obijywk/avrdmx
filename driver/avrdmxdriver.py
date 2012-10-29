import array
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

  # uncomment this to enable sending of test data
  # test_data = array.array('B', [127] * 512).tostring()
  test_data = None

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
    start = time.clock()

    # TODO: better performance from sending universes one at a time, or sending
    # them all at once? use only one of SendUniverses or SendChannels
    serial_dmx.SendUniverses(universe_data)

    for universe, channels in universe_data.iteritems():
      # serial_dmx.SendChannels(channels, universe=universe)
      send_fps[universe] = send_fps.get(universe, 0) + 1

    end = time.clock()

    t = threading.Timer((1.0 / send_frame_rate) - (end - start),
                        SendChannels)
    t.daemon = True
    t.start()

  SendChannels()

  try:
    while True:
      if test_data:
        for i in range(send_frame_rate):
          for u in universes:
            ReceiveChannels(u, test_channels)
          time.sleep(1.0 / send_frame_rate)
      else:
        time.sleep(1)
      logging.info('recv FPS: %s', str(receive_fps))
      logging.info('send FPS: %s', str(send_fps))
      receive_fps.clear()
      send_fps.clear()
  finally:
    sacn_listener.Close()
    serial_dmx.Close()
