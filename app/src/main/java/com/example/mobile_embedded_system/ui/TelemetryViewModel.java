package com.example.mobile_embedded_system.ui;

import android.app.Application;
import androidx.annotation.NonNull;
import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.LiveData;

import com.example.mobile_embedded_system.data.TelemetryRepository;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import java.util.List;

/**
 * ViewModel для связи данных телеметрии с экраном тактической обстановки (ТЗ §4.2).
 */
public class TelemetryViewModel extends AndroidViewModel {

    private final TelemetryRepository repository;

    public TelemetryViewModel(@NonNull Application application) {
        super(application);
        this.repository = new TelemetryRepository(application);
    }

    public LiveData<TelemetryEntity> getLatestTelemetry(long userId) {
        return repository.getLatestTelemetryForUser(userId);
    }

    public LiveData<List<TelemetryEntity>> getHistory(long userId, long sinceTimestamp) {
        return repository.getHistoryForUser(userId, sinceTimestamp);
    }

    public void insertTelemetry(TelemetryEntity entity) {
        repository.insert(entity);
    }
}