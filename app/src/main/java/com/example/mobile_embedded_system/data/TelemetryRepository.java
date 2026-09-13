package com.example.mobile_embedded_system.data;

import android.app.Application;
import androidx.lifecycle.LiveData;

import com.example.mobile_embedded_system.data.local.AppDatabase;
import com.example.mobile_embedded_system.data.local.TelemetryDao;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Репозиторий слоя данных телеметрии (ТЗ §4.2, Архитектура MVVM).
 */
public class TelemetryRepository {

    private final TelemetryDao telemetryDao;
    private final ExecutorService executorService;

    public TelemetryRepository(Application application) {
        AppDatabase db = AppDatabase.getInstance(application);
        this.telemetryDao = db.telemetryDao();
        this.executorService = Executors.newSingleThreadExecutor();
    }

    public TelemetryRepository(TelemetryDao telemetryDao, ExecutorService executorService) {
        this.telemetryDao = telemetryDao;
        this.executorService = executorService;
    }

    public void insert(TelemetryEntity entity) {
        executorService.execute(() -> telemetryDao.insert(entity));
    }

    public LiveData<TelemetryEntity> getLatestTelemetryForUser(long userId) {
        return telemetryDao.getLatestTelemetryForUser(userId);
    }

    public LiveData<List<TelemetryEntity>> getHistoryForUser(long userId, long sinceTimestamp) {
        return telemetryDao.getHistoryForUser(userId, sinceTimestamp);
    }

    public void pruneOlderThan(long cutoffMs) {
        // Фоновое выполнение, чтобы не блокировать UI-поток
        new Thread(() -> {
            try {
                telemetryDao.deleteOlderThan(cutoffMs);
            } catch (Exception ignored) {
            }
        }).start();
    }
}