package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

/**
 * Тестирование точности генерации колец дальности (ТЗ §5.1, §6.10).
 */
public class TacticalRangeRingGeneratorTest {

    private static final double DELTA_DISTANCE = 1.0; // Погрешность до 1 метра

    @Test
    public void testRingIsClosed() {
        double lat = 55.7539;
        double lon = 37.6208;
        List<TacticalRangeRingGenerator.GeoPoint> ring = TacticalRangeRingGenerator.generateRingPoints(lat, lon, 100.0);

        assertFalse(ring.isEmpty());
        TacticalRangeRingGenerator.GeoPoint first = ring.get(0);
        TacticalRangeRingGenerator.GeoPoint last = ring.get(ring.size() - 1);

        assertEquals(first.latitude, last.latitude, 0.000001);
        assertEquals(first.longitude, last.longitude, 0.000001);
    }

    @Test
    public void testRingRadiusAccuracy() {
        double centerLat = 55.7539;
        double centerLon = 37.6208;
        double targetRadius = 250.0;

        List<TacticalRangeRingGenerator.GeoPoint> ring = TacticalRangeRingGenerator.generateRingPoints(centerLat, centerLon, targetRadius);

        for (TacticalRangeRingGenerator.GeoPoint point : ring) {
            double actualDistance = TacticalNavigationCalculator.calculateDistanceMeters(
                    centerLat, centerLon, point.latitude, point.longitude
            );
            assertEquals(targetRadius, actualDistance, DELTA_DISTANCE);
        }
    }
}