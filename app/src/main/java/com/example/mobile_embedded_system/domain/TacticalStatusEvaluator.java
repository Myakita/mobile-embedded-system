package com.example.mobile_embedded_system.domain;

/**
 * Оценщик физиологического статуса бойца по витальным показателям (ТЗ §4.2, §6.4, §6.7).
 */
public final class TacticalStatusEvaluator {

    public enum Status {
        OK,
        WARNING,
        CRITICAL
    }

    private TacticalStatusEvaluator() {
        // Утилитный класс
    }

    /**
     * Классификация состояния по ЧСС и температуре тела.
     * Пороги:
     * - CRITICAL: ЧСС < 45 или > 120 уд/мин, Температура > 38.5 °C
     * - WARNING: ЧСС > 95 уд/мин или Температура > 37.2 °C
     * - OK: номинальные значения
     */
    public static Status evaluate(int pulseBpm, double temperatureCelsius) {
        if (pulseBpm > 120 || pulseBpm < 45 || temperatureCelsius > 38.5) {
            return Status.CRITICAL;
        }
        if (pulseBpm > 95 || temperatureCelsius > 37.2) {
            return Status.WARNING;
        }
        return Status.OK;
    }
}