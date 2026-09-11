package com.example.mobile_embedded_system.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import androidx.arch.core.executor.testing.InstantTaskExecutorRule;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

import com.example.mobile_embedded_system.data.local.TelemetryDao;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Модульный тест репозитория телеметрии (ТЗ §4.2, §5.1).
 */
public class TelemetryRepositoryTest {

    // Принудительно выполняет задачи Architecture Components синхронно в тестовом потоке
    @Rule
    public InstantTaskExecutorRule instantTaskExecutorRule = new InstantTaskExecutorRule();

    private TelemetryRepository repository;
    private MockTelemetryDao mockDao;

    @Before
    public void setUp() {
        mockDao = new MockTelemetryDao();
        ExecutorService directExecutor = Executors.newSingleThreadExecutor();
        repository = new TelemetryRepository(mockDao, directExecutor);
    }

    @Test
    public void testInsertDelegatesToDao() throws InterruptedException {
        TelemetryEntity entity = new TelemetryEntity();
        entity.deviceSerial = 998877L;
        entity.sequence = 1L;
        entity.userId = 1001L;

        repository.insert(entity);
        Thread.sleep(100);

        assertEquals(1, mockDao.insertedEntities.size());
        assertEquals(998877L, mockDao.insertedEntities.get(0).deviceSerial);
    }

    @Test
    public void testGetLatestTelemetryReturnsLiveData() {
        LiveData<TelemetryEntity> liveData = repository.getLatestTelemetryForUser(1001L);
        assertNotNull(liveData);
        assertNotNull(liveData.getValue());
        assertEquals(1001L, liveData.getValue().userId);
    }

    private static class MockTelemetryDao implements TelemetryDao {
        final List<TelemetryEntity> insertedEntities = new java.util.ArrayList<>();

        @Override
        public long insert(TelemetryEntity entity) {
            insertedEntities.add(entity);
            return 1L;
        }

        @Override
        public LiveData<TelemetryEntity> getLatestTelemetryForUser(long userId) {
            MutableLiveData<TelemetryEntity> data = new MutableLiveData<>();
            TelemetryEntity entity = new TelemetryEntity();
            entity.userId = userId;
            data.setValue(entity);
            return data;
        }

        @Override
        public LiveData<List<TelemetryEntity>> getHistoryForUser(long userId, long sinceTimestamp) {
            MutableLiveData<List<TelemetryEntity>> data = new MutableLiveData<>();
            data.setValue(Collections.emptyList());
            return data;
        }

        @Override
        public int deleteOlderThan(long timestampThreshold) {
            return 0;
        }
    }
}