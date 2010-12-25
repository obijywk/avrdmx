#define F_CPU 16000000UL  // clock frequency = 16MHz
#include <inttypes.h>
#include <stdlib.h>
#include <avr/io.h>
#include <util/delay.h>

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
  while (1) {
  }
}
