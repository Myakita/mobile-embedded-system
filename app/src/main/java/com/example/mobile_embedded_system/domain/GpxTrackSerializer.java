package com.example.mobile_embedded_system.domain;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Тактический сериализатор сессии в стандартный формат GPX 1.1 (ТЗ §4.3, §6.9).
 */
public final class GpxTrackSerializer {

    private GpxTrackSerializer() {
        // Утилитный класс
    }

    public static String serialize(String trackName, List<TelemetryEntity> points) {
        SimpleDateFormat isoFormat = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        isoFormat.setTimeZone(TimeZone.getTimeZone("UTC"));

        StringBuilder sb = new StringBuilder();
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        sb.append("<gpx version=\"1.1\" creator=\"TacticalTerminalBMS\" ")
                .append("xmlns=\"http://www.topografix.com/GPX/1/1\">\n");
        sb.append("  <metadata>\n");
        sb.append("    <name>").append(escapeXml(trackName)).append("</name>\n");
        sb.append("    <time>").append(isoFormat.format(new Date())).append("</time>\n");
        sb.append("  </metadata>\n");
        sb.append("  <trk>\n");
        sb.append("    <name>").append(escapeXml(trackName)).append("</name>\n");
        sb.append("    <trkseg>\n");

        if (points != null) {
            for (TelemetryEntity pt : points) {
                sb.append(String.format(Locale.US,
                        "      <trkpt lat=\"%.6f\" lon=\"%.6f\">\n",
                        pt.latitude, pt.longitude));

                long timeMs = pt.timestamp > 10000000000L ? pt.timestamp : pt.timestamp * 1000L;
                sb.append("        <time>").append(isoFormat.format(new Date(timeMs))).append("</time>\n");
                sb.append("        <extensions>\n");
                sb.append("          <pulse>").append(pt.pulseBpm).append("</pulse>\n");
                sb.append(String.format(Locale.US, "          <temp>%.1f</temp>\n", pt.temperatureCelsius));
                sb.append("          <heading>").append(Math.round(pt.headingDegrees)).append("</heading>\n");
                sb.append("        </extensions>\n");
                sb.append("      </trkpt>\n");
            }
        }

        sb.append("    </trkseg>\n");
        sb.append("  </trk>\n");
        sb.append("</gpx>\n");

        return sb.toString();
    }

    private static String escapeXml(String text) {
        if (text == null) return "";
        return text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&apos;");
    }
}