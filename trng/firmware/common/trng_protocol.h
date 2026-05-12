#ifndef TRNG_PROTOCOL_H
#define TRNG_PROTOCOL_H

/*
 * Общий serial-протокол TRNG-проекта (Arduino → ПК)
 * ==================================================
 *
 * Цель: единый формат, который понимает capture/capture_serial.py для всех
 * источников энтропии. Прошивка после reset делает следующее:
 *
 *   1. Шлёт ASCII-баннер с метаданными, заканчивающийся строкой "BEGIN\n":
 *
 *      # TRNG_SOURCE=02_zener
 *      # FIRMWARE_VERSION=1.0
 *      # SAMPLE_FORMAT=u16le
 *      # SAMPLE_BITS=10
 *      # SAMPLE_RATE_HZ=76923
 *      # ADC_REF=AVCC
 *      # NOTES=Free-running ADC, prescaler=16
 *      BEGIN
 *
 *   2. Бесконечно шлёт little-endian uint16_t отсчёты. Поток ничем не
 *      разбивается — capture_serial.py пишет всё в *.bin.
 *
 *   3. Любая непустая ASCII-строка после BEGIN считается ошибкой и
 *      логируется в meta-файл рядом с *.bin.
 *
 * SAMPLE_FORMAT возможные значения:
 *   - u16le        : сырой ADC, 10/12 бит выровнены вправо в uint16
 *   - bits_packed  : 8 бит ГСЧ упакованы в один байт (uint8 поток),
 *                    но мы всё равно отправляем по 2 байта (uint16le, нулевой
 *                    старший байт), чтобы захват был унифицирован.
 *   - mpu6050_lsb  : 16-бит сырой регистр MPU-6050 (ACCEL_* или GYRO_*)
 *
 * Использование в скетче:
 *
 *   #include "trng_protocol.h"
 *   ...
 *   void setup() {
 *     Serial.begin(TRNG_BAUD);
 *     trng_print_banner("02_zener", 10, 76923, "AVCC", "...");
 *   }
 *   void loop() {
 *     uint16_t s = read_sample();
 *     trng_send_u16(s);
 *   }
 */

#include <Arduino.h>

#ifndef TRNG_BAUD
#define TRNG_BAUD 1000000UL  // 1 Мбит/с — родной для FT232/CH340
#endif

// Шлёт ASCII-баннер; вызывать ОДИН раз после Serial.begin().
inline void trng_print_banner(const char* source_id,
                              uint8_t sample_bits,
                              uint32_t sample_rate_hz,
                              const char* adc_ref,
                              const char* notes) {
    Serial.print(F("# TRNG_SOURCE="));        Serial.println(source_id);
    Serial.print(F("# FIRMWARE_VERSION=1.0\n"));
    Serial.print(F("# SAMPLE_FORMAT=u16le\n"));
    Serial.print(F("# SAMPLE_BITS="));        Serial.println(sample_bits);
    Serial.print(F("# SAMPLE_RATE_HZ="));     Serial.println(sample_rate_hz);
    Serial.print(F("# ADC_REF="));            Serial.println(adc_ref);
    Serial.print(F("# NOTES="));              Serial.println(notes);
    Serial.println(F("BEGIN"));
    Serial.flush();
}

// Отправка одного отсчёта в little-endian.
inline void trng_send_u16(uint16_t v) {
    Serial.write((uint8_t)(v & 0xFF));
    Serial.write((uint8_t)(v >> 8));
}

// Удобный help для тех, у кого нет свободного места — проверяем переполнение TX.
// Если writeAvailable == 0, поток отбрасывается (так лучше, чем стопорить АЦП).
inline bool trng_send_u16_nonblock(uint16_t v) {
    if (Serial.availableForWrite() < 2) return false;
    trng_send_u16(v);
    return true;
}

#endif // TRNG_PROTOCOL_H
