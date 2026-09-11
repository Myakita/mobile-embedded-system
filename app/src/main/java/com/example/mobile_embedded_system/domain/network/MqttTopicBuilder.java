package com.example.mobile_embedded_system.domain.network;

import java.util.Objects;

/**
 * Построитель MQTT-топиков по спецификации архитектуры v3 (§9, §10).
 */
public final class MqttTopicBuilder {

    public static final String TYPE_TELEMETRY = "telemetry";
    public static final String TYPE_COMMAND   = "command";

    private MqttTopicBuilder() {
    }

    public static String buildTelemetryPublishTopic(
            String networkRoot,
            String hierarchyPath,
            long destinationId,
            long sourceId
    ) {
        return buildTopic(networkRoot, hierarchyPath, TYPE_TELEMETRY, formatHexId(destinationId), formatHexId(sourceId));
    }

    public static String buildCommandPublishTopic(
            String networkRoot,
            String hierarchyPath,
            long destinationId,
            long sourceId
    ) {
        return buildTopic(networkRoot, hierarchyPath, TYPE_COMMAND, formatHexId(destinationId), formatHexId(sourceId));
    }

    /**
     * Формирует топик подписки на входящие команды/сообщения для устройства с известным путем в дереве.
     * Пример: mesh-a/7F10/21A0/0304/command/to/19AA0221/#
     */
    public static String buildDeviceSubscriptionTopic(
            String networkRoot,
            String hierarchyPath,
            String messageType,
            long myId
    ) {
        String cleanRoot = sanitize(networkRoot);
        String cleanPath = sanitize(hierarchyPath);
        return cleanRoot + "/" + cleanPath + "/" + messageType + "/to/" + formatHexId(myId) + "/#";
    }

    /**
     * Формирует подписку на всё поддерево подразделения (для командира/штаба).
     * Пример: mesh-a/7F10/21A0/#
     */
    public static String buildSubtreeSubscriptionTopic(
            String networkRoot,
            String hierarchyPath
    ) {
        String cleanRoot = sanitize(networkRoot);
        String cleanPath = sanitize(hierarchyPath);
        return cleanRoot + "/" + cleanPath + "/#";
    }

    private static String buildTopic(
            String networkRoot,
            String hierarchyPath,
            String messageType,
            String destination,
            String source
    ) {
        String cleanRoot = sanitize(networkRoot);
        String cleanPath = sanitize(hierarchyPath);
        return cleanRoot + "/" + cleanPath + "/" + messageType + "/to/" + destination + "/from/" + source;
    }

    public static String formatHexId(long id) {
        return String.format("%08X", id & 0xFFFFFFFFL);
    }

    private static String sanitize(String part) {
        Objects.requireNonNull(part, "Topic component must not be null");
        String trimmed = part.trim();
        while (trimmed.startsWith("/")) {
            trimmed = trimmed.substring(1);
        }
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }
}