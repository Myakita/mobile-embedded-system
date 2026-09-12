package com.example.mobile_embedded_system.transport;

import android.util.Log;

import com.example.mobile_embedded_system.data.TelemetryRepository;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.protocol.LMashPayload;

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
    private static final String DEFAULT_SUB_TOPIC = "unit/telemetry/+";

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

    /**
     * Асинхронное подключение к брокеру телеметрии.
     * @param brokerUrl URL шлюза, например: "tcp://10.0.2.2:1883" или "tcp://192.168.1.100:1883"
     * @param clientId Уникальный идентификатор терминала
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
                        // Приём телеметрии не требует подтверждения доставки публикации
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
                mqttClient.subscribe(DEFAULT_SUB_TOPIC, 1);
                Log.i(TAG, "Подписка оформлена на: " + DEFAULT_SUB_TOPIC);
            }
        } catch (MqttException e) {
            Log.e(TAG, "Ошибка подписки на топик телеметрии", e);
        }
    }

    /**
     * Обработка входящего бинарного пакета и передача в базу Room.
     */
    public void processIncomingMessage(String topic, byte[] payloadBytes) {
        if (payloadBytes == null || payloadBytes.length != LMashPayload.PAYLOAD_SIZE_BYTES) {
            Log.w(TAG, "Отброшен некорректный пакет. Длина: " + (payloadBytes != null ? payloadBytes.length : 0));
            return;
        }

        try {
            LMashPayload payload = LMashPayload.fromByteArray(payloadBytes);
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
}