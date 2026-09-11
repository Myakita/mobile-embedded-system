package com.example.mobile_embedded_system.data.local;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.example.mobile_embedded_system.data.model.LMashPayload;

import org.junit.Test;

/**
 * Модульный тест проверки формирования записи БД из сетевого пакета LMashPayload (ТЗ §13, §14).
 * Проверяет корректность типов, масштабирование величин и ключи дедупликации.
 */
public class TelemetryEntityTest {

    @Test
    public void testEntityConversionFromPayload() {
        LMashPayload payload = new LMashPayload();
        payload.setDeviceSerial(0x19AA0221L);
        payload.setSequence(471L);
        payload.setUserId(1001L);
        payload.setDestinationId(0x7A831204L);
        payload.setTimestamp(1726000000L);
        payload.setTemperatureX100((short) 3672); // 36.72 °C
        payload.setPulseBpm(84);
        payload.setPressureSys(120);
        payload.setPressureDia(80);
        payload.setLatitudeE7(557539123);
        payload.setLongitudeE7(376208110);
        payload.setHeadingCdeg(18050);
        payload.setPositionQuality(3);

        long beforeConversionMs = System.currentTimeMillis();
        TelemetryEntity entity = TelemetryEntity.fromPayload(payload);

        // Проверка составного первичного ключа дедупликации (deviceSerial, sequence)
        assertEquals(0x19AA0221L, entity.deviceSerial);
        assertEquals(471L, entity.sequence);

        // Проверка маршрутных полей
        assertEquals(1001L, entity.userId);
        assertEquals(0x7A831204L, entity.destinationId);
        assertEquals(1726000000L, entity.timestamp);

        // Проверка физиологических показателей
        assertEquals(36.72, entity.temperatureCelsius, 0.001);
        assertEquals(84, entity.pulseBpm);
        assertEquals(120, entity.pressureSys);
        assertEquals(80, entity.pressureDia);

        // Проверка координат и навигации
        assertEquals(55.7539123, entity.latitude, 0.0000001);
        assertEquals(37.6208110, entity.longitude, 0.0000001);
        assertEquals(180.50, entity.headingDegrees, 0.01);
        assertEquals(3, entity.positionQuality);

        // Метка времени приема
        assertTrue(entity.receivedAtMs >= beforeConversionMs);
    }
}