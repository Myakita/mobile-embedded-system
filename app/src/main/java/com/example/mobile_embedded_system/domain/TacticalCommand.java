package com.example.mobile_embedded_system.domain;

import java.util.Locale;

/**
 * Пакет тактического приказа целеуказания (C2 Uplink) (ТЗ §4.1, §14).
 */
public class TacticalCommand {

    public static final String CMD_ASSIGN_TARGET = "ASSIGN_TARGET";

    private final String command;
    private final long targetUserId;
    private final String waypointCallsign;
    private final double latitude;
    private final double longitude;
    private final long timestampMs;

    public TacticalCommand(long targetUserId, String waypointCallsign, double latitude, double longitude) {
        this.command = CMD_ASSIGN_TARGET;
        this.targetUserId = targetUserId;
        this.waypointCallsign = waypointCallsign;
        this.latitude = latitude;
        this.longitude = longitude;
        this.timestampMs = System.currentTimeMillis();
    }

    public String getCommand() {
        return command;
    }

    public long getTargetUserId() {
        return targetUserId;
    }

    public String getWaypointCallsign() {
        return waypointCallsign;
    }

    public double getLatitude() {
        return latitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public long getTimestampMs() {
        return timestampMs;
    }

    /**
     * Сериализация приказа в легковесный JSON-пакет для передачи по радиоканалу.
     */
    public String toJson() {
        return String.format(Locale.US,
                "{\"cmd\":\"%s\",\"target\":%d,\"callsign\":\"%s\",\"lat\":%.6f,\"lon\":%.6f,\"ts\":%d}",
                command, targetUserId, waypointCallsign, latitude, longitude, timestampMs);
    }
}