from pygame import pypm

class MidiSender(object):
    def __init__(self, text):
        pypm.Initialize()
        device_number = None
        for i in range(pypm.CountDevices()):
            interface, name, is_input, is_output, opened = pypm.GetDeviceInfo(i)
            if is_output and (text in interface or text in name):
                device_number = i
                break
        if device_number:
            self._output = pypm.Output(device_number)
        else:
            raise Exception('MIDI output not found')

    def SendMSCGo(self, cue_string):
        self._output.WriteSysEx(
            0,
            '\xF0\x7F\x7F\x02\x7F\x01' + cue_string + '\xF7')

    def SendMSCAllOff(self):
        self._output.WriteSysEx(
            0,
            '\xF0\x7F\x7F\x02\x7F\x08\xF7')

if __name__ == '__main__':
    m = MidiSender('MolCp3Port 1xxx')
    m.SendMSCGo('2')
    #m.SendMSCStop()
    
