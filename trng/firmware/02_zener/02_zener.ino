/*
 * Источник №2 — Шум стабилитрона (Зенера / лавинный)
 * ===================================================
 *
 * Схема:
 *   Внешнее питание +9 В (от Arduino Vin или внешний БП) через 100 кОм
 *   подаётся на катод стабилитрона 5,1 В 1 Вт; анод — на GND. Режим — около
 *   точки пробоя, ток ~40 мкА (нестабильный, шумящий).
 *   Через AC-связь 10 мкФ и резистор 1 МОм шум попадает на + вход LM358(A),
 *   далее два каскада усиления (Au_total ~ 1000), смещение 2.5 В, выход на A0.
 *
 * Подробная схема — ../../hardware/02_zener.md
 */

#include "trng_protocol.h"
#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE = 4;
constexpr uint32_t SAMPLE_RATE_HZ = 76923UL;

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    trng_print_banner("02_zener", 10, SAMPLE_RATE_HZ, "AVCC",
                      "5.1V Zener at breakdown, AC-coupled, 2x LM358 ~1000 gain");
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);
}

void loop() {
    uint16_t s = adc_fast_read();
    trng_send_u16(s);
}
