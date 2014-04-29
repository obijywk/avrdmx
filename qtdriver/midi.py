import logging
try:
  from pygame import pypm
  pypm.Initialize()
except Exception, e:
  logging.info('Failed to initialize midi: ' + str(e))
  pypm = None

def ListPorts():
  if not pypm:
    return []
  outputs = []
  for i in range(pypm.CountDevices()):
    interface, name, is_input, is_output, opened = pypm.GetDeviceInfo(i)
    if is_output:
      outputs.append(name)
  return outputs

class MidiSender(object):
  def __init__(self, text):
    if not pypm:
      raise Exception('Failed to initialize midi: pypm module not available')
    device_number = None
    for i in range(pypm.CountDevices()):
      interface, name, is_input, is_output, opened = pypm.GetDeviceInfo(i)
      if is_output and (text in interface or text in name):
        device_number = i
        break
    if device_number:
      self._output = pypm.Output(device_number)
      logging.info('Opened midi output ' + name)
    else:
      raise Exception('MIDI output not found')

  def SendMSCGo(self, cue_string):
    logging.info('Send MSC go ' + cue_string)
    self._output.WriteSysEx(
        0,
        '\xF0\x7F\x7F\x02\x7F\x01' + cue_string + '\xF7')

  def SendMSCAllOff(self):
    logging.info('Send MSC all off')
    self._output.WriteSysEx(
        0,
        '\xF0\x7F\x7F\x02\x7F\x08\xF7')

if __name__ == '__main__':
  m = MidiSender('01. Ethernet MIDI')
  m.SendMSCGo('2')
  #m.SendMSCStop()
