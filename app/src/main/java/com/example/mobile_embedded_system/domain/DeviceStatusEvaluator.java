package com.example.mobile_embedded_system.domain;

/**
 * Доменный классификатор аппаратных статусов терминала (ТЗ §6.6, §6.8).
 */
public final class DeviceStatusEvaluator {

    private DeviceStatusEvaluator() {
        // Утилитный класс
    }

    public enum BatteryState {
        NORMAL,
        WARNING,
        CRITICAL
    }

    public enum GnssState {
        FIX_3D,
        FIX_2D,
        NO_FIX
    }

    public static BatteryState evaluateBattery(int percentage) {
        if (percentage < 15) {
            return BatteryState.CRITICAL;
        }
        if (percentage < 30) {
            return BatteryState.WARNING;
        }
        return BatteryState.NORMAL;
    }

    public static GnssState evaluateGnss(int positionQuality) {
        if (positionQuality >= 3) {
            return GnssState.FIX_3D;
        }
        if (positionQuality >= 1) {
            return GnssState.FIX_2D;
        }
        return GnssState.NO_FIX;
    }
}