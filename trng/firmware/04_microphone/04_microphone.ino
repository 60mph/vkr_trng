/*
 * Источник №4 — Акустический шум (KY-037)
 * ========================================
 *
 * Схема: KY-037 AO → A0 напрямую. Питание VCC=5В от Arduino. Регулятором
 * чувствительности на модуле выставляем середину диапазона (около 2.5 В на
 * выходе AO в тишине). При наличии звука амплитуда колеблется в 0–5 В.
 *
 * Источник энтропии — естественный окружающий акустический фон + дробовой
 * шум электретного микрофона. Соответствует разделу 2.3 дипломной работы.
 *
 * Подробная схема — ../../hardware/04_microphone.md
 */

#include "trng_protocol.h"
#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE = 5;        // 32 → 38461 Hz, точные 10 бит
constexpr uint32_t SAMPLE_RATE_HZ = 38461UL;

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    trng_print_banner("04_microphone", 10, SAMPLE_RATE_HZ, "AVCC",
                      "KY-037 electret mic AO->A0, prescaler=32 (full 10-bit fidelity)");
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);
}

void loop() {
    uint16_t s = adc_fast_read();
    trng_send_u16(s);
}
