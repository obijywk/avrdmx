/*
             LUFA Library
     Copyright (C) Dean Camera, 2012.

  dean [at] fourwalledcubicle [dot] com
           www.lufa-lib.org
*/

/*
  Copyright 2012  Dean Camera (dean [at] fourwalledcubicle [dot] com)

  Permission to use, copy, modify, distribute, and sell this
  software and its documentation for any purpose is hereby granted
  without fee, provided that the above copyright notice appear in
  all copies and that both that the copyright notice and this
  permission notice and warranty disclaimer appear in supporting
  documentation, and that the name of the author not be used in
  advertising or publicity pertaining to distribution of the
  software without specific, written prior permission.

  The author disclaim all warranties with regard to this
  software, including all implied warranties of merchantability
  and fitness.  In no event shall the author be liable for any
  special, indirect or consequential damages or any damages
  whatsoever resulting from loss of use, data or profits, whether
  in an action of contract, negligence or other tortious action,
  arising out of or in connection with the use or performance of
  this software.
*/

#include "avrdmx.h"

// LUFA CDC Class driver interface configuration and state information. This
// structure is passed to all CDC Class driver functions, so that multiple
// instances of the same class within a device can be differentiated from one
// another.
USB_ClassInfo_CDC_Device_t VirtualSerial_CDC_Interface = {
  .Config = {
    .ControlInterfaceNumber   = 0,
    .DataINEndpoint           = {
      .Address          = CDC_TX_EPADDR,
      .Size             = CDC_TX_EPSIZE,
      .Banks            = 1,
    },
    .DataOUTEndpoint = {
      .Address          = CDC_RX_EPADDR,
      .Size             = CDC_RX_EPSIZE,
      .Banks            = 2,
    },
    .NotificationEndpoint = {
      .Address          = CDC_NOTIFICATION_EPADDR,
      .Size             = CDC_NOTIFICATION_EPSIZE,
      .Banks            = 1,
    },
  },
};

// True iff connected.
extern bool connected;

// Array of channel data. Universes are interleaved e.g.
//    chandata[0] => universe 1, channel 1
//    chandata[1] => universe 2, channel 1
//    chandata[2] => universe 3, channel 1
//    chandata[3] => universe 4, channel 1
//    chandata[4] => universe 1, channel 2
//    chandata[5] => universe 2, channel 2
//    ...
extern uint8_t _chandata[2048];

extern void InitDMXOut(void);

int main(void) {
  SetupHardware();

  // If digital pin 6 (PD7) is low, fill channel data with a distinctive
  // pattern.
  DDRD &= 0b01111111;
  bool fill_with_pattern = bit_is_clear(PIND, 7);
  if (fill_with_pattern) {
    memset(_chandata, 0b01010101, 2048);
  }

  LEDs_SetAllLEDs(LEDMASK_USB_NOTREADY);
  GlobalInterruptEnable();

  while (true) {
    CDC_Device_USBTask(&VirtualSerial_CDC_Interface);
    USB_USBTask();

    if (connected) {
      uint8_t* position = _chandata;
      int16_t universe = CDC_Device_ReceiveByte(&VirtualSerial_CDC_Interface);
      if (universe == -1) {
        // just a normal timeout, continue
        continue;
      }
      position += universe;

      while (position < _chandata + 2048) {
        int16_t channel_level =
            CDC_Device_ReceiveByte(&VirtualSerial_CDC_Interface);
        if (channel_level != -1) {
          *position = (uint8_t)channel_level;
          position += 4;
        } else {
          if (!connected) {
            // connection lost, forget our position and wait for a connection
            break;
          }
          // just a normal timeout, continue
          continue;
        }
      }
    }
  }
}

void SetupHardware(void) {
  connected = false;

  // Disable watchdog if enabled by bootloader/fuses
  MCUSR &= ~(1 << WDRF);
  wdt_disable();

  // Disable clock division
  clock_prescale_set(clock_div_1);

  // Hardware Initialization
  LEDs_Init();
  USB_Init();
  InitDMXOut();
}

// Event handler for the library USB Connection event.
void EVENT_USB_Device_Connect(void) {
  LEDs_SetAllLEDs(LEDMASK_USB_ENUMERATING);
}

// Event handler for the library USB Disconnection event.
void EVENT_USB_Device_Disconnect(void) {
  connected = false;
  LEDs_SetAllLEDs(LEDMASK_USB_NOTREADY);
}

// Event handler for the library USB Configuration Changed event.
void EVENT_USB_Device_ConfigurationChanged(void) {
  bool ConfigSuccess = true;

  ConfigSuccess &= CDC_Device_ConfigureEndpoints(&VirtualSerial_CDC_Interface);
  connected = ConfigSuccess;

  LEDs_SetAllLEDs(ConfigSuccess ? LEDMASK_USB_READY : LEDMASK_USB_ERROR);
}

// Event handler for the library USB Control Request reception event.
void EVENT_USB_Device_ControlRequest(void) {
  CDC_Device_ProcessControlRequest(&VirtualSerial_CDC_Interface);
}
