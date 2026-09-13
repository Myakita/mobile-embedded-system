package com.example.mobile_embedded_system.domain;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Доменный менеджер тактических ориентиров и персонального целеуказания (ТЗ §4.2, §6.10, §6.13).
 */
public class TacticalWaypointManager {

    public static class NavInfo {
        public final double distanceMeters;
        public final double bearingDegrees;

        public NavInfo(double distanceMeters, double bearingDegrees) {
            this.distanceMeters = distanceMeters;
            this.bearingDegrees = bearingDegrees;
        }
    }

    private final List<Waypoint> waypoints = new ArrayList<>();
    private final Map<Long, Long> unitTargetAssignments = new HashMap<>(); // userId -> waypointId
    private long nextId = 1L;

    /**
     * Создание новой точки с автонумерацией "ОБУ-1", "ОБУ-2" и т.д.
     */
    public synchronized Waypoint addWaypoint(double latitude, double longitude) {
        String callsign = "ОБУ-" + nextId;
        Waypoint wp = new Waypoint(nextId, callsign, latitude, longitude, System.currentTimeMillis());
        nextId++;
        waypoints.add(wp);
        return wp;
    }

    /**
     * Персональное назначение боевой задачи бойцу.
     */
    public synchronized void assignTargetToUnit(long userId, long waypointId) {
        unitTargetAssignments.put(userId, waypointId);
    }

    /**
     * Получение назначенной цели конкретного бойца.
     */
    public synchronized Waypoint getAssignedWaypointForUnit(long userId) {
        Long wpId = unitTargetAssignments.get(userId);
        if (wpId == null) {
            return null;
        }
        for (Waypoint wp : waypoints) {
            if (wp.getId() == wpId) {
                return wp;
            }
        }
        return null;
    }

    public synchronized void clearTargetForUnit(long userId) {
        unitTargetAssignments.remove(userId);
    }

    public synchronized List<Waypoint> getWaypoints() {
        return Collections.unmodifiableList(new ArrayList<>(waypoints));
    }

    public synchronized boolean removeWaypoint(long id) {
        unitTargetAssignments.values().removeIf(wpId -> wpId == id);
        return waypoints.removeIf(wp -> wp.getId() == id);
    }

    /**
     * Поиск бойца, за которым закреплена данная точка ОБУ.
     */
    public synchronized Long getUnitAssignedToWaypoint(long waypointId) {
        for (Map.Entry<Long, Long> entry : unitTargetAssignments.entrySet()) {
            if (entry.getValue() == waypointId) {
                return entry.getKey();
            }
        }
        return null;
    }

    /**
     * Навигационный расчёт параметров наведения бойца на цель.
     */
    public NavInfo calculateNav(double fromLat, double fromLon, Waypoint target) {
        if (target == null) {
            return null;
        }
        double dist = TacticalNavigationCalculator.calculateDistanceMeters(
                fromLat, fromLon,
                target.getLatitude(), target.getLongitude()
        );
        double bearing = TacticalNavigationCalculator.calculateBearingDegrees(
                fromLat, fromLon,
                target.getLatitude(), target.getLongitude()
        );
        return new NavInfo(dist, bearing);
    }
}