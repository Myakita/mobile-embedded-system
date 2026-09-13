package com.example.mobile_embedded_system.domain;

/**
 * Тактическая путевая точка / ориентир целеуказания (ТЗ §6.10, §6.13).
 */
public class Waypoint {

    private final long id;
    private final String callsign;
    private final double latitude;
    private final double longitude;
    private final long timestampMs;

    public Waypoint(long id, String callsign, double latitude, double longitude, long timestampMs) {
        this.id = id;
        this.callsign = callsign;
        this.latitude = latitude;
        this.longitude = longitude;
        this.timestampMs = timestampMs;
    }

    public long getId() {
        return id;
    }

    public String getCallsign() {
        return callsign;
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
}