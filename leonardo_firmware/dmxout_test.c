#include <avr/interrupt.h>
#include <avr/io.h>
#include <avr/power.h>
#include <string.h>
#include <stdio.h>

extern uint8_t* _chandata;
extern void InitDMXOut(void);

int main(void) {
  // memset(chandata, 0, 2048);

  InitDMXOut();

  while (1) {}

  return 0;
}
