package com.example.mobile_embedded_system.data;

import android.util.Log;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.ui.TelemetryViewModel;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * Генератор тестового mesh-потока группы бойцов тактического звена (ТЗ §13, §14).
 * Имитирует одновременную передачу телеметрии от 3 абонентов:
 * - 1001: Командир (норма)
 * - 1002: Стрелок (нагрузка / предупреждение)
 * - 1003: Санинструктор (норма)
 */
public class MockTelemetryGenerator {

    private static final String TAG = "MockTelemetry";

    private final TelemetryViewModel viewModel;
    private ScheduledExecutorService executor;
    private ScheduledFuture<?> periodicTask;

    // Состояние абонента 1001 (Командир)
    private static long seq1001 = 100L;
    private static double lat1001 = 55.753912;
    private static double lon1001 = 37.620811;
    private static double head1001 = 45.0;

    // Состояние абонента 1002 (Стрелок)
    private static long seq1002 = 200L;
    private static double lat1002 = 55.753200;
    private static double lon1002 = 37.622500;
    private static double head1002 = 60.0;

    // Состояние абонента 1003 (Санинструктор)
    private static long seq1003 = 300L;
    private static double lat1003 = 55.752500;
    private static double lon1003 = 37.619000;
    private static double head1003 = 30.0;

    public MockTelemetryGenerator(TelemetryViewModel viewModel) {
        this.viewModel = viewModel;
    }

    public synchronized void start() {
        if (executor != null && !executor.isShutdown()) {
            return;
        }

        executor = Executors.newSingleThreadScheduledExecutor();
        periodicTask = executor.scheduleWithFixedDelay(() -> {
            try {
                generateSquadStep();
            } catch (Throwable t) {
                Log.e(TAG, "Ошибка генерации телеметрии отряда", t);
            }
        }, 1, 2, TimeUnit.SECONDS);
    }

    public synchronized void stop() {
        if (periodicTask != null) {
            periodicTask.cancel(true);
            periodicTask = null;
        }
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
    }

    private void generateSquadStep() {
        long now = System.currentTimeMillis();
        long nowSec = now / 1000L;

        // 1. Пакет Командира [1001] — норма
        seq1001++;
        lat1001 += 0.00014;
        lon1001 += 0.00018;
        head1001 = (head1001 + 5.0) % 360.0;
        int pulse1001 = 72 + (int) (Math.random() * 6);
        double temp1001 = 36.6 + (Math.random() * 0.2);

        viewModel.insertTelemetry(createEntity(
                99881121L, seq1001, 1001L, nowSec, lat1001, lon1001, head1001,
                pulse1001, temp1001, 120, 80, now
        ));

        // 2. Пакет Стрелка [1002] — динамический переход в CRITICAL (126..132 BPM)
        seq1002++;
        lat1002 += 0.00018;
        lon1002 += 0.00012;
        head1002 = (head1002 + 8.0) % 360.0;
        int pulse1002 = 126 + (int) (Math.random() * 6);
        double temp1002 = 38.6 + (Math.random() * 0.2);

        viewModel.insertTelemetry(createEntity(
                99881122L, seq1002, 1002L, nowSec, lat1002, lon1002, head1002,
                pulse1002, temp1002, 145, 95, now
        ));

        // 3. Пакет Санинструктора [1003] — норма
        seq1003++;
        lat1003 += 0.00010;
        lon1003 += 0.00022;
        head1003 = (head1003 + 3.0) % 360.0;
        int pulse1003 = 68 + (int) (Math.random() * 5);
        double temp1003 = 36.5 + (Math.random() * 0.2);

        viewModel.insertTelemetry(createEntity(
                99881123L, seq1003, 1003L, nowSec, lat1003, lon1003, head1003,
                pulse1003, temp1003, 118, 76, now
        ));
    }

    private TelemetryEntity createEntity(long serial, long seq, long userId, long timestamp,
                                         double lat, double lon, double heading,
                                         int pulse, double temp, int pSys, int pDia, long receivedAt) {
        TelemetryEntity entity = new TelemetryEntity();
        entity.deviceSerial = serial;
        entity.sequence = seq;
        entity.userId = userId;
        entity.destinationId = 0L;
        entity.timestamp = timestamp;
        entity.latitude = lat;
        entity.longitude = lon;
        entity.headingDegrees = heading;
        entity.pulseBpm = pulse;
        entity.temperatureCelsius = temp;
        entity.pressureSys = pSys;
        entity.pressureDia = pDia;
        entity.positionQuality = 3;
        entity.receivedAtMs = receivedAt;
        return entity;
    }
}