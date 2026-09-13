package com.example.mobile_embedded_system.domain;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Before;
import org.junit.Test;

/**
 * Тестирование менеджера тактических ориентиров и назначения целей (ТЗ §5.1, §6.10, §6.13).
 */
public class TacticalWaypointManagerTest {

    private TacticalWaypointManager manager;

    @Before
    public void setUp() {
        manager = new TacticalWaypointManager();
    }

    @Test
    public void testSequentialNaming() {
        Waypoint wp1 = manager.addWaypoint(55.75, 37.61);
        Waypoint wp2 = manager.addWaypoint(55.76, 37.62);

        assertEquals("ОБУ-1", wp1.getCallsign());
        assertEquals("ОБУ-2", wp2.getCallsign());
        assertEquals(2, manager.getWaypoints().size());
    }

    @Test
    public void testUnitTargetAssignmentPersistence() {
        Waypoint targetShooter = manager.addWaypoint(55.755, 37.625);
        Waypoint targetMedic = manager.addWaypoint(55.758, 37.629);

        manager.assignTargetToUnit(1002L, targetShooter.getId());
        manager.assignTargetToUnit(1003L, targetMedic.getId());

        // Проверяем, что цели закреплены независимо за каждым бойцом
        Waypoint retrieved1002 = manager.getAssignedWaypointForUnit(1002L);
        Waypoint retrieved1003 = manager.getAssignedWaypointForUnit(1003L);

        assertNotNull(retrieved1002);
        assertNotNull(retrieved1003);
        assertEquals(targetShooter.getId(), retrieved1002.getId());
        assertEquals(targetMedic.getId(), retrieved1003.getId());

        // Проверяем удаление
        manager.clearTargetForUnit(1002L);
        assertNull(manager.getAssignedWaypointForUnit(1002L));
        assertNotNull(manager.getAssignedWaypointForUnit(1003L));
    }

    @Test
    public void testNavCalculation() {
        Waypoint target = manager.addWaypoint(56.0, 37.0);
        TacticalWaypointManager.NavInfo nav = manager.calculateNav(55.0, 37.0, target);

        assertNotNull(nav);
        assertEquals(0.0, nav.bearingDegrees, 0.5);
        assertEquals(111195.0, nav.distanceMeters, 200.0);
    }
}