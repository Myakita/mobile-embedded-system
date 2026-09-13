package com.example.mobile_embedded_system.data;

import android.os.Handler;
import android.os.Looper;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.domain.TacticalNavigationCalculator;
import com.example.mobile_embedded_system.ui.TelemetryViewModel;

/**
 * Автономный генератор с динамическим наведением группы на назначенные ориентиры (ТЗ §4.2, §6.10).
 */
public class MockTelemetryGenerator {

    private static final long STEP_INTERVAL_MS = 1000L;

    private final TelemetryViewModel viewModel;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean isRunning = false;

    private double lat1001 = 55.753912, lon1001 = 37.620811, head1001 = 45.0;
    private double lat1002 = 55.753300, lon1002 = 37.621500, head1002 = 30.0;
    private double lat1003 = 55.754400, lon1003 = 37.619800, head1003 = 90.0;

    private Double targetLat1001 = null, targetLon1001 = null;
    private Double targetLat1002 = null, targetLon1002 = null;
    private Double targetLat1003 = null, targetLon1003 = null;

    private long seq1001 = 100, seq1002 = 200, seq1003 = 300;

    public MockTelemetryGenerator(TelemetryViewModel viewModel) {
        this.viewModel = viewModel;
    }

    public synchronized void setUnitTarget(long userId, double targetLat, double targetLon) {
        if (userId == 1001L) {
            targetLat1001 = targetLat;
            targetLon1001 = targetLon;
        } else if (userId == 1002L) {
            targetLat1002 = targetLat;
            targetLon1002 = targetLon;
        } else if (userId == 1003L) {
            targetLat1003 = targetLat;
            targetLon1003 = targetLon;
        }
    }

    public synchronized void clearUnitTarget(long userId) {
        if (userId == 1001L) {
            targetLat1001 = null;
            targetLon1001 = null;
        } else if (userId == 1002L) {
            targetLat1002 = null;
            targetLon1002 = null;
        } else if (userId == 1003L) {
            targetLat1003 = null;
            targetLon1003 = null;
        }
    }

    private final Runnable stepRunnable = new Runnable() {
        @Override
        public void run() {
            if (!isRunning) return;
            generateSquadStep();
            handler.postDelayed(this, STEP_INTERVAL_MS);
        }
    };

    public void start() {
        if (!isRunning) {
            isRunning = true;
            handler.post(stepRunnable);
        }
    }

    public void stop() {
        isRunning = false;
        handler.removeCallbacks(stepRunnable);
    }

    private synchronized void generateSquadStep() {
        long now = System.currentTimeMillis();
        long nowSec = now / 1000L;

        // 1. Командир [1001]
        seq1001++;
        double[] step1001 = calculateNextStep(lat1001, lon1001, head1001, targetLat1001, targetLon1001, 0.00010, 0.00015, 5.0);
        lat1001 = step1001[0];
        lon1001 = step1001[1];
        head1001 = step1001[2];

        viewModel.insertTelemetry(createEntity(
                99881100L, seq1001, 1001L, nowSec, lat1001, lon1001, head1001,
                72 + (int) (Math.random() * 4), 36.6, 120, 80, now
        ));

        // 2. Стрелок [1002] — эмуляция тахикардии для проверки тревог
        seq1002++;
        double[] step1002 = calculateNextStep(lat1002, lon1002, head1002, targetLat1002, targetLon1002, 0.00018, 0.00012, 8.0);
        lat1002 = step1002[0];
        lon1002 = step1002[1];
        head1002 = step1002[2];

        int pulse1002 = 126 + (int) (Math.random() * 6);
        double temp1002 = 38.6 + (Math.random() * 0.2);

        viewModel.insertTelemetry(createEntity(
                99881122L, seq1002, 1002L, nowSec, lat1002, lon1002, head1002,
                pulse1002, temp1002, 145, 95, now
        ));

        // 3. Санинструктор [1003]
        seq1003++;
        double[] step1003 = calculateNextStep(lat1003, lon1003, head1003, targetLat1003, targetLon1003, -0.00012, 0.00016, -6.0);
        lat1003 = step1003[0];
        lon1003 = step1003[1];
        head1003 = step1003[2];

        viewModel.insertTelemetry(createEntity(
                99881144L, seq1003, 1003L, nowSec, lat1003, lon1003, head1003,
                68 + (int) (Math.random() * 5), 36.5, 118, 78, now
        ));
    }

    private double[] calculateNextStep(double currentLat, double currentLon, double currentHeading,
                                       Double targetLat, Double targetLon,
                                       double defaultDLat, double defaultDLon, double defaultDHead) {
        if (targetLat != null && targetLon != null) {
            double distance = TacticalNavigationCalculator.calculateDistanceMeters(currentLat, currentLon, targetLat, targetLon);
            if (distance > 8.0) {
                double bearing = TacticalNavigationCalculator.calculateBearingDegrees(currentLat, currentLon, targetLat, targetLon);
                double stepMeters = Math.min(distance, 12.0); // шаг ~12 метров

                double dLat = (stepMeters * Math.cos(Math.toRadians(bearing))) / 111195.0;
                double dLon = (stepMeters * Math.sin(Math.toRadians(bearing))) / (111195.0 * Math.cos(Math.toRadians(currentLat)));

                return new double[]{currentLat + dLat, currentLon + dLon, bearing};
            } else {
                // Цель достигнута: остановка на месте
                return new double[]{currentLat, currentLon, currentHeading};
            }
        } else {
            // Штатное патрулирование
            return new double[]{
                    currentLat + defaultDLat,
                    currentLon + defaultDLon,
                    (currentHeading + defaultDHead + 360.0) % 360.0
            };
        }
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