package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/**
 * Тестирование сериализации пакетов Uplink (ТЗ §5.1, §14).
 */
public class TacticalCommandTest {

    @Test
    public void testCommandJsonSerialization() {
        TacticalCommand cmd = new TacticalCommand(1002L, "ОБУ-1", 55.753912, 37.620811);

        assertEquals("ASSIGN_TARGET", cmd.getCommand());
        assertEquals(1002L, cmd.getTargetUserId());
        assertEquals("ОБУ-1", cmd.getWaypointCallsign());

        String json = cmd.toJson();
        assertNotNull(json);
        assertTrue(json.contains("\"cmd\":\"ASSIGN_TARGET\""));
        assertTrue(json.contains("\"target\":1002"));
        assertTrue(json.contains("\"callsign\":\"ОБУ-1\""));
        assertTrue(json.contains("55.753912"));
        assertTrue(json.contains("37.620811"));
        assertTrue(json.contains("\"ts\":"));
    }
}