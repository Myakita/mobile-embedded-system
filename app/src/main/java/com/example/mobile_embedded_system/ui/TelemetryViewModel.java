package com.example.mobile_embedded_system.ui;

import android.app.Application;

import androidx.annotation.NonNull;
import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

import com.example.mobile_embedded_system.data.MockTelemetryGenerator;
import com.example.mobile_embedded_system.data.TelemetryRepository;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.transport.MqttTransportManager;

import java.util.List;

/**
 * MVVM-фасад для доступа к телеметрии и управления сетевым транспортом (ТЗ §4.2).
 */
public class TelemetryViewModel extends AndroidViewModel {

    public enum ConnectionState {
        DISCONNECTED,
        CONNECTING,
        CONNECTED,
        MOCK_MODE
    }

    private final TelemetryRepository repository;
    private final MockTelemetryGenerator mockGenerator;
    private final MqttTransportManager mqttTransport;

    private final MutableLiveData<ConnectionState> connectionState = new MutableLiveData<>(ConnectionState.DISCONNECTED);

    public TelemetryViewModel(@NonNull Application application) {
        super(application);
        // Предполагается, что конструктор репозитория принимает Application или Context
        this.repository = new TelemetryRepository(application);

        this.mockGenerator = new MockTelemetryGenerator(this);
        this.mqttTransport = new MqttTransportManager(repository);

        // По умолчанию стартуем в режиме имитатора (автономная работа)
        startMockMode();
    }

    public void insertTelemetry(TelemetryEntity entity) {
        repository.insert(entity);
    }

    public LiveData<TelemetryEntity> getLatestTelemetry(long userId) {
        return repository.getLatestTelemetryForUser(userId);
    }

    public LiveData<List<TelemetryEntity>> getHistory(long userId, long since) {
        return repository.getHistoryForUser(userId, since);
    }

    public LiveData<ConnectionState> getConnectionState() {
        return connectionState;
    }

    public void startMockMode() {
        mqttTransport.disconnect();
        mockGenerator.start();
        connectionState.postValue(ConnectionState.MOCK_MODE);
    }

    public void startMqttMode(String brokerUrl, String clientId) {
        mockGenerator.stop();
        connectionState.postValue(ConnectionState.CONNECTING);

        mqttTransport.connect(brokerUrl, clientId, new MqttTransportManager.ConnectionCallback() {
            @Override
            public void onConnected() {
                connectionState.postValue(ConnectionState.CONNECTED);
            }

            @Override
            public void onDisconnected(String reason) {
                connectionState.postValue(ConnectionState.DISCONNECTED);
            }

            @Override
            public void onError(String error) {
                connectionState.postValue(ConnectionState.DISCONNECTED);
            }
        });
    }

    @Override
    protected void onCleared() {
        super.onCleared();
        mockGenerator.stop();
        mqttTransport.disconnect();
    }

    public void setUnitTarget(long userId, double targetLat, double targetLon) {
        mockGenerator.setUnitTarget(userId, targetLat, targetLon);
    }

    public void clearUnitTarget(long userId) {
        mockGenerator.clearUnitTarget(userId);
    }
}
