package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/**
 * Модульные тесты оценки питания и спутниковой группировки (ТЗ §5.1, §6.6, §6.8).
 */
public class DeviceStatusEvaluatorTest {

    @Test
    public void testBatteryThresholds() {
        assertEquals(DeviceStatusEvaluator.BatteryState.NORMAL, DeviceStatusEvaluator.evaluateBattery(100));
        assertEquals(DeviceStatusEvaluator.BatteryState.NORMAL, DeviceStatusEvaluator.evaluateBattery(30));
        assertEquals(DeviceStatusEvaluator.BatteryState.WARNING, DeviceStatusEvaluator.evaluateBattery(29));
        assertEquals(DeviceStatusEvaluator.BatteryState.WARNING, DeviceStatusEvaluator.evaluateBattery(15));
        assertEquals(DeviceStatusEvaluator.BatteryState.CRITICAL, DeviceStatusEvaluator.evaluateBattery(14));
        assertEquals(DeviceStatusEvaluator.BatteryState.CRITICAL, DeviceStatusEvaluator.evaluateBattery(0));
    }

    @Test
    public void testGnssThresholds() {
        assertEquals(DeviceStatusEvaluator.GnssState.FIX_3D, DeviceStatusEvaluator.evaluateGnss(3));
        assertEquals(DeviceStatusEvaluator.GnssState.FIX_3D, DeviceStatusEvaluator.evaluateGnss(4));
        assertEquals(DeviceStatusEvaluator.GnssState.FIX_2D, DeviceStatusEvaluator.evaluateGnss(1));
        assertEquals(DeviceStatusEvaluator.GnssState.FIX_2D, DeviceStatusEvaluator.evaluateGnss(2));
        assertEquals(DeviceStatusEvaluator.GnssState.NO_FIX, DeviceStatusEvaluator.evaluateGnss(0));
        assertEquals(DeviceStatusEvaluator.GnssState.NO_FIX, DeviceStatusEvaluator.evaluateGnss(-1));
    }
}