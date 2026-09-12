package com.example.mobile_embedded_system.domain;

/**
 * Геодезический калькулятор тактической навигации (ТЗ §6.10, §6.13).
 */
public final class TacticalNavigationCalculator {

    private static final double EARTH_RADIUS_METERS = 6371000.0;

    private TacticalNavigationCalculator() {
        // Утилитный класс
    }

    /**
     * Расчёт расстояния между двумя координатами по формуле гаверсинусов (в метрах).
     */
    public static double calculateDistanceMeters(double lat1, double lon1, double lat2, double lon2) {
        double phi1 = Math.toRadians(lat1);
        double phi2 = Math.toRadians(lat2);
        double deltaPhi = Math.toRadians(lat2 - lat1);
        double deltaLambda = Math.toRadians(lon2 - lon1);

        double a = Math.sin(deltaPhi / 2.0) * Math.sin(deltaPhi / 2.0)
                + Math.cos(phi1) * Math.cos(phi2)
                * Math.sin(deltaLambda / 2.0) * Math.sin(deltaLambda / 2.0);

        double c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));

        return EARTH_RADIUS_METERS * c;
    }

    /**
     * Расчёт истинного азимута (пеленга) от точки 1 на точку 2 в градусах (0..359).
     */
    public static double calculateBearingDegrees(double lat1, double lon1, double lat2, double lon2) {
        double phi1 = Math.toRadians(lat1);
        double phi2 = Math.toRadians(lat2);
        double deltaLambda = Math.toRadians(lon2 - lon1);

        double y = Math.sin(deltaLambda) * Math.cos(phi2);
        double x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);

        double bearingRad = Math.atan2(y, x);
        double bearingDeg = Math.toDegrees(bearingRad);

        return (bearingDeg + 360.0) % 360.0;
    }
}