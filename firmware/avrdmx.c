#define F_CPU 16000000UL  // clock frequency = 16MHz
#include <inttypes.h>
#include <stdlib.h>
#include <avr/io.h>
#include <util/delay.h>
#include "usb_serial.h"

extern unsigned char* chandata;
extern void InitDMXOut(void);

#define DEBUG

#ifdef DEBUG
#define DEBUG_OUTPUT_PORT (*((volatile char *)0x20))
void LOG(const char *str) {
  const char *c;
  for (c = str; *c; c++)
    DEBUG_OUTPUT_PORT = *c;
  DEBUG_OUTPUT_PORT = '\n';
}
#else
#define LOG(x)
#endif

int main(void) {
  InitDMXOut();
  usb_init();
  while (!usb_configured());
  while (1) {
    // driver will set DTR when it is connected
    while (!(usb_serial_get_control() & USB_SERIAL_DTR));
    // discard anything that was received prior to DTR being set
    usb_serial_flush_input();

    while (1) {
      unsigned char* position = chandata;
      int16_t universe = usb_serial_getchar();
      if (universe == -1) {
        if (!usb_configured() || !(usb_serial_get_control() & USB_SERIAL_DTR)) {
          // connection lost, forget our position and wait for a connection
          break;
        }
        // just a normal timeout, continue
        continue;
      }
      position += universe;

      while (position < chandata + 2048) {
        int16_t channel_level = usb_serial_getchar();
        if (channel_level != -1) {
          *position = channel_level;
          position += 4;
        } else {
          if (!usb_configured() ||
              !(usb_serial_get_control() & USB_SERIAL_DTR)) {
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
