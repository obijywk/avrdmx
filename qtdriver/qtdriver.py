import logging
import midi
import sacn
import serialdmx
import sys
from PyQt4 import QtCore
from PyQt4 import QtGui

UNIVERSES = 4
CHANNEL_DISPLAY_FORMAT = '\n'.join([' '.join(['{:02X}'] * 32)] * 16)
DEFAULT_MIDI_PORT = 'MolCp3Port 1'

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

        self._palIdle = QtGui.QPalette()
        self._palIdle.setColor(
            QtGui.QPalette.Window, QtGui.QColor(127, 127, 127))
        self._palIdle.setColor(
            QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))

        self._palActive = QtGui.QPalette()
        self._palActive.setColor(
            QtGui.QPalette.Window, QtGui.QColor(63, 191, 63))
        self._palActive.setColor(
            QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))

        self.setWindowTitle('avrdmx Control Panel')

        vbox = QtGui.QVBoxLayout()

        hbox = QtGui.QHBoxLayout()

        hbox.addWidget(QtGui.QLabel('sACN In', self))
        self._sacnLights = [QtGui.QLabel('%d' % i, self)
                            for i in xrange(UNIVERSES)]
        for w in self._sacnLights:
            w.setAlignment(QtCore.Qt.AlignHCenter)
            w.setAutoFillBackground(True)
            w.setPalette(self._palIdle)
            hbox.addWidget(w)
        hbox.addStretch(1)

        hbox.addWidget(QtGui.QLabel('DMX Out', self))
        self._dmxLights = [QtGui.QLabel('%d' % i, self)
                           for i in xrange(UNIVERSES)]
        for w in self._dmxLights:
            w.setAlignment(QtCore.Qt.AlignHCenter)
            w.setAutoFillBackground(True)
            w.setPalette(self._palIdle)
            hbox.addWidget(w)
        self._dmxOutWaiting = QtGui.QLabel('outbuf=0', self)
        hbox.addWidget(self._dmxOutWaiting)
        hbox.addStretch(1)

        self._midiLight = QtGui.QLabel('MIDI Out', self)
        self._midiLight.setAlignment(QtCore.Qt.AlignHCenter)
        self._midiLight.setAutoFillBackground(True)
        self._midiLight.setPalette(self._palIdle)
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

        sacnConfig = QtGui.QGroupBox('sACN', self)
        configVbox = QtGui.QVBoxLayout()

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Network interface', sacnConfig))
        self._sacnIntf = QtGui.QLineEdit(sacn.DefaultIntf(), sacnConfig)
        configHbox.addWidget(self._sacnIntf)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Protocol', sacnConfig))
        self._sacnProtocol = QtGui.QComboBox(sacnConfig)
        self._sacnProtocol.addItem('Auto')
        self._sacnProtocol.addItem('V2')
        self._sacnProtocol.addItem('V3')
        configHbox.addWidget(self._sacnProtocol)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Universe offset', sacnConfig))
        self._sacnUniverseOffset = QtGui.QSpinBox(sacnConfig)
        self._sacnUniverseOffset.setRange(-1, 1)
        configHbox.addWidget(self._sacnUniverseOffset)
        configVbox.addLayout(configHbox)

        sacnConfig.setLayout(configVbox)
        hbox.addWidget(sacnConfig)

        dmxConfig = QtGui.QGroupBox('avrdmx', self)
        configVbox = QtGui.QVBoxLayout()

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Port', dmxConfig))
        self._dmxPort = QtGui.QComboBox(dmxConfig)
        self._dmxPort.setEditable(True)
        self._dmxPort.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
        self._refreshDmxPorts()
        configHbox.addWidget(self._dmxPort)
        self._dmxPortRefresh = QtGui.QPushButton('Refresh', dmxConfig)
        self._dmxPortRefresh.setFocusPolicy(QtCore.Qt.NoFocus)
        self._dmxPortRefresh.clicked.connect(self._refreshDmxPorts)
        configHbox.addWidget(self._dmxPortRefresh)
        configVbox.addLayout(configHbox)

        self._dmxSetDtr = QtGui.QCheckBox('Set DTR', dmxConfig)
        self._dmxSetDtr.setChecked(True)
        configVbox.addWidget(self._dmxSetDtr)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Frame rate', dmxConfig))
        self._dmxFrameRate = QtGui.QSpinBox(dmxConfig)
        self._dmxFrameRate.setRange(1, 44)
        self._dmxFrameRate.setValue(33)
        configHbox.addWidget(self._dmxFrameRate)
        configVbox.addLayout(configHbox)

        self._dmxRetry = QtGui.QCheckBox('Retry on disconnect', dmxConfig)
        self._dmxRetry.setChecked(True)
        configVbox.addWidget(self._dmxRetry)

        dmxConfig.setLayout(configVbox)
        hbox.addWidget(dmxConfig)

        midiConfig = QtGui.QGroupBox('midi', self)
        configVbox = QtGui.QVBoxLayout()

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Port', midiConfig))
        self._midiPort = QtGui.QComboBox(midiConfig)
        self._midiPort.setEditable(True)
        self._midiPort.setInsertPolicy(QtGui.QComboBox.InsertAlphabetically)
        self._refreshMidiPorts()
        configHbox.addWidget(self._midiPort)
        self._midiPortRefresh = QtGui.QPushButton('Refresh', midiConfig)
        self._midiPortRefresh.setFocusPolicy(QtCore.Qt.NoFocus)
        self._midiPortRefresh.clicked.connect(self._refreshMidiPorts)
        configHbox.addWidget(self._midiPortRefresh)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Universe', self))
        self._midiUniverse = QtGui.QSpinBox(midiConfig)
        self._midiUniverse.setRange(1, UNIVERSES)
        configHbox.addWidget(self._midiUniverse)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Reset chan', self))
        self._midiResetChan = QtGui.QSpinBox(midiConfig)
        self._midiResetChan.setRange(1, 512)
        self._midiResetChan.setValue(100)
        configHbox.addWidget(self._midiResetChan)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Cue chan start', self))
        self._midiCueChanStart = QtGui.QSpinBox(midiConfig)
        self._midiCueChanStart.setRange(1, 512)
        self._midiCueChanStart.setValue(101)
        configHbox.addWidget(self._midiCueChanStart)
        configVbox.addLayout(configHbox)

        configHbox = QtGui.QHBoxLayout()
        configHbox.addWidget(QtGui.QLabel('Cue chan end', self))
        self._midiCueChanEnd = QtGui.QSpinBox(midiConfig)
        self._midiCueChanEnd.setRange(1, 512)
        self._midiCueChanEnd.setValue(199)
        configHbox.addWidget(self._midiCueChanEnd)
        configVbox.addLayout(configHbox)

        midiConfig.setLayout(configVbox)
        hbox.addWidget(midiConfig)

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
                l.setPalette(self._palIdle)
            for l in self._dmxLights:
                l.setPalette(self._palIdle)
            if self._dmx:
                self._dmxOutWaiting.setText(
                    'outbuf=%d' % self._dmx.OutWaiting())
            self._midiLight.setPalette(self._palIdle)

    def _toggleSacn(self, enabled):
        if enabled:
            self._sacnIntf.setDisabled(True)
            self._sacnProtocol.setDisabled(True)
            self._sacnUniverseOffset.setDisabled(True)
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
                self._sacnIntf.setDisabled(False)
                self._sacnProtocol.setDisabled(False)
                self._sacnUniverseOffset.setDisabled(False)
            if sacnListener:
                sacnListener.Close()

    def _toggleDisplay(self, enabled):
        with QtCore.QMutexLocker(self._mutex):
            self._display = enabled

    def _toggleDmx(self, enabled):
        if enabled:
            self._dmxPort.setDisabled(True)
            self._dmxPortRefresh.setDisabled(True)
            self._dmxSetDtr.setDisabled(True)
            self._dmxFrameRate.setDisabled(True)
            self._dmxRetry.setDisabled(True)
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
                self._dmxPort.setDisabled(False)
                self._dmxPortRefresh.setDisabled(False)
                self._dmxSetDtr.setDisabled(False)
                self._dmxFrameRate.setDisabled(False)
                self._dmxRetry.setDisabled(False)
            if dmx:
                dmx.Close()

    def _toggleMidi(self, enabled):
        if enabled:
            self._midiPort.setDisabled(True)
            self._midiPortRefresh.setDisabled(True)
            self._midiUniverse.setDisabled(True)
            self._midiResetChan.setDisabled(True)
            self._midiCueChanStart.setDisabled(True)
            self._midiCueChanEnd.setDisabled(True)
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
                self._midiPort.setDisabled(False)
                self._midiPortRefresh.setDisabled(False)
                self._midiUniverse.setDisabled(False)
                self._midiResetChan.setDisabled(False)
                self._midiCueChanStart.setDisabled(False)
                self._midiCueChanEnd.setDisabled(False)

    def _refreshDmxPorts(self):
        self._dmxPort.clear()
        for port in serialdmx.ListPorts():
            self._dmxPort.addItem(port)

    def _refreshMidiPorts(self):
        self._midiPort.clear()
        for port in midi.ListPorts():
            self._midiPort.addItem(port)
            if port == DEFAULT_MIDI_PORT:
                self._midiPort.setCurrentIndex(self._midiPort.count() - 1)

    def _receiveChannels(self, universe, channels):
        with QtCore.QMutexLocker(self._mutex):
            if self._midi:
                self._sendMidi(universe, channels)
            self._universeData[universe] = channels
            self._sacnLights[universe-1].setPalette(self._palActive)
            if self._display:
                text = CHANNEL_DISPLAY_FORMAT.format(
                    *[ord(b) for b in channels])
                self._channelDisplays[universe-1].setText(text)

    def _sendMidi(self, universe, channels):
        midiUniverse = self._midiUniverse.value()
        if universe == midiUniverse and universe in self._universeData:
            resetChan = self._midiResetChan.value() - 1
            if (ord(channels[resetChan]) > 0 and
                ord(self._universeData[universe][resetChan]) == 0):
                self._midi.SendMSCAllOff()
                self._midiLight.setPalette(self._palActive)
            else:
                startChan = self._midiCueChanStart.value() - 1
                endChan = self._midiCueChanEnd.value() - 1
                for chan in xrange(startChan, endChan + 1):
                    if (ord(channels[chan]) > 0 and
                        ord(self._universeData[universe][chan]) == 0):
                        self._midi.SendMSCGo(str(chan - startChan + 1))
                        self._midiLight.setPalette(self._palActive)

    def _onDmxTimer(self):
        try:
            with QtCore.QMutexLocker(self._mutex):
                self._dmx.SendUniverses(self._universeData)
                for universe in self._universeData.iterkeys():
                    self._dmxLights[universe-1].setPalette(self._palActive)
        except Exception, e:
            if self._dmxRetry.isChecked():
                with QtCore.QMutexLocker(self._mutex):
                    if self._dmx:
                        logging.info('DMX disconnected: ' + str(e))
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
