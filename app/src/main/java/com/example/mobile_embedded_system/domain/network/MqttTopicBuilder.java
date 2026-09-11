package com.example.mobile_embedded_system.domain.network;

import java.util.Objects;

/**
 * Построитель MQTT-топиков по спецификации архитектуры.
 */
public final class MqttTopicBuilder {

    public static final String TYPE_TELEMETRY = "telemetry";
    public static final String TYPE_COMMAND   = "command";

    private MqttTopicBuilder() {
    }

    /**
     * Формирует топик для публикации телеметрии.
     */
    public static String buildTelemetryPublishTopic(
            String networkRoot,
            String hierarchyPath,
            long destinationId,
            long sourceId
    ) {
        return buildTopic(networkRoot, hierarchyPath, TYPE_TELEMETRY, formatHexId(destinationId), formatHexId(sourceId));
    }

    /**
     * Формирует топик для публикации команды.
     */
    public static String buildCommandPublishTopic(
            String networkRoot,
            String hierarchyPath,
            long destinationId,
            long sourceId
    ) {
        return buildTopic(networkRoot, hierarchyPath, TYPE_COMMAND, formatHexId(destinationId), formatHexId(sourceId));
    }

    /**
     * Формирует топик подписки на входящие сообщения конкретного типа, адресованные данному узлу.
     * Пример: mesh-a/+/+/+/telemetry/to/7A831204/#
     */
    public static String buildInboxSubscriptionTopic(
            String networkRoot,
            String messageType,
            long myId
    ) {
        String cleanRoot = sanitize(networkRoot);
        return cleanRoot + "/+/+/+/" + messageType + "/to/" + formatHexId(myId) + "/#";
    }

    /**
     * Формирует универсальный топик подписки на весь трафик поддерева (для командира/штаба).
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

    /**
     * Приведение ID к 8-значной шестнадцатеричной строке верхнего регистра (как в ТЗ: 19AA0221).
     */
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