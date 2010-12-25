#define F_CPU 16000000  // clock frequency = 16MHz
#include <avr/io.h>

#define DMX_PORT _SFR_IO_ADDR(PORTB)

#define SEND_STATE_MTBP 0
#define SEND_STATE_BREAK 1
#define SEND_STATE_MAB 2

.section bss
.lcomm send_state, 1	
.lcomm chandata, 2048
.text
	
#define LOOPS_TO_DELAY (F_CPU / (1000000 * 4) - 1)
.macro delay us=0 cycles=0
.if \cycles > 0
	ldi r24, (\cycles / 4)
cycle_loop\@:
	nop
	dec r24
	brne cycle_loop\@
.endif
.if \us > 0
	ldi r25, \us
	ldi r24, (LOOPS_TO_DELAY - 1)
	nop
	nop
	nop
us_loop\@:
	nop
	dec r24
	brne us_loop\@
	nop
	ldi r24, LOOPS_TO_DELAY
	dec r25
	brne us_loop\@
.endif
.endm

.global TIMER0_COMPB_vect
TIMER0_COMPB_vect:
	push r25
	lds r25, SREG
	push r25
	lds r25, send_state
	cpi r25, SEND_STATE_BREAK
	breq sendMab
	cpi r25, SEND_STATE_MAB
	breq sendStartCode
sendBreak:
	ldi r25, SEND_STATE_BREAK
	sts send_state, r25
	clr r25
	out DMX_PORT, r25
	ldi r25, 22
	out _SFR_IO_ADDR(OCR0B), r25    ; run the interrupt in 88 microseconds
	clr r25
	out _SFR_IO_ADDR(TCNT0), r25    ; reset timer
	pop r25
	sts SREG, r25
	pop r25
	reti
sendMab:
	ldi r25, SEND_STATE_MAB
	sts send_state, r25
	ser r25
	out DMX_PORT, r25
	ldi r25, 2
	out _SFR_IO_ADDR(OCR0B), r25    ; run the interrupt in 8 microseconds
	clr r25
	out _SFR_IO_ADDR(TCNT0), r25    ; reset timer
	pop r25
	sts SREG, r25
	pop r25
	reti
sendStartCode:
	ldi r25, SEND_STATE_MTBP
	sts send_state, r25
	clr r25
	sts TIMSK0, r25                 ; disable compare match B interrupt
	push XH
	push XL
	push r24
	push r23
	push r22
	push r21
	push r20
	push r19
	push r18
	push r17
	clr r25
	out DMX_PORT, r25
	delay us=35 cycles=8
	nop
	ldi XH, hi8(chandata)
	ldi XL, lo8(chandata)
	ldi r17, 2                      ; channel counter MSB
	ser r18                         ; channel counter LSB
	ldi r19, 8                      ; bit counter
	ser r25
	out DMX_PORT, r25               ; send stop bits
	delay cycles=124
	nop
	nop
sendChannel:
	clr r25
	out DMX_PORT, r25               ; send start bit
	ld r20, X+
	ld r21, X+
	ld r22, X+
	ld r23, X+
	delay cycles=44
	nop
	nop
	nop
sendBit:
	lsr r20
	rol r25
	lsr r21
	rol r25
	lsr r22
	rol r25
	lsr r23
	rol r25
	out DMX_PORT, r25               ; send channel data bit
	delay cycles=52
	dec r19
	brne sendBit
	delay cycles=8
	ser r25
	out DMX_PORT, r25               ; send stop bits
	delay cycles=120
	nop
	nop
	ldi r19, 8
	dec r18
	brne sendChannel
	ser r18
	dec r17
	brne sendChannel
	ldi r25, 255
	out _SFR_IO_ADDR(OCR0B), r25    ; run the interrupt in ~1 millisecond
	clr r25
	out _SFR_IO_ADDR(TCNT0), r25    ; reset timer
	ser r25
	out _SFR_IO_ADDR(TIFR0), r25    ; clear pending timer interrupts
	ldi r25, 1 << OCIE0B
	sts TIMSK0, r25                 ; enable compare match B interrupt
	pop r17
	pop r18
	pop r19
	pop r20
	pop r21
	pop r22
	pop r23
	pop r24
	pop XL
	pop XH
	pop r25
	sts SREG, r25
	pop r25
	reti
	
.global InitDMXOut
InitDMXOut:
	;; initialize packet send state
	ldi r25, SEND_STATE_MTBP
	sts send_state, r25
	;; enable and initialize DMX outputs
	ldi r25, 0b00001111
	out _SFR_IO_ADDR(DDRB), r25
	out DMX_PORT, r25
	;; set up timer
	ldi r25, (1 << CS01) | (1 << CS00)
	out _SFR_IO_ADDR(TCCR0B), r25   ; 64-cycle (4 microsecond) prescaler
	ser r25
	out _SFR_IO_ADDR(TIFR0), r25    ; clear pending interrupts
	ldi r25, 0x01
	out _SFR_IO_ADDR(OCR0B), r25    ; run the interrupt in 4 microseconds
	ldi r25, 1 << OCIE0B
	sts TIMSK0, r25                 ; enable compare match B interrupt
	clr r25
	out _SFR_IO_ADDR(TCNT0), r25    ; reset timer
	sei
	ret

delay_test:
	cpi r17, 1
	delay cycles=4
	cpi r17, 2
	delay cycles=8
	cpi r17, 3
	delay cycles=12
	cpi r17, 4
	delay us=1
	cpi r17, 5
	delay us=1 cycles=4
	cpi r17, 6
	delay us=1 cycles=8
	cpi r17, 7
	delay us=1 cycles=12
	cpi r17, 8
	delay us=2
	cpi r17, 9
	delay us=2 cycles=4
	cpi r17, 10
	delay us=2 cycles=8
	cpi r17, 11
	delay us=2 cycles=12
	cpi r17, 12
	delay us=3
	cpi r17, 13
	delay us=3 cycles=4
