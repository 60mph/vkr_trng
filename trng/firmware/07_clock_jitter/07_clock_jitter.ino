/*
 * Источник №7 — Дрожание тактовых сигналов (clock jitter TRNG)
 * =============================================================
 *
 * Идея: сравниваем ДВА независимых тактовых источника ATmega328P —
 *   - быстрый кварц 16 МГц (основной CPU);
 *   - медленный watchdog ~128 кГц (внутренний RC-генератор).
 *
 * RC-генератор имеет существенный относительный шум фазы. Считаем число
 * тиков TIMER1 (от кварца), произошедших за один период WDT (~16 мс).
 * Из получившегося значения берём НЕСКОЛЬКО младших бит — они
 * непредсказуемы, потому что зависят от хаотических флуктуаций RC-цепи.
 *
 * Никакого внешнего железа не требуется. Скорость низкая (~60 бит/с),
 * но это идеальный демонстрационный источник для главы 2.1.
 */

#include "trng_protocol.h"
#include <avr/wdt.h>
#include <avr/interrupt.h>

volatile uint32_t timer1_overflows = 0;

ISR(TIMER1_OVF_vect) {
    timer1_overflows++;
}

// WDT в interrupt-only режиме (без reset).
ISR(WDT_vect) {
    // Захват TCNT1 + переполнения — атомарно (мы уже в ISR).
    uint16_t t  = TCNT1;
    uint32_t ov = timer1_overflows;

    // Re-arm WDT в interrupt-only режиме (по умолчанию после ISR это сбросит CPU).
    WDTCSR |= (1 << WDIE);

    // Берём 16 младших бит "тиков с момента запуска": (ov<<16)|t — но из них
    // нам важны только младшие, так как старшие предсказуемы.
    uint32_t ticks = (ov << 16) | t;
    uint16_t out = (uint16_t)(ticks & 0xFFFF);
    trng_send_u16(out);
}

static void wdt_setup() {
    cli();
    wdt_reset();
    // Разрешаем изменение конфигурации WDT.
    WDTCSR = (1 << WDCE) | (1 << WDE);
    // Период ~16 мс (WDP=000), interrupt-only (без reset).
    WDTCSR = (1 << WDIE);
    sei();
}

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}

    // Запускаем TIMER1 в normal mode без предделителя — 16 МГц/тик.
    cli();
    TCCR1A = 0;
    TCCR1B = (1 << CS10);    // prescaler = 1
    TIMSK1 = (1 << TOIE1);   // overflow interrupt
    TCNT1  = 0;
    timer1_overflows = 0;
    sei();

    trng_print_banner("07_clock_jitter", 16, 60, "INTERNAL_RC_vs_XTAL",
                      "TIMER1 (16MHz xtal) ticks per WDT (128kHz RC) tick — low-rate noise");

    wdt_setup();
}

void loop() {
    // Вся работа — в ISR(WDT_vect).
    sleep_mode_disable();
}
