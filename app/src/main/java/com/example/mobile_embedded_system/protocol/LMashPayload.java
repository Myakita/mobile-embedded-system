package com.example.mobile_embedded_system.protocol;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * 44-байтовая бинарная структура пакета телеметрии LMash_Payload_t (ТЗ §13).
 * Порядок байт: Little-Endian.
 */
public class LMashPayload {

    public static final int PAYLOAD_SIZE_BYTES = 44;

    private final long deviceSerial;      // uint32
    private final long sequence;          // uint32
    private final long userId;            // uint16
    private final long destinationId;     // uint16
    private final long timestamp;         // uint32 (Unix epoch seconds)
    private final double latitude;        // double (8 bytes)
    private final double longitude;       // double (8 bytes)
    private final double headingDegrees;  // float (4 bytes)
    private final int pulseBpm;           // uint8 (1 byte)
    private final double temperatureCelsius; // float (4 bytes)
    private final int pressureSys;        // uint8 (1 byte)
    private final int pressureDia;        // uint8 (1 byte)
    private final int positionQuality;    // uint8 (1 byte)

    public LMashPayload(long deviceSerial, long sequence, long userId, long destinationId,
                        long timestamp, double latitude, double longitude, double headingDegrees,
                        int pulseBpm, double temperatureCelsius, int pressureSys,
                        int pressureDia, int positionQuality) {
        this.deviceSerial = deviceSerial;
        this.sequence = sequence;
        this.userId = userId;
        this.destinationId = destinationId;
        this.timestamp = timestamp;
        this.latitude = latitude;
        this.longitude = longitude;
        this.headingDegrees = headingDegrees;
        this.pulseBpm = pulseBpm;
        this.temperatureCelsius = temperatureCelsius;
        this.pressureSys = pressureSys;
        this.pressureDia = pressureDia;
        this.positionQuality = positionQuality;
    }

    public static LMashPayload fromByteArray(byte[] bytes) {
        if (bytes == null || bytes.length != PAYLOAD_SIZE_BYTES) {
            throw new IllegalArgumentException("Размер пакета должен быть строго " + PAYLOAD_SIZE_BYTES + " байт");
        }

        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);

        long deviceSerial = buffer.getInt() & 0xFFFFFFFFL;
        long sequence = buffer.getInt() & 0xFFFFFFFFL;
        long userId = buffer.getShort() & 0xFFFFL;
        long destinationId = buffer.getShort() & 0xFFFFL;
        long timestamp = buffer.getInt() & 0xFFFFFFFFL;
        double latitude = buffer.getDouble();
        double longitude = buffer.getDouble();
        double heading = buffer.getFloat();
        double temperature = buffer.getFloat();
        int pulse = buffer.get() & 0xFF;
        int pSys = buffer.get() & 0xFF;
        int pDia = buffer.get() & 0xFF;
        int quality = buffer.get() & 0xFF;

        return new LMashPayload(
                deviceSerial, sequence, userId, destinationId, timestamp,
                latitude, longitude, heading, pulse, temperature, pSys, pDia, quality
        );
    }

    public byte[] toByteArray() {
        ByteBuffer buffer = ByteBuffer.allocate(PAYLOAD_SIZE_BYTES).order(ByteOrder.LITTLE_ENDIAN);

        buffer.putInt((int) (deviceSerial & 0xFFFFFFFFL));
        buffer.putInt((int) (sequence & 0xFFFFFFFFL));
        buffer.putShort((short) (userId & 0xFFFFL));
        buffer.putShort((short) (destinationId & 0xFFFFL));
        buffer.putInt((int) (timestamp & 0xFFFFFFFFL));
        buffer.putDouble(latitude);
        buffer.putDouble(longitude);
        buffer.putFloat((float) headingDegrees);
        buffer.putFloat((float) temperatureCelsius);
        buffer.put((byte) (pulseBpm & 0xFF));
        buffer.put((byte) (pressureSys & 0xFF));
        buffer.put((byte) (pressureDia & 0xFF));
        buffer.put((byte) (positionQuality & 0xFF));

        return buffer.array();
    }

    public long getDeviceSerial() {
        return deviceSerial;
    }

    public long getSequence() {
        return sequence;
    }

    public long getUserId() {
        return userId;
    }

    public long getDestinationId() {
        return destinationId;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public double getLatitude() {
        return latitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public double getHeadingDegrees() {
        return headingDegrees;
    }

    public int getPulseBpm() {
        return pulseBpm;
    }

    public double getTemperatureCelsius() {
        return temperatureCelsius;
    }

    public int getPressureSys() {
        return pressureSys;
    }

    public int getPressureDia() {
        return pressureDia;
    }

    public int getPositionQuality() {
        return positionQuality;
    }
}