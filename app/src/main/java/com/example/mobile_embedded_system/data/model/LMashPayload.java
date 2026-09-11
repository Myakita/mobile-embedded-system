package com.example.mobile_embedded_system.data.model;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Objects;

/**
 * Парсер и сериализатор бинарного протокола LMash_Payload_t (54 байта, Little-Endian).
 */
public class LMashPayload {

    public static final int PAYLOAD_SIZE = 54;

    public static final int MSG_TELEMETRY = 0;
    public static final int MSG_COMMAND   = 1;

    public static final int CMD_NONE      = 0;
    public static final int CMD_CHECK_IN  = 1;
    public static final int CMD_HOLD      = 2;
    public static final int CMD_RETURN    = 3;

    private int version;
    private int messageType;
    private int commandType;
    private int flags;
    private int ttl;

    private long sequence;
    private long timestamp;

    private long deviceSerial;
    private long userId;
    private long destinationId;

    private short temperatureX100;
    private int pulseBpm;
    private int pressureSys;
    private int pressureDia;

    private int latitudeE7;
    private int longitudeE7;
    private int headingCdeg;
    private int positionQuality;

    public LMashPayload() {
    }

    public static LMashPayload fromBytes(byte[] bytes) {
        if (bytes == null || bytes.length < PAYLOAD_SIZE) {
            throw new IllegalArgumentException("Payload array is invalid or smaller than " + PAYLOAD_SIZE + " bytes");
        }

        ByteBuffer buffer = ByteBuffer.wrap(bytes);
        buffer.order(ByteOrder.LITTLE_ENDIAN);

        LMashPayload payload = new LMashPayload();

        payload.version = buffer.get() & 0xFF;
        payload.messageType = buffer.get() & 0xFF;
        payload.commandType = buffer.get() & 0xFF;
        payload.flags = buffer.get() & 0xFF;
        payload.ttl = buffer.get() & 0xFF;

        payload.sequence = buffer.getInt() & 0xFFFFFFFFL;
        payload.timestamp = buffer.getInt() & 0xFFFFFFFFL;

        payload.deviceSerial = buffer.getLong();
        payload.userId = buffer.getLong();
        payload.destinationId = buffer.getLong();

        payload.temperatureX100 = buffer.getShort();
        payload.pulseBpm = buffer.getShort() & 0xFFFF;
        payload.pressureSys = buffer.get() & 0xFF;
        payload.pressureDia = buffer.get() & 0xFF;

        payload.latitudeE7 = buffer.getInt();
        payload.longitudeE7 = buffer.getInt();
        payload.headingCdeg = buffer.getShort() & 0xFFFF;
        payload.positionQuality = buffer.get() & 0xFF;

        return payload;
    }

    public byte[] toBytes() {
        ByteBuffer buffer = ByteBuffer.allocate(PAYLOAD_SIZE);
        buffer.order(ByteOrder.LITTLE_ENDIAN);

        buffer.put((byte) (version & 0xFF));
        buffer.put((byte) (messageType & 0xFF));
        buffer.put((byte) (commandType & 0xFF));
        buffer.put((byte) (flags & 0xFF));
        buffer.put((byte) (ttl & 0xFF));

        buffer.putInt((int) (sequence & 0xFFFFFFFFL));
        buffer.putInt((int) (timestamp & 0xFFFFFFFFL));

        buffer.putLong(deviceSerial);
        buffer.putLong(userId);
        buffer.putLong(destinationId);

        buffer.putShort(temperatureX100);
        buffer.putShort((short) (pulseBpm & 0xFFFF));
        buffer.put((byte) (pressureSys & 0xFF));
        buffer.put((byte) (pressureDia & 0xFF));

        buffer.putInt(latitudeE7);
        buffer.putInt(longitudeE7);
        buffer.putShort((short) (headingCdeg & 0xFFFF));
        buffer.put((byte) (positionQuality & 0xFF));

        return buffer.array();
    }

    public static LMashPayload createCommand(
            long sequence,
            long timestamp,
            long deviceSerial,
            long userId,
            long destinationId,
            int commandType
    ) {
        LMashPayload payload = new LMashPayload();
        payload.version = 1;
        payload.messageType = MSG_COMMAND;
        payload.commandType = commandType;
        payload.flags = 0;
        payload.ttl = 4;
        payload.sequence = sequence;
        payload.timestamp = timestamp;
        payload.deviceSerial = deviceSerial;
        payload.userId = userId;
        payload.destinationId = destinationId;
        return payload;
    }

    public double getTemperatureCelsius() {
        return temperatureX100 / 100.0;
    }

    public double getLatitude() {
        return latitudeE7 / 1e7;
    }

    public double getLongitude() {
        return longitudeE7 / 1e7;
    }

    public double getHeadingDegrees() {
        return headingCdeg / 100.0;
    }

    public String getPressureString() {
        return pressureSys + " / " + pressureDia;
    }

    public boolean isTelemetry() {
        return messageType == MSG_TELEMETRY;
    }

    public boolean isCommand() {
        return messageType == MSG_COMMAND;
    }

    public String getPositionQualityText() {
        switch (positionQuality) {
            case 3:
                return "Хорошее";
            case 2:
                return "Ограниченное";
            case 1:
                return "Низкое";
            case 0:
                return "Недоступно";
            default:
                return "Неизвестно (" + positionQuality + ")";
        }
    }

    public int getVersion() { return version; }
    public void setVersion(int version) { this.version = version; }

    public int getMessageType() { return messageType; }
    public void setMessageType(int messageType) { this.messageType = messageType; }

    public int getCommandType() { return commandType; }
    public void setCommandType(int commandType) { this.commandType = commandType; }

    public int getFlags() { return flags; }
    public void setFlags(int flags) { this.flags = flags; }

    public int getTtl() { return ttl; }
    public void setTtl(int ttl) { this.ttl = ttl; }

    public long getSequence() { return sequence; }
    public void setSequence(long sequence) { this.sequence = sequence; }

    public long getTimestamp() { return timestamp; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }

    public long getDeviceSerial() { return deviceSerial; }
    public void setDeviceSerial(long deviceSerial) { this.deviceSerial = deviceSerial; }

    public long getUserId() { return userId; }
    public void setUserId(long userId) { this.userId = userId; }

    public long getDestinationId() { return destinationId; }
    public void setDestinationId(long destinationId) { this.destinationId = destinationId; }

    public short getTemperatureX100() { return temperatureX100; }
    public void setTemperatureX100(short temperatureX100) { this.temperatureX100 = temperatureX100; }

    public int getPulseBpm() { return pulseBpm; }
    public void setPulseBpm(int pulseBpm) { this.pulseBpm = pulseBpm; }

    public int getPressureSys() { return pressureSys; }
    public void setPressureSys(int pressureSys) { this.pressureSys = pressureSys; }

    public int getPressureDia() { return pressureDia; }
    public void setPressureDia(int pressureDia) { this.pressureDia = pressureDia; }

    public int getLatitudeE7() { return latitudeE7; }
    public void setLatitudeE7(int latitudeE7) { this.latitudeE7 = latitudeE7; }

    public int getLongitudeE7() { return longitudeE7; }
    public void setLongitudeE7(int longitudeE7) { this.longitudeE7 = longitudeE7; }

    public int getHeadingCdeg() { return headingCdeg; }
    public void setHeadingCdeg(int headingCdeg) { this.headingCdeg = headingCdeg; }

    public int getPositionQuality() { return positionQuality; }
    public void setPositionQuality(int positionQuality) { this.positionQuality = positionQuality; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        LMashPayload that = (LMashPayload) o;
        return version == that.version &&
                messageType == that.messageType &&
                commandType == that.commandType &&
                flags == that.flags &&
                ttl == that.ttl &&
                sequence == that.sequence &&
                timestamp == that.timestamp &&
                deviceSerial == that.deviceSerial &&
                userId == that.userId &&
                destinationId == that.destinationId &&
                temperatureX100 == that.temperatureX100 &&
                pulseBpm == that.pulseBpm &&
                pressureSys == that.pressureSys &&
                pressureDia == that.pressureDia &&
                latitudeE7 == that.latitudeE7 &&
                longitudeE7 == that.longitudeE7 &&
                headingCdeg == that.headingCdeg &&
                positionQuality == that.positionQuality;
    }

    @Override
    public int hashCode() {
        return Objects.hash(version, messageType, commandType, flags, ttl, sequence,
                timestamp, deviceSerial, userId, destinationId, temperatureX100, pulseBpm,
                pressureSys, pressureDia, latitudeE7, longitudeE7, headingCdeg, positionQuality);
    }
}