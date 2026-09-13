package com.example.mobile_embedded_system.transport;

import android.util.Log;

import com.example.mobile_embedded_system.data.TelemetryRepository;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.data.model.LMashPayload;
import com.example.mobile_embedded_system.domain.network.MqttTopicBuilder;
import com.example.mobile_embedded_system.domain.TacticalCommand;

import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallbackExtended;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

/**
 * Сетевой транспорт телеметрии на базе MQTT для приёма mesh-пакетов (ТЗ §4.1, §14, §19).
 */
public class MqttTransportManager {

    private static final String TAG = "MqttTransport";

    // Настройки сети (ТЗ §1.40) - временно хардкод для MVP P0
    private String networkRoot = "mesh-a";
    private String hierarchyPath = "7F10/21A0";

    private final TelemetryRepository repository;
    private MqttClient mqttClient;
    private boolean isConnecting = false;

    public interface ConnectionCallback {
        void onConnected();
        void onDisconnected(String reason);
        void onError(String error);
    }

    public MqttTransportManager(TelemetryRepository repository) {
        this.repository = repository;
    }

    public void setNetworkConfig(String root, String path) {
        this.networkRoot = root;
        this.hierarchyPath = path;
    }

    /**
     * Асинхронное подключение к брокеру телеметрии.
     */
    public synchronized void connect(String brokerUrl, String clientId, ConnectionCallback callback) {
        if (mqttClient != null && mqttClient.isConnected()) {
            if (callback != null) callback.onConnected();
            return;
        }

        if (isConnecting) {
            return;
        }

        isConnecting = true;

        new Thread(() -> {
            try {
                mqttClient = new MqttClient(brokerUrl, clientId, new MemoryPersistence());
                MqttConnectOptions options = new MqttConnectOptions();
                options.setAutomaticReconnect(true);
                options.setCleanSession(true);
                options.setConnectionTimeout(5);
                options.setKeepAliveInterval(10);

                mqttClient.setCallback(new MqttCallbackExtended() {
                    @Override
                    public void connectComplete(boolean reconnect, String serverURI) {
                        Log.i(TAG, "MQTT подключен к: " + serverURI + " (reconnect=" + reconnect + ")");
                        subscribeToTelemetry();
                        if (callback != null) callback.onConnected();
                    }

                    @Override
                    public void connectionLost(Throwable cause) {
                        Log.w(TAG, "MQTT связь потеряна: " + (cause != null ? cause.getMessage() : "unknown"));
                        if (callback != null) callback.onDisconnected(cause != null ? cause.getMessage() : "Соединение разорвано");
                    }

                    @Override
                    public void messageArrived(String topic, MqttMessage message) {
                        processIncomingMessage(topic, message.getPayload());
                    }

                    @Override
                    public void deliveryComplete(IMqttDeliveryToken token) {
                    }
                });

                mqttClient.connect(options);
                isConnecting = false;

            } catch (MqttException e) {
                isConnecting = false;
                Log.e(TAG, "Ошибка подключения к брокеру MQTT: " + e.getMessage(), e);
                if (callback != null) callback.onError("Сбой MQTT: " + e.getReasonCode());
            }
        }).start();
    }

    private void subscribeToTelemetry() {
        try {
            if (mqttClient != null && mqttClient.isConnected()) {
                String topic = MqttTopicBuilder.buildSubtreeSubscriptionTopic(networkRoot, hierarchyPath);
                mqttClient.subscribe(topic, 1);
                Log.i(TAG, "Подписка оформлена на: " + topic);
            }
        } catch (MqttException e) {
            Log.e(TAG, "Ошибка подписки на топик телеметрии", e);
        }
    }

    /**
     * Обработка входящего бинарного пакета (P0 исправление 54-байтового формата).
     */
    public void processIncomingMessage(String topic, byte[] payloadBytes) {
        if (payloadBytes == null || payloadBytes.length < LMashPayload.PAYLOAD_SIZE) {
            Log.w(TAG, "Отброшен некорректный пакет. Длина: " + (payloadBytes != null ? payloadBytes.length : 0));
            return;
        }

        try {
            LMashPayload payload = LMashPayload.fromBytes(payloadBytes);
            if (!payload.isTelemetry()) {
                Log.d(TAG, "Пропущен пакет не-телеметрии (type=" + payload.getMessageType() + ")");
                return;
            }
            
            TelemetryEntity entity = convertToEntity(payload);
            repository.insert(entity);
            Log.d(TAG, "Телеметрия сохранена от бойца [" + entity.userId + "], seq=" + entity.sequence);
        } catch (IllegalArgumentException e) {
            Log.e(TAG, "Ошибка декодирования бинарного пакета телеметрии", e);
        }
    }

    private TelemetryEntity convertToEntity(LMashPayload payload) {
        TelemetryEntity entity = new TelemetryEntity();
        entity.deviceSerial = payload.getDeviceSerial();
        entity.sequence = payload.getSequence();
        entity.userId = payload.getUserId();
        entity.destinationId = payload.getDestinationId();
        entity.timestamp = payload.getTimestamp();
        entity.latitude = payload.getLatitude();
        entity.longitude = payload.getLongitude();
        entity.headingDegrees = payload.getHeadingDegrees();
        entity.pulseBpm = payload.getPulseBpm();
        entity.temperatureCelsius = payload.getTemperatureCelsius();
        entity.pressureSys = payload.getPressureSys();
        entity.pressureDia = payload.getPressureDia();
        entity.positionQuality = payload.getPositionQuality();
        entity.receivedAtMs = System.currentTimeMillis();
        return entity;
    }

    public synchronized void disconnect() {
        if (mqttClient != null) {
            try {
                if (mqttClient.isConnected()) {
                    mqttClient.disconnect();
                }
                mqttClient.close();
            } catch (MqttException e) {
                Log.e(TAG, "Ошибка отключения MQTT", e);
            } finally {
                mqttClient = null;
                isConnecting = false;
            }
        }
    }

    public boolean isConnected() {
        return mqttClient != null && mqttClient.isConnected();
    }

    /**
     * Публикация командного пакета в бинарном виде LMashPayload (ТЗ §4.1, P0 исправление).
     */
    public boolean publishCommand(TacticalCommand command, long sourceId) {
        if (mqttClient == null || !mqttClient.isConnected()) {
            return false;
        }

        String topic = MqttTopicBuilder.buildCommandPublishTopic(
                networkRoot, hierarchyPath, command.getTargetUserId(), sourceId
        );

        try {
            long currentTimestamp = System.currentTimeMillis() / 1000L;
            
            LMashPayload payload = LMashPayload.createCommand(
                    currentTimestamp, // sequence (simplified for MVP)
                    currentTimestamp, // timestamp
                    0L, // deviceSerial (omitted for phone)
                    sourceId,
                    command.getTargetUserId(),
                    LMashPayload.CMD_HOLD // Example command type
            );
            
            payload.setLatitudeE7((int) (command.getLatitude() * 1e7));
            payload.setLongitudeE7((int) (command.getLongitude() * 1e7));

            MqttMessage message = new MqttMessage(payload.toBytes());
            message.setQos(1); // Гарантированная доставка приказа
            message.setRetained(false);

            mqttClient.publish(topic, message);
            Log.i(TAG, "Бинарная команда отправлена в топик: " + topic);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Ошибка отправки команды", e);
            return false;
        }
    }
}
