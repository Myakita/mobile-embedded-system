package com.example.mobile_embedded_system.domain.network;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class MqttTopicBuilderTest {

    @Test
    public void testTelemetryPublishTopic() {
        String topic = MqttTopicBuilder.buildTelemetryPublishTopic(
                "mesh-a",
                "7F10/21A0/0304",
                0x7A831204L,
                0x19AA0221L
        );
        assertEquals("mesh-a/7F10/21A0/0304/telemetry/to/7A831204/from/19AA0221", topic);
    }

    @Test
    public void testCommandPublishTopic() {
        String topic = MqttTopicBuilder.buildCommandPublishTopic(
                "mesh-a",
                "7F10/21A0/0304",
                0x19AA0221L,
                0x7A831204L
        );
        assertEquals("mesh-a/7F10/21A0/0304/command/to/19AA0221/from/7A831204", topic);
    }

    @Test
    public void testDeviceSubscriptionTopic() {
        String topic = MqttTopicBuilder.buildDeviceSubscriptionTopic(
                "mesh-a",
                "7F10/21A0/0304",
                MqttTopicBuilder.TYPE_COMMAND,
                0x19AA0221L
        );
        assertEquals("mesh-a/7F10/21A0/0304/command/to/19AA0221/#", topic);
    }

    @Test
    public void testSubtreeSubscriptionTopic() {
        String topic = MqttTopicBuilder.buildSubtreeSubscriptionTopic(
                "mesh-a",
                "7F10/21A0"
        );
        assertEquals("mesh-a/7F10/21A0/#", topic);
    }
}