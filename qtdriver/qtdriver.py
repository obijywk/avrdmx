import logging
import midi
import sacn
import serialdmx
import sys
from PyQt4 import QtCore
from PyQt4 import QtGui

UNIVERSES = 4
CHANNEL_DISPLAY_FORMAT = '\n'.join([' '.join(['{:02X}'] * 32)] * 16)
IDLE_COLOR = QtGui.QColor(127, 127, 127)
ACTIVE_COLOR = QtGui.QColor(63, 191, 63)
LIGHT_TEXT_COLOR = QtGui.QColor(255, 255, 255)

class BlinkLight(QtGui.QWidget):
  def __init__(self, label, parent):
    super(BlinkLight, self).__init__(parent)
    self._label = label
    self._active = False

  def activate(self):
    if not self._active:
      self._active = True
      self.update()

  def deactivate(self):
    if self._active:
      self._active = False
      self.update()

  def sizeHint(self):
    fontMetrics = self.fontMetrics()
    textHeight = fontMetrics.height()
    textWidth = fontMetrics.width(self._label)
    return QtCore.QSize(textWidth, textHeight)

  def paintEvent(self, event):
    painter = QtGui.QPainter(self)
    painter.setPen(QtCore.Qt.NoPen)
    if self._active:
      painter.setBrush(ACTIVE_COLOR)
    else:
      painter.setBrush(IDLE_COLOR)
    painter.drawRect(self.rect())
    painter.setPen(LIGHT_TEXT_COLOR)
    fontMetrics = self.fontMetrics()
    painter.drawText(
        0,
        self.height() - fontMetrics.descent() - 1,
        self._label)

class MainWindow(QtGui.QWidget):
  def __init__(self):
    super(MainWindow, self).__init__()

    self._mutex = QtCore.QMutex()

    self._sacn = None
    self._dmx = None
    self._dmxTimer = None
    self._midi = None
    self._display = False
    self._universeData = {}

    self.setWindowTitle('avrdmx Control Panel')

    vbox = QtGui.QVBoxLayout()

    hbox = QtGui.QHBoxLayout()

    hbox.addWidget(QtGui.QLabel('sACN In', self))
    self._sacnLights = []
    for i in xrange(UNIVERSES):
      l = BlinkLight('%d' % (i + 1), self)
      hbox.addWidget(l)
      self._sacnLights.append(l)
    hbox.addStretch(1)

    hbox.addWidget(QtGui.QLabel('DMX Out', self))
    self._dmxLights = []
    for i in xrange(UNIVERSES):
      l = BlinkLight('%d' % (i + 1), self)
      hbox.addWidget(l)
      self._dmxLights.append(l)
    self._dmxOutWaiting = QtGui.QLabel('outbuf=0', self)
    hbox.addWidget(self._dmxOutWaiting)
    hbox.addStretch(1)

    self._midiLight = BlinkLight('MIDI Out', self)
    hbox.addWidget(self._midiLight)
    hbox.addStretch(1)

    vbox.addLayout(hbox)

    hbox = QtGui.QHBoxLayout()

    self._sacnButton = QtGui.QToolButton(self)
    self._sacnButton.setFocusPolicy(QtCore.Qt.NoFocus)
    self._sacnButton.setCheckable(True)
    self._sacnButton.setText('sACN Receive')
    self._sacnButton.toggled.connect(self._toggleSacn)
    hbox.addWidget(self._sacnButton)

    self._displayButton = QtGui.QToolButton(self)
    self._displayButton.setFocusPolicy(QtCore.Qt.NoFocus)
    self._displayButton.setCheckable(True)
    self._displayButton.setText('sACN Display')
    self._displayButton.toggled.connect(self._toggleDisplay)
    hbox.addWidget(self._displayButton)

    self._dmxButton = QtGui.QToolButton(self)
    self._dmxButton.setFocusPolicy(QtCore.Qt.NoFocus)
    self._dmxButton.setCheckable(True)
    self._dmxButton.setText('DMX Send')
    self._dmxButton.toggled.connect(self._toggleDmx)
    hbox.addWidget(self._dmxButton)

    self._midiButton = QtGui.QToolButton(self)
    self._midiButton.setFocusPolicy(QtCore.Qt.NoFocus)
    self._midiButton.setCheckable(True)
    self._midiButton.setText('MIDI Send')
    self._midiButton.toggled.connect(self._toggleMidi)
    hbox.addWidget(self._midiButton)

    hbox.addStretch(1)

    vbox.addLayout(hbox)

    hbox = QtGui.QHBoxLayout()

    self._sacnConfig = QtGui.QGroupBox('sACN', self)
    configVbox = QtGui.QVBoxLayout()

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Network interface', self._sacnConfig))
    self._sacnIntf = QtGui.QLineEdit(sacn.DefaultIntf(), self._sacnConfig)
    configHbox.addWidget(self._sacnIntf)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Protocol', self._sacnConfig))
    self._sacnProtocol = QtGui.QComboBox(self._sacnConfig)
    self._sacnProtocol.addItem('Auto')
    self._sacnProtocol.addItem('V2')
    self._sacnProtocol.addItem('V3')
    configHbox.addWidget(self._sacnProtocol)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Universe offset', self._sacnConfig))
    self._sacnUniverseOffset = QtGui.QSpinBox(self._sacnConfig)
    self._sacnUniverseOffset.setRange(-1, 1)
    configHbox.addWidget(self._sacnUniverseOffset)
    configVbox.addLayout(configHbox)

    self._sacnConfig.setLayout(configVbox)
    hbox.addWidget(self._sacnConfig)

    self._dmxConfig = QtGui.QGroupBox('avrdmx', self)
    configVbox = QtGui.QVBoxLayout()

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Port', self._dmxConfig))
    self._dmxPort = QtGui.QComboBox(self._dmxConfig)
    self._dmxPort.setEditable(True)
    self._dmxPort.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
    self._refreshDmxPorts()
    configHbox.addWidget(self._dmxPort)
    self._dmxPortRefresh = QtGui.QPushButton('Refresh', self._dmxConfig)
    self._dmxPortRefresh.setFocusPolicy(QtCore.Qt.NoFocus)
    self._dmxPortRefresh.clicked.connect(self._refreshDmxPorts)
    configHbox.addWidget(self._dmxPortRefresh)
    configVbox.addLayout(configHbox)

    self._dmxSetDtr = QtGui.QCheckBox('Set DTR', self._dmxConfig)
    self._dmxSetDtr.setChecked(True)
    configVbox.addWidget(self._dmxSetDtr)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Frame rate', self._dmxConfig))
    self._dmxFrameRate = QtGui.QSpinBox(self._dmxConfig)
    self._dmxFrameRate.setRange(1, 44)
    self._dmxFrameRate.setValue(33)
    configHbox.addWidget(self._dmxFrameRate)
    configVbox.addLayout(configHbox)

    self._dmxRetry = QtGui.QCheckBox('Retry on disconnect', self._dmxConfig)
    self._dmxRetry.setChecked(True)
    configVbox.addWidget(self._dmxRetry)

    self._dmxConfig.setLayout(configVbox)
    hbox.addWidget(self._dmxConfig)

    self._midiConfig = QtGui.QGroupBox('MIDI', self)
    configVbox = QtGui.QVBoxLayout()

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Port', self._midiConfig))
    self._midiPort = QtGui.QComboBox(self._midiConfig)
    self._midiPort.setEditable(True)
    self._midiPort.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
    self._refreshMidiPorts()
    configHbox.addWidget(self._midiPort)
    self._midiPortRefresh = QtGui.QPushButton('Refresh', self._midiConfig)
    self._midiPortRefresh.setFocusPolicy(QtCore.Qt.NoFocus)
    self._midiPortRefresh.clicked.connect(self._refreshMidiPorts)
    configHbox.addWidget(self._midiPortRefresh)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Universe', self._midiConfig))
    self._midiUniverse = QtGui.QSpinBox(self._midiConfig)
    self._midiUniverse.setRange(1, UNIVERSES)
    configHbox.addWidget(self._midiUniverse)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Reset chan', self._midiConfig))
    self._midiResetChan = QtGui.QSpinBox(self._midiConfig)
    self._midiResetChan.setRange(1, 512)
    self._midiResetChan.setValue(100)
    configHbox.addWidget(self._midiResetChan)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Cue chan start', self._midiConfig))
    self._midiCueChanStart = QtGui.QSpinBox(self._midiConfig)
    self._midiCueChanStart.setRange(1, 512)
    self._midiCueChanStart.setValue(101)
    configHbox.addWidget(self._midiCueChanStart)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Cue chan end', self._midiConfig))
    self._midiCueChanEnd = QtGui.QSpinBox(self._midiConfig)
    self._midiCueChanEnd.setRange(1, 512)
    self._midiCueChanEnd.setValue(199)
    configHbox.addWidget(self._midiCueChanEnd)
    configVbox.addLayout(configHbox)

    self._midiConfig.setLayout(configVbox)
    hbox.addWidget(self._midiConfig)

    self._dimmerCheck = QtGui.QGroupBox('Dimmer Check', self)
    configVbox = QtGui.QVBoxLayout()

    self._dimmerCheckEnable = QtGui.QCheckBox('Enable', self._dimmerCheck)
    self._dimmerCheckEnable.setChecked(False)
    configVbox.addWidget(self._dimmerCheckEnable)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Universe', self._dimmerCheck))
    self._dimmerCheckUniverse = QtGui.QSpinBox(self._dimmerCheck)
    self._dimmerCheckUniverse.setRange(1, UNIVERSES)
    configHbox.addWidget(self._dimmerCheckUniverse)
    configVbox.addLayout(configHbox)

    configHbox = QtGui.QHBoxLayout()
    configHbox.addWidget(QtGui.QLabel('Chan', self._dimmerCheck))
    self._dimmerCheckChan = QtGui.QSpinBox(self._dimmerCheck)
    self._dimmerCheckChan.setRange(1, 512)
    self._dimmerCheckChan.setValue(1)
    configHbox.addWidget(self._dimmerCheckChan)
    configVbox.addLayout(configHbox)

    self._dimmerCheck.setLayout(configVbox)
    hbox.addWidget(self._dimmerCheck)

    hbox.addStretch(1)

    vbox.addLayout(hbox)

    hbox = QtGui.QHBoxLayout()

    self._channelTabs = QtGui.QTabWidget(self)
    self._channelDisplays = [QtGui.QLabel(self) for i in xrange(UNIVERSES)]
    font = QtGui.QFont('monospace', 8)
    font.insertSubstitution('monospace', 'Courier')
    for i, l in enumerate(self._channelDisplays):
      l.setFont(font)
      l.setText(CHANNEL_DISPLAY_FORMAT.format(*([0] * 512)))
      self._channelTabs.addTab(l, 'Universe %d' % (i+1))
    hbox.addWidget(self._channelTabs)
    hbox.addStretch(1)

    vbox.addLayout(hbox)
    vbox.addStretch(1)

    self.setLayout(vbox)
    self.show()

    self._guiTimer = QtCore.QTimer(self)
    self._guiTimer.timeout.connect(self._onGuiTimer)
    self._guiTimer.start(500)

  def closeEvent(self, event):
    if self._sacn:
      self._sacn.Close()
      self._sacn = None
    if self._dmx:
      self._dmx.Close()
      self._dmx = None

  def _onGuiTimer(self):
    with QtCore.QMutexLocker(self._mutex):
      for l in self._sacnLights:
        l.deactivate()
      for l in self._dmxLights:
        l.deactivate()
      if self._dmx:
        self._dmxOutWaiting.setText(
            'outbuf=%d' % self._dmx.OutWaiting())
      self._midiLight.deactivate()

  def _toggleSacn(self, enabled):
    if enabled:
      self._sacnConfig.setDisabled(True)
      protocol = None
      if self._sacnProtocol.currentText == 'V2':
        protocol = sacn.SACNListener.PROTOCOL_V2
      elif self._sacnProtocol.currentText == 'V3':
        protocol = sacn.SACNListener.PROTOCOL_V3
      try:
        sacnListener = sacn.SACNListener(
            universes=range(1, UNIVERSES+1),
            callback=self._receiveChannels,
            protocol=protocol,
            console_universe_offset=self._sacnUniverseOffset.value(),
            intf=str(self._sacnIntf.text()))
        with QtCore.QMutexLocker(self._mutex):
          self._sacn = sacnListener
      except Exception, e:
        msg = QtGui.QMessageBox(self)
        msg.setWindowTitle('Error')
        msg.setText(str(e))
        msg.setIcon(QtGui.QMessageBox.Critical)
        msg.exec_()
        self._sacnButton.setChecked(False)
    else:
      with QtCore.QMutexLocker(self._mutex):
        sacnListener = self._sacn
        self._sacn = None
        self._sacnConfig.setDisabled(False)
      if sacnListener:
        sacnListener.Close()

  def _toggleDisplay(self, enabled):
    with QtCore.QMutexLocker(self._mutex):
      self._display = enabled

  def _toggleDmx(self, enabled):
    if enabled:
      self._dmxConfig.setDisabled(True)
      try:
        dmx = serialdmx.SerialDmx(
            port=str(self._dmxPort.currentText()),
            set_dtr=self._dmxSetDtr.isChecked())
        with QtCore.QMutexLocker(self._mutex):
          self._dmx = dmx
          self._dmxTimer = QtCore.QTimer(self)
          self._dmxTimer.timeout.connect(self._onDmxTimer)
          self._dmxTimer.start(1000 / self._dmxFrameRate.value())
      except Exception, e:
        msg = QtGui.QMessageBox(self)
        msg.setWindowTitle('Error')
        msg.setText(str(e))
        msg.setIcon(QtGui.QMessageBox.Critical)
        msg.exec_()
        self._dmxButton.setChecked(False)
    else:
      with QtCore.QMutexLocker(self._mutex):
        dmx = self._dmx
        self._dmx = None
        if self._dmxTimer:
          self._dmxTimer.stop()
          self._dmxTimer = None
        self._dmxConfig.setDisabled(False)
      if dmx:
        dmx.Close()

  def _toggleMidi(self, enabled):
    if enabled:
      self._midiConfig.setDisabled(True)
      try:
        mymidi = midi.MidiSender(str(self._midiPort.currentText()))
        with QtCore.QMutexLocker(self._mutex):
          self._midi = mymidi
      except Exception, e:
        msg = QtGui.QMessageBox(self)
        msg.setWindowTitle('Error')
        msg.setText(str(e))
        msg.setIcon(QtGui.QMessageBox.Critical)
        msg.exec_()
        self._midiButton.setChecked(False)
    else:
      with QtCore.QMutexLocker(self._mutex):
        self._midi = None
        self._midiConfig.setDisabled(False)

  def _refreshDmxPorts(self):
    self._dmxPort.clear()
    for port in serialdmx.ListPorts():
      self._dmxPort.addItem(port)

  def _refreshMidiPorts(self):
    self._midiPort.clear()
    for port in midi.ListPorts():
      self._midiPort.addItem(port)
      if port == 'MolCp3Port 1':
        self._midiPort.setCurrentIndex(self._midiPort.count() - 1)

  def _receiveChannels(self, universe, channels):
    with QtCore.QMutexLocker(self._mutex):
      if self._midi:
        self._sendMidi(universe, channels)
      self._universeData[universe] = channels

      if (self._dimmerCheckEnable.isChecked() and
        self._dimmerCheckUniverse.value() == universe):
        chan = self._dimmerCheckChan.value() - 1
        self._universeData[universe] = (
          self._universeData[universe][:chan] + chr(255) +
          self._universeData[universe][chan+1:])

      self._sacnLights[universe-1].activate()
      if self._display:
        text = CHANNEL_DISPLAY_FORMAT.format(
          *[ord(b) for b in self._universeData[universe]])
        self._channelDisplays[universe-1].setText(text)

  def _sendMidi(self, universe, channels):
    midiUniverse = self._midiUniverse.value()
    if universe == midiUniverse and universe in self._universeData:
      resetChan = self._midiResetChan.value() - 1
      if (ord(channels[resetChan]) > 0 and
        ord(self._universeData[universe][resetChan]) == 0):
        self._midi.SendMSCAllOff()
        self._midiLight.activate()
      else:
        startChan = self._midiCueChanStart.value() - 1
        endChan = self._midiCueChanEnd.value() - 1
        for chan in xrange(startChan, endChan + 1):
          if (ord(channels[chan]) > 0 and
            ord(self._universeData[universe][chan]) == 0):
            self._midi.SendMSCGo(str(chan - startChan + 1))
            self._midiLight.activate()

  def _onDmxTimer(self):
    try:
      with QtCore.QMutexLocker(self._mutex):
        self._dmx.SendUniverses(self._universeData)
        for universe in self._universeData.iterkeys():
          self._dmxLights[universe-1].activate()
    except Exception, e:
      if self._dmxRetry.isChecked():
        with QtCore.QMutexLocker(self._mutex):
          if self._dmx:
            logging.info('DMX disconnected')
            self._dmx.Close()
            self._dmx = None
            return
        for port in serialdmx.ListPorts():
          if port == str(self._dmxPort.currentText()):
            dmx = serialdmx.SerialDmx(
              port=str(self._dmxPort.currentText()),
              set_dtr=self._dmxSetDtr.isChecked())
            with QtCore.QMutexLocker(self._mutex):
              self._dmx = dmx
      else:
        self._dmxButton.setChecked(False)
        msg = QtGui.QMessageBox(self)
        msg.setWindowTitle('Error')
        msg.setText(str(e))
        msg.setIcon(QtGui.QMessageBox.Critical)
        msg.exec_()

def main():
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)
  app = QtGui.QApplication(sys.argv)
  #app.setStyle(QtGui.QStyleFactory.create('plastique'))
  w = MainWindow()
  sys.exit(app.exec_())

if __name__ == '__main__':
  main()
