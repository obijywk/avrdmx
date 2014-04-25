import logging
import sacn
import serialdmx
import sys
from PyQt4 import QtCore
from PyQt4 import QtGui

UNIVERSES = 4
CHANNEL_DISPLAY_FORMAT = '\n'.join([' '.join(['{:02X}'] * 32)] * 16)

class MainWindow(QtGui.QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()

        self._mutex = QtCore.QMutex()

        self._sacn = None
        self._dmx = None
        self._dmxTimer = None
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

        dmxConfig.setLayout(configVbox)
        hbox.addWidget(dmxConfig)

        hbox.addStretch(1)

        vbox.addLayout(hbox)

        hbox = QtGui.QHBoxLayout()

        self._channelTabs = QtGui.QTabWidget(self)
        self._channelDisplays = [QtGui.QLabel(self) for i in xrange(UNIVERSES)]
        font = QtGui.QFont('monospace', 8)
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
            if dmx:
                dmx.Close()

    def _toggleMidi(self, enabled):
        pass

    def _refreshDmxPorts(self):
        self._dmxPort.clear()
        for port in serialdmx.ListPorts():
            self._dmxPort.addItem(port)

    def _receiveChannels(self, universe, channels):
        with QtCore.QMutexLocker(self._mutex):
            self._universeData[universe] = channels
            self._sacnLights[universe-1].setPalette(self._palActive)
            if self._display:
                text = CHANNEL_DISPLAY_FORMAT.format(
                    *[ord(b) for b in channels])
                self._channelDisplays[universe-1].setText(text)

    def _onDmxTimer(self):
        try:
            with QtCore.QMutexLocker(self._mutex):
                self._dmx.SendUniverses(self._universeData)
                for universe in self._universeData.iterkeys():
                    self._dmxLights[universe-1].setPalette(self._palActive)
        except Exception, e:
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
