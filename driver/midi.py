import logging
import pypm
import threading
import time

logging.basicConfig(level=logging.INFO)

class MidiReceiver(object):
  def __init__(self, name=None, callback=None):
    self._callback = callback
    self._stopped = threading.Event()
    self._read_thread = threading.Thread(target=self.ReadThread)
    self._input = None

    pypm.Initialize()

    device_to_open = None
    for i in xrange(pypm.CountDevices()):
      interface, port, has_in, has_out, is_open = pypm.GetDeviceInfo(i)
      if has_in:
        if not name or name in interface or name in port:
          device_to_open = i
          break
    if device_to_open is None:
      raise LookupError('No appropriate MIDI device found')
    logging.info('Opening MIDI device %s %s for input' % (interface, port))

    self._input = pypm.Input(device_to_open)
    self._read_thread.start()

  def Stop(self):
    logging.info('Closing MIDI device')
    self._stopped.set()
    self._read_thread.join()
    if self._input:
      del self._input

  def ReadThread(self):
    while True:
      while not self._stopped.is_set() and not self._input.Poll():
        time.sleep(0.001)
      if self._stopped.is_set():
        return
      data = self._input.Read(1)[0]
      msg = data[0]
      timestamp = data[1]
      if self._callback:
        self._callback(msg)

if __name__ == '__main__':
  def Callback(data):
    print data
  try:
    midi = MidiReceiver(name='VirMIDI', callback=Callback)
    while True:
      time.sleep(1)
  finally:
    midi.Stop()
