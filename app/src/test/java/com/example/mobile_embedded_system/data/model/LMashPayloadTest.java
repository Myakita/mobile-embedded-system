package com.example.mobile_embedded_system.data.model;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class LMashPayloadTest {

    @Test
    public void testSerializationAndDeserialization() {
        LMashPayload source = new LMashPayload();
        source.setVersion(1);
        source.setMessageType(LMashPayload.MSG_TELEMETRY);
        source.setCommandType(LMashPayload.CMD_NONE);
        source.setFlags(0x05);
        source.setTtl(4);
        source.setSequence(471L);
        source.setTimestamp(1726000000L);
        source.setDeviceSerial(0x19AA0221L);
        source.setUserId(1001L);
        source.setDestinationId(0x7A831204L);
        source.setTemperatureX100((short) 3672);
        source.setPulseBpm(84);
        source.setPressureSys(120);
        source.setPressureDia(80);
        source.setLatitudeE7(557539123);
        source.setLongitudeE7(376208110);
        source.setHeadingCdeg(18050);
        source.setPositionQuality(3);

        byte[] serialized = source.toBytes();
        assertEquals(LMashPayload.PAYLOAD_SIZE, serialized.length);

        LMashPayload restored = LMashPayload.fromBytes(serialized);

        assertEquals(source, restored);
        assertEquals(36.72, restored.getTemperatureCelsius(), 0.001);
        assertEquals(55.7539123, restored.getLatitude(), 0.0000001);
        assertEquals(37.6208110, restored.getLongitude(), 0.0000001);
        assertEquals(180.50, restored.getHeadingDegrees(), 0.01);
        assertEquals("120 / 80", restored.getPressureString());
        assertEquals("Хорошее", restored.getPositionQualityText());
        assertTrue(restored.isTelemetry());
    }

    @Test
    public void testCommandCreation() {
        LMashPayload cmd = LMashPayload.createCommand(
                102L,
                1726000050L,
                0x19AA0221L,
                1001L,
                0x7A831204L,
                LMashPayload.CMD_RETURN
        );

        byte[] rawBytes = cmd.toBytes();
        assertEquals(LMashPayload.PAYLOAD_SIZE, rawBytes.length);

        LMashPayload parsed = LMashPayload.fromBytes(rawBytes);
        assertTrue(parsed.isCommand());
        assertEquals(LMashPayload.CMD_RETURN, parsed.getCommandType());
        assertEquals(102L, parsed.getSequence());
    }
}