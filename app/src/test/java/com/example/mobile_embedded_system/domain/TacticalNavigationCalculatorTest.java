package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/**
 * Тестирование расчётов дистанции и пеленга (ТЗ §5.1, §6.10).
 */
public class TacticalNavigationCalculatorTest {

    private static final double DELTA_DISTANCE = 1.0; // точность до 1 метра
    private static final double DELTA_BEARING = 0.5;  // точность до 0.5 градуса

    @Test
    public void testDistanceToSamePointIsZero() {
        double dist = TacticalNavigationCalculator.calculateDistanceMeters(55.7539, 37.6208, 55.7539, 37.6208);
        assertEquals(0.0, dist, DELTA_DISTANCE);
    }

    @Test
    public void testBearingDirectNorth() {
        // Точка строго на север: широта увеличивается, долгота та же
        double bearing = TacticalNavigationCalculator.calculateBearingDegrees(55.0, 37.0, 56.0, 37.0);
        assertEquals(0.0, bearing, DELTA_BEARING);
    }

    @Test
    public void testBearingDirectEast() {
        // Точка строго на восток на экваторе
        double bearing = TacticalNavigationCalculator.calculateBearingDegrees(0.0, 0.0, 0.0, 1.0);
        assertEquals(90.0, bearing, DELTA_BEARING);
    }

    @Test
    public void testBearingDirectSouth() {
        // Точка строго на юг
        double bearing = TacticalNavigationCalculator.calculateBearingDegrees(56.0, 37.0, 55.0, 37.0);
        assertEquals(180.0, bearing, DELTA_BEARING);
    }

    @Test
    public void testBearingDirectWest() {
        // Точка строго на запад на экваторе
        double bearing = TacticalNavigationCalculator.calculateBearingDegrees(0.0, 1.0, 0.0, 0.0);
        assertEquals(270.0, bearing, DELTA_BEARING);
    }

    @Test
    public void testKnownDistanceApproximation() {
        // 1 градус по меридиану ~ 111.195 км
        double dist = TacticalNavigationCalculator.calculateDistanceMeters(55.0, 37.0, 56.0, 37.0);
        assertEquals(111195.0, dist, 200.0);
    }
}