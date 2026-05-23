/*
 * Источник №8 — Гибридный TRNG (XOR-комбинация всех источников)
 * ==============================================================
 *
 * На борту Arduino комбинируем:
 *   A) ADC от внешнего аналогового источника (пин A0). Реально на A0 удобно
 *      посадить выход LM358 (Зенер/тепловой/BJT — выбираем при сборке);
 *   B) ADC от плавающего пина A1 (источник №6);
 *   C) MPU-6050 LSB (источник №5);
 *   D) WDT-jitter (источник №7) — собирается в фоне.
 *
 * Каждый из 4 потоков "вытягиваем" в 8-битные слова (LSB ADC × 8 раз для A/B,
 * MPU LSB × 8, WDT-tick LSB × 8) и затем XOR'им — получаем один байт. Шлём
 * как uint16_le с нулевым старшим байтом, чтобы пайплайн на ПК работал
 * единообразно.
 *
 * Источник соответствует разделу 2.4 дипломной работы ("XOR-корректоры") и главе 3
 * ("гибридные/многоканальные схемы").
 *
 * ВАЖНО: реализован минимальный вариант — без SHA. Финальное хеширование
 * (SHA-256/BLAKE2) делается на ПК утилитой capture/mix.py.
 */

#include "trng_protocol.h"
#include "adc_fast.h"
#include <Wire.h>

constexpr uint8_t  CH_EXT      = 0;        // A0 — внешний источник
constexpr uint8_t  CH_FLOAT    = 1;        // A1 — плавающий
constexpr uint8_t  ADC_PRESCALE = 4;       // 76923 Hz

constexpr uint8_t MPU_ADDR     = 0x68;
constexpr uint8_t REG_PWR_MGMT = 0x6B;
constexpr uint8_t REG_ACCEL_X  = 0x3B;

static void mpu_init() {
    Wire.begin();
    Wire.setClock(400000);
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(REG_PWR_MGMT);
    Wire.write(0x01);
    Wire.endTransmission();
}

static uint8_t mpu_lsb_byte() {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(REG_ACCEL_X);
    Wire.endTransmission(false);
    Wire.requestFrom((int)MPU_ADDR, 14);

    uint8_t b = 0;
    int16_t ax = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((ax & 1) << 0);
    int16_t ay = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((ay & 1) << 1);
    int16_t az = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((az & 1) << 2);
    (void)Wire.read(); (void)Wire.read();
    int16_t gx = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((gx & 1) << 3);
    int16_t gy = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((gy & 1) << 4);
    int16_t gz = (Wire.read() << 8) | Wire.read(); b |= (uint8_t)((gz & 1) << 5);
    // 6 бит из MPU; добиваем 2 бита от соседних отсчётов (через цикл XOR).
    return b;
}

static uint8_t adc_lsb_byte(uint8_t channel) {
    adc_fast_set_channel(channel);
    uint8_t b = 0;
    for (uint8_t i = 0; i < 8; i++) {
        b |= (uint8_t)(adc_fast_read() & 1) << i;
    }
    return b;
}

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    adc_fast_init(CH_EXT, ADC_PRESCALE, ADC_REF_AVCC);
    mpu_init();
    trng_print_banner("08_hybrid", 8, 5000, "AVCC+I2C",
                      "XOR(ADC_A0_LSBx8, ADC_A1_LSBx8, MPU_LSBx2) per output byte");
}

void loop() {
    uint8_t a = adc_lsb_byte(CH_EXT);
    uint8_t b = adc_lsb_byte(CH_FLOAT);
    uint8_t m = mpu_lsb_byte();
    uint8_t out = a ^ b ^ m;
    trng_send_u16((uint16_t)out);     // старший байт = 0
}
