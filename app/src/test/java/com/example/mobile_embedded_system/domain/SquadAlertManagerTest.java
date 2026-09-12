package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import org.junit.Before;
import org.junit.Test;

/**
 * Тестирование менеджера тревог и эскалации (ТЗ §5.1, §6.7).
 */
public class SquadAlertManagerTest {

    private SquadAlertManager alertManager;

    @Before
    public void setUp() {
        alertManager = new SquadAlertManager();
    }

    @Test
    public void testNominalTelemetryDoesNotTriggerAlert() {
        TelemetryEntity entity = new TelemetryEntity();
        entity.userId = 1001L;
        entity.pulseBpm = 75;
        entity.temperatureCelsius = 36.6;

        SquadAlertManager.AlertInfo alert = alertManager.processTelemetry(entity);
        assertNull(alert);
        assertFalse(alertManager.hasActiveCriticalAlert());
    }

    @Test
    public void testCriticalPulseTriggersAlert() {
        TelemetryEntity entity = new TelemetryEntity();
        entity.userId = 1002L;
        entity.pulseBpm = 135;
        entity.temperatureCelsius = 37.0;

        SquadAlertManager.AlertInfo alert = alertManager.processTelemetry(entity);
        assertNotNull(alert);
        assertEquals(1002L, alert.userId);
        assertTrue(alert.reason.contains("ТАХИКАРДИЯ"));
        assertTrue(alertManager.hasActiveCriticalAlert());
    }

    @Test
    public void testRecoveryClearsActiveCriticalState() {
        TelemetryEntity entity = new TelemetryEntity();
        entity.userId = 1002L;
        entity.pulseBpm = 135;
        entity.temperatureCelsius = 37.0;
        alertManager.processTelemetry(entity);
        assertTrue(alertManager.hasActiveCriticalAlert());

        // Нормализация показателей
        entity.pulseBpm = 80;
        alertManager.processTelemetry(entity);
        assertFalse(alertManager.hasActiveCriticalAlert());
    }
}