/*
 * Источник №1 — Тепловой шум (Johnson-Nyquist)
 * ============================================
 *
 * Схема:
 *   R_n = 1 МОм между +IN_A (LM358) и GND (тепловой шум). Опора каскада — V_mid.
 *   Неинвертирующий усилитель Au = 1 + Rf/Rg, типично 1000 (Rf=1 МОм, Rg=1 кОм).
 *   Каскад 2 на втором ОУ — ещё ~100×, итого ~10⁵ ×.
 *   Выход OUT_B → A0 (см. hardware/01_thermal.md).
 *
 * Подробная схема — см. ../../hardware/01_thermal.md
 *
 * Прошивка просто гонит free-running ADC с opt-выбранной скоростью на A0.
 * Опорное — AVCC=5В, чтобы сохранить полную динамику усилителя.
 */

#include "trng_protocol.h"
#include "adc_fast.h"

// Канал A0; prescaler 16 → 76923 выб/с.
constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE = 4;        // 100b = 16
constexpr uint32_t SAMPLE_RATE_HZ = 16000000UL / 16UL / 13UL;  // = 76923

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) { /* wait for USB */ }
    trng_print_banner("01_thermal", 10, SAMPLE_RATE_HZ, "AVCC",
                      "LM358 x2 (~1e5 gain), 1MOhm thermal source, AC-coupled to A0");
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);
}

void loop() {
    uint16_t s = adc_fast_read();
    trng_send_u16(s);
}
