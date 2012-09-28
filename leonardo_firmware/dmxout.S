#define F_CPU 16000000  // clock frequency = 16MHz
#include <avr/io.h>

#define DMX_PORT _SFR_IO_ADDR(PORTB)

#define SEND_STATE_MTBP 0
#define SEND_STATE_BREAK 1
#define SEND_STATE_MAB 2
#define SEND_STATE_CHANNELS 3

.section bss

;;; array containing current DMX channel values
;;; the 4 universes are interleaved
;;; aligned to a 256-byte boundary so that we can check for reaching the end of
;;; the array by only comparing the hi byte
.global chandata
.comm chandata, 2048, 256

;;; determines the portion of the 'slow' timer interrupt that should run next
;;; set to one of the SEND_STATE_* constants
.lcomm send_state, 1

;;; pointer to our current lo byte position within the bits buffer
.lcomm bits_ptr, 1

;;; pointer to our current position within the chandata array
.lcomm chans_h, 1
.lcomm chans_l, 1

;;; buffer to hold interleaved channel value bits that are ready to be sent
;;; aligned to an 8-byte boundary so that we don't have to keep a hi byte ptr
.local bits
.comm bits, 8, 8

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

;;; timer0 COMPA is used for channel value bit send
.global TIMER0_COMPA_vect
TIMER0_COMPA_vect:
        ;; save registers
        push r0                 ; 2
        push r31                ; 2
        ;; avrfreaks design note #046 - fix interrupt timer accuracy
        in r31, _SFR_IO_ADDR(TCNT0)  ; 1
        sbrc r31, 1             ; 1 / 2
        lpm                     ; 3
        sbrs r31, 0             ; 1 / 2
        rjmp _timer0_compa_next ; 2
_timer0_compa_next:
        ;; save more registers
        in r0, _SFR_IO_ADDR(SREG)  ; 1
        push r0                 ; 2
        push r30                ; 2
        ;; load our position within the bits buffer
        ldi ZH, hi8(bits)       ; 1
        lds ZL, bits_ptr        ; 2
        ;; output a bit to each universe
        ld r0, Z+               ; 2
        out DMX_PORT, r0        ; 1
        ;; check if we've sent 8 bits
        cpi ZL, lo8(bits + 8)   ; 1
        breq _timer0_compa_done ; 1 / 2
        ;; store our position within the bits buffer
        sts bits_ptr, ZL        ; 2
        ;; reload the time
        ldi r31, 226            ; 1
        out _SFR_IO_ADDR(TCNT0), r31  ; 1
        ;; restore registers
        pop r30                 ; 2
        pop r0                  ; 2
        out _SFR_IO_ADDR(SREG), r0  ; 1
        pop r31                 ; 2
        pop r0                  ; 2
        reti                    ; 5
_timer0_compa_done:
        ;; switch from COMPA to COMPB interrupt
        ldi r31, 1 << OCIE0B    ; 1
	sts TIMSK0, r31         ; 2
        ;; clear pending timer interrupts
	ser r31                 ; 1
	out _SFR_IO_ADDR(TIFR0), r31  ; 1
        ;; reload the time
        ldi r31, 229            ; 1
        out _SFR_IO_ADDR(TCNT0), r31  ; 1
        ;; restore registers
        pop r30                 ; 2
        pop r0                  ; 2
        out _SFR_IO_ADDR(SREG), r0  ; 1
        pop r31                 ; 2
        pop r0                  ; 2
        reti                    ; 5

;;; timer0 COMPB is used for all other states
.global TIMER0_COMPB_vect
TIMER0_COMPB_vect:
        ;; save registers
        push r0                 ; 2
        push r25                ; 2
        ;; avrfreaks design note #046 - fix interrupt timer accuracy
        in r25, _SFR_IO_ADDR(TCNT0)  ; 1
        sbrc r25, 1             ; 1 / 2
        lpm                     ; 3
        sbrs r25, 0             ; 1 / 2
        rjmp _timer0_compb_next ; 2
_timer0_compb_next:
        ;; save more registers
        in r0, _SFR_IO_ADDR(SREG)  ; 1
        push r0                 ; 2
        ;; TCNT0 should be 21 here (when prescaler is not enabled)
        lds r25, send_state     ; 2
        cpi r25, SEND_STATE_CHANNELS  ; 1
        breq _timer0_compb_send_stop_bits  ; 1 / 2
        jmp _timer0_compb_next_2
_timer0_compb_send_stop_bits:
        ser r25                 ; 1
        out DMX_PORT, r25       ; 1
_timer0_compb_prep_channel:
        ;; load channel pointer
        push ZH                 ; 2
        lds ZH, chans_h         ; 2
        ;; stop if we've sent every channel
        ldi r25, hi8(chandata + 2048)  ; 1
        cpse r25, ZH             ; 1 / 2
        rjmp _timer0_compb_prep_channel_2  ; 2
        jmp _timer0_compb_prep_mtbp  ; 1 / 2
_timer0_compb_prep_channel_2:
        push ZL                 ; 2
        lds ZL, chans_l         ; 2
        ;; load bits buffer pointer
        push YH                 ; 2
        ldi YH, hi8(bits)       ; 1
        push YL                 ; 2
        ldi YL, lo8(bits)       ; 1
        ;; load channel data
        push r24                ; 2
        push r23                ; 2
        push r22                ; 2
        push r21                ; 2
        ld r22, Z+              ; 2
	ld r23, Z+              ; 2
	ld r24, Z+              ; 2
	ld r25, Z+              ; 2
        ;; processing all 8 bits now would take too long - we only do 7, then
        ;; unroll the last iteration which happens after sending the start bit
        ldi r21, 7              ; 1
_timer0_compb_prep_channel_loop:
        ;; copy channel data into bit buffer
        lsr r25                 ; 1
	ror r0                  ; 1
	lsr r24                 ; 1
	ror r0                  ; 1
	lsr r23                 ; 1
	ror r0                  ; 1
	lsr r22                 ; 1
	ror r0                  ; 1
        st Y+, r0               ; 2
        dec r21                 ; 1
        brne _timer0_compb_prep_channel_loop  ; 1 / 2
        ;; send start bit
        nop                     ; 1
        clr r0                  ; 1
        out DMX_PORT, r0        ; 1
        ;; last iteration of the channel data copy
        lsr r25                 ; 1
	ror r0                  ; 1
	lsr r24                 ; 1
	ror r0                  ; 1
	lsr r23                 ; 1
	ror r0                  ; 1
	lsr r22                 ; 1
	ror r0                  ; 1
        st Y+, r0               ; 2
        ;; restore some registers
        pop r21                 ; 2
        pop r22                 ; 2
        pop r23                 ; 2
        pop r24                 ; 2
        pop YL                  ; 2
        pop YH                  ; 2
        ;; store channel pointers
        sts chans_l, ZL         ; 2
        pop ZL                  ; 2
        sts chans_h, ZH         ; 2
        pop ZH                  ; 2
        ;; initialize the bit buffer pointer
        ldi r25, lo8(bits)      ; 1
        sts bits_ptr, r25       ; 2
        ;; setup the timer for sending channel bits
        ;; switch from COMPB to COMPA interrupt
        ldi r25, 1 << OCIE0A    ; 1
	sts TIMSK0, r25         ; 2
        ;; clear the timer and any pending timer interrupts
        clr r25                 ; 1
        out _SFR_IO_ADDR(TCNT0), r25  ; 1
        ser r25                 ; 1
	out _SFR_IO_ADDR(TIFR0), r25  ; 1
        ;; we don't have enough time to let the COMPA interrupt happen
        ;; naturally, so let's just jump right into it
        ;; fix up the stack so it looks like we came from COMPA
        pop r0                  ; 2
        out _SFR_IO_ADDR(SREG), r0  ; 1
        pop r25                 ; 2
        push r31                ; 2
        nop                     ; 1
        nop                     ; 1
        nop                     ; 1
        jmp _timer0_compa_next  ; 3
_timer0_compb_next_2:
        cpi r25, SEND_STATE_MTBP
        breq _timer0_compb_send_break
        cpi r25, SEND_STATE_BREAK
        breq _timer0_compb_send_mab
        cpi r25, SEND_STATE_MAB
        breq _timer0_compb_send_start_code
_timer0_compb_send_break:
        ;; output break
        clr r25
	out DMX_PORT, r25
        ;; set send state
        ldi r25, SEND_STATE_BREAK
        sts send_state, r25
        ;; configure 8-cycle prescaler
	ldi r25, (1 << CS01)
	out _SFR_IO_ADDR(TCCR0B), r25
        ;; run the interrupt in 88 microseconds
	ldi r25, 80
	out _SFR_IO_ADDR(TCNT0), r25
        ;; restore registers
        pop r0
        out _SFR_IO_ADDR(SREG), r0
        pop r25
        pop r0
        reti
_timer0_compb_send_mab:
        ;; output MAB (mark after break)
        ser r25
	out DMX_PORT, r25
        ;; set send state
        ldi r25, SEND_STATE_MAB
        sts send_state, r25
        ;; disable the prescaler
	ldi r25, (1 << CS00)
	out _SFR_IO_ADDR(TCCR0B), r25
        ;; run the interrupt in 5 microseconds
	ldi r25, 176
	out _SFR_IO_ADDR(TCNT0), r25
        ;; restore registers
        pop r0
        out _SFR_IO_ADDR(SREG), r0
        pop r25
        pop r0
        reti
_timer0_compb_send_start_code:
        ;; prepare channel data pointer
        ldi r25, hi8(chandata)
        sts chans_h, r25
        ldi r25, lo8(chandata)
        sts chans_l, r25
        ;; prepare bits buffer pointer
        ldi r25, lo8(bits)
        sts bits_ptr, r25
        ;; clear bits buffer
        push YH
        ldi YH, hi8(bits)
        push YL
        ldi YL, lo8(bits)
        ldi r25, 8
        clr r0
_timer0_compb_clear_bits_loop:
        st Y+, r0
        dec r25
        brne _timer0_compb_clear_bits_loop
        pop YL
        pop YH
        ;; set send state
        ldi r25, SEND_STATE_CHANNELS
        sts send_state, r25
        ;; switch from COMPB to COMPA interrupt
        ldi r25, 1 << OCIE0A
	sts TIMSK0, r25
        ;; clear pending timer interrupts
	ser r25
	out _SFR_IO_ADDR(TIFR0), r25
        ;; run the interrupt when it's time for the first data bit
	ldi r25, 218
	out _SFR_IO_ADDR(TCNT0), r25
        ;; output start code
        clr r25                 ; 1
        out DMX_PORT, r25       ; 1
        ;; restore registers
        pop r0                  ; 2
        out _SFR_IO_ADDR(SREG), r0  ; 1
        pop r25                 ; 2
        pop r0                  ; 2
        reti                    ; 5
_timer0_compb_prep_mtbp:
        pop ZH                  ; 2
        ;; set send state
        ldi r25, SEND_STATE_MTBP
        sts send_state, r25
        ;; configure 1024-cycle prescaler
	ldi r25, (1 << CS02) + (1 << CS00)
	out _SFR_IO_ADDR(TCCR0B), r25
        ;; run the interrupt in ~6 milliseconds
	ldi r25, 162
	out _SFR_IO_ADDR(TCNT0), r25
        ;; clear pending timer interrupts
	ser r25
	out _SFR_IO_ADDR(TIFR0), r25
        ;; enable COMPB interrupt
	ldi r25, 1 << OCIE0B
	sts TIMSK0, r25
        ;; restore registers
        pop r0                  ; 2
        out _SFR_IO_ADDR(SREG), r0  ; 1
        pop r25                 ; 2
        pop r0                  ; 2
        reti                    ; 5

.global InitDMXOut
InitDMXOut:
	;; initialize packet send state
	ldi r25, SEND_STATE_MTBP
	sts send_state, r25
	;; enable and initialize DMX outputs
        in  r25, _SFR_IO_ADDR(DDRB)
	ldi r26, 0b11110000
        or  r25, r26
	out _SFR_IO_ADDR(DDRB), r25
	out DMX_PORT, r25
        ;; disable the prescaler
	ldi r25, (1 << CS00)
	out _SFR_IO_ADDR(TCCR0B), r25
        ;; reset timer
	clr r25
	out _SFR_IO_ADDR(TCNT0), r25
        ;; set COMPA and COMPB times to 0
	clr r25
	out _SFR_IO_ADDR(OCR0A), r25
      	out _SFR_IO_ADDR(OCR0B), r25
        ;; clear pending timer interrupts
	ser r25
	out _SFR_IO_ADDR(TIFR0), r25
        ;; enable COMPB interrupt
	ldi r25, 1 << OCIE0B
	sts TIMSK0, r25
	sei
	ret
