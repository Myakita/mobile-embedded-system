package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

/**
 * Модульные тесты генератора тактических GPX-треков (ТЗ §5.1, §6.9).
 */
public class GpxTrackSerializerTest {

    @Test
    public void testEmptyListSerializesValidGpx() {
        String gpx = GpxTrackSerializer.serialize("EMPTY_MISSION", new ArrayList<>());
        assertNotNull(gpx);
        assertTrue(gpx.contains("<trkseg>"));
        assertTrue(gpx.contains("</trkseg>"));
        assertTrue(gpx.contains("EMPTY_MISSION"));
    }

    @Test
    public void testPointsFormattingAndExtensions() {
        List<TelemetryEntity> points = new ArrayList<>();
        TelemetryEntity e = new TelemetryEntity();
        e.latitude = 55.753912;
        e.longitude = 37.620811;
        e.timestamp = 1700000000L;
        e.pulseBpm = 85;
        e.temperatureCelsius = 36.6;
        e.headingDegrees = 42.0;
        points.add(e);

        String gpx = GpxTrackSerializer.serialize("COMBAT_OP_1", points);
        assertTrue(gpx.contains("lat=\"55.753912\""));
        assertTrue(gpx.contains("lon=\"37.620811\""));
        assertTrue(gpx.contains("<pulse>85</pulse>"));
        assertTrue(gpx.contains("<temp>36.6</temp>"));
        assertTrue(gpx.contains("<heading>42</heading>"));
    }
}