package com.example.mobile_embedded_system.data.local;

import androidx.room.ColumnInfo;
import androidx.room.Entity;

import com.example.mobile_embedded_system.data.model.LMashPayload;

/**
 * Запись телеметрии в локальной БД.
 * Составной первичный ключ (deviceSerial, sequence) гарантирует дедупликацию по ТЗ (§13).
 */
@Entity(
        tableName = "telemetry_records",
        primaryKeys = {"device_serial", "sequence"}
)
public class TelemetryEntity {

    @ColumnInfo(name = "device_serial")
    public long deviceSerial;

    @ColumnInfo(name = "sequence")
    public long sequence;

    @ColumnInfo(name = "user_id")
    public long userId;

    @ColumnInfo(name = "destination_id")
    public long destinationId;

    @ColumnInfo(name = "timestamp")
    public long timestamp;

    @ColumnInfo(name = "temperature_celsius")
    public double temperatureCelsius;

    @ColumnInfo(name = "pulse_bpm")
    public int pulseBpm;

    @ColumnInfo(name = "pressure_sys")
    public int pressureSys;

    @ColumnInfo(name = "pressure_dia")
    public int pressureDia;

    @ColumnInfo(name = "latitude")
    public double latitude;

    @ColumnInfo(name = "longitude")
    public double longitude;

    @ColumnInfo(name = "heading_degrees")
    public double headingDegrees;

    @ColumnInfo(name = "position_quality")
    public int positionQuality;

    @ColumnInfo(name = "received_at_ms")
    public long receivedAtMs;

    public TelemetryEntity() {
    }

    /**
     * Фабричный метод конвертации из сетевого пакета LMashPayload.
     */
    public static TelemetryEntity fromPayload(LMashPayload payload) {
        TelemetryEntity entity = new TelemetryEntity();
        entity.deviceSerial = payload.getDeviceSerial();
        entity.sequence = payload.getSequence();
        entity.userId = payload.getUserId();
        entity.destinationId = payload.getDestinationId();
        entity.timestamp = payload.getTimestamp();
        entity.temperatureCelsius = payload.getTemperatureCelsius();
        entity.pulseBpm = payload.getPulseBpm();
        entity.pressureSys = payload.getPressureSys();
        entity.pressureDia = payload.getPressureDia();
        entity.latitude = payload.getLatitude();
        entity.longitude = payload.getLongitude();
        entity.headingDegrees = payload.getHeadingDegrees();
        entity.positionQuality = payload.getPositionQuality();
        entity.receivedAtMs = System.currentTimeMillis();
        return entity;
    }
}