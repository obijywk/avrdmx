#include <avr/interrupt.h>
#include <avr/io.h>
#include <avr/power.h>
#include <string.h>
#include <stdio.h>

extern uint8_t* chandata;
extern void InitDMXOut(void);

int main(void) {
  // memset(chandata, 0, 2048);
  chandata[0] = 1;
  chandata[1] = 2;
  chandata[2] = 4;
  chandata[3] = 8;

  InitDMXOut();

  while (1) {}

  return 0;
}
