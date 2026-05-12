/*
 * Источник №6 — Шум плавающего ADC-пина
 * ======================================
 *
 * Самый дешёвый источник: вход A0 НЕ подключён, free-running ADC с опорным
 * 1.1 В (минимальный диапазон → максимальное относительное влияние шума).
 *
 * Источники "хаоса":
 *   - тепловой шум входного S/H-конденсатора;
 *   - наводки 50 Гц / Wi-Fi / USB;
 *   - переключения внутренних шин ATmega328P.
 *
 * Это слабый, но рабочий источник — упоминается во многих обзорных работах
 * как "free-running floating ADC TRNG". Качество низкое; пригодно как
 * демонстрация и как ОДИН из входов гибридного источника №8.
 *
 * Никакого внешнего железа не требуется — удобно для bring-up'а инфраструктуры.
 */

#include "trng_protocol.h"
#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE = 5;        // 32 → 38461 Hz
constexpr uint32_t SAMPLE_RATE_HZ = 38461UL;

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    trng_print_banner("06_floating_adc", 10, SAMPLE_RATE_HZ, "INTERNAL_1V1",
                      "A0 floating, INTERNAL 1.1V ref to maximise relative noise");
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_INTERNAL);
}

void loop() {
    uint16_t s = adc_fast_read();
    trng_send_u16(s);
}
