package com.example.mobile_embedded_system.data;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.ui.TelemetryViewModel;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Генератор тестового mesh-потока телеметрии для отладки тактической карты (ТЗ §14).
 */
public class MockTelemetryGenerator {

    private final TelemetryViewModel viewModel;
    private ScheduledExecutorService executor;
    private long sequence = 100L;
    private double currentLat = 55.753912;
    private double currentLon = 37.620811;
    private double heading = 45.0;

    public MockTelemetryGenerator(TelemetryViewModel viewModel) {
        this.viewModel = viewModel;
    }

    /**
     * Запуск периодической генерации пакетов с интервалом 2 секунды.
     */
    public synchronized void start() {
        if (executor != null && !executor.isShutdown()) {
            return;
        }

        executor = Executors.newSingleThreadScheduledExecutor();
        executor.scheduleAtFixedRate(this::generateStep, 1, 2, TimeUnit.SECONDS);
    }

    /**
     * Остановка фонового генератора.
     */
    public synchronized void stop() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    private void generateStep() {
        sequence++;

        // Шаг перемещения бойца на северо-восток
        currentLat += 0.00015;
        currentLon += 0.00020;
        heading = (heading + 5.0) % 360.0;

        // Небольшие колебания пульса в пределах нормы (72..78 BPM)
        int pulse = 72 + (int) (Math.random() * 7);
        double temp = 36.5 + (Math.random() * 0.3);

        TelemetryEntity entity = new TelemetryEntity();
        entity.deviceSerial = 99881122L;
        entity.sequence = sequence;
        entity.userId = 1001L;
        entity.destinationId = 0L;
        entity.timestamp = System.currentTimeMillis() / 1000L;
        entity.latitude = currentLat;
        entity.longitude = currentLon;
        entity.headingDegrees = heading;
        entity.pulseBpm = pulse;
        entity.temperatureCelsius = temp;
        entity.pressureSys = 120;
        entity.pressureDia = 80;
        entity.positionQuality = 3;
        entity.receivedAtMs = System.currentTimeMillis();

        viewModel.insertTelemetry(entity);
    }
}