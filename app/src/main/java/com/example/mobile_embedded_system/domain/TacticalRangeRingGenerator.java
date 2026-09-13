package com.example.mobile_embedded_system.domain;

import java.util.ArrayList;
import java.util.List;

/**
 * Генератор тактических колец дальности (Range Rings) (ТЗ §6.10, §6.13).
 */
public final class TacticalRangeRingGenerator {

    private static final double EARTH_RADIUS_METERS = 6371000.0;
    private static final int DEFAULT_POINTS_COUNT = 36; // Шаг 10 градусов

    private TacticalRangeRingGenerator() {
        // Утилитный класс
    }

    public static class GeoPoint {
        public final double latitude;
        public final double longitude;

        public GeoPoint(double latitude, double longitude) {
            this.latitude = latitude;
            this.longitude = longitude;
        }
    }

    /**
     * Генерация точек замкнутой окружности заданного радиуса (в метрах) вокруг центра.
     */
    public static List<GeoPoint> generateRingPoints(double centerLat, double centerLon, double radiusMeters) {
        return generateRingPoints(centerLat, centerLon, radiusMeters, DEFAULT_POINTS_COUNT);
    }

    public static List<GeoPoint> generateRingPoints(double centerLat, double centerLon, double radiusMeters, int pointsCount) {
        List<GeoPoint> ringPoints = new ArrayList<>(pointsCount + 1);

        double distRatio = radiusMeters / EARTH_RADIUS_METERS;
        double centerLatRad = Math.toRadians(centerLat);
        double centerLonRad = Math.toRadians(centerLon);

        for (int i = 0; i <= pointsCount; i++) {
            double bearingRad = Math.toRadians((360.0 / pointsCount) * i);

            double latRad = Math.asin(
                    Math.sin(centerLatRad) * Math.cos(distRatio) +
                            Math.cos(centerLatRad) * Math.sin(distRatio) * Math.cos(bearingRad)
            );

            double lonRad = centerLonRad + Math.atan2(
                    Math.sin(bearingRad) * Math.sin(distRatio) * Math.cos(centerLatRad),
                    Math.cos(distRatio) - Math.sin(centerLatRad) * Math.sin(latRad)
            );

            ringPoints.add(new GeoPoint(Math.toDegrees(latRad), Math.toDegrees(lonRad)));
        }

        return ringPoints;
    }
}