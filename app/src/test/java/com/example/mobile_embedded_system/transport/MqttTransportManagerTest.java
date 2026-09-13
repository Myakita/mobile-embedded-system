package com.example.mobile_embedded_system.transport;

import static org.junit.Assert.assertEquals;

import androidx.annotation.NonNull;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

import com.example.mobile_embedded_system.data.TelemetryRepository;
import com.example.mobile_embedded_system.data.local.TelemetryDao;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.data.model.LMashPayload;

import org.junit.Before;
import org.junit.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.AbstractExecutorService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Тестирование конвейера приёма бинарных пакетов из MQTT в Room (ТЗ §5.1, §14, §19).
 */
public class MqttTransportManagerTest {

    private MqttTransportManager transportManager;
    private MockDao mockDao;

    @Before
    public void setUp() {
        mockDao = new MockDao();

        // Синхронный прямой ExecutorService для мгновенного выполнения без race conditions в тестах
        ExecutorService directExecutor = new AbstractExecutorService() {
            private boolean isShutdown = false;

            @Override
            public void shutdown() {
                isShutdown = true;
            }

            @NonNull
            @Override
            public List<Runnable> shutdownNow() {
                isShutdown = true;
                return Collections.emptyList();
            }

            @Override
            public boolean isShutdown() {
                return isShutdown;
            }

            @Override
            public boolean isTerminated() {
                return isShutdown;
            }

            @Override
            public boolean awaitTermination(long timeout, @NonNull TimeUnit unit) {
                return true;
            }

            @Override
            public void execute(@NonNull Runnable command) {
                command.run();
            }
        };

        TelemetryRepository repository = new TelemetryRepository(mockDao, directExecutor);
        transportManager = new MqttTransportManager(repository);
    }

    @Test
    public void testProcessIncomingValidBinaryPacketInsertsToRepository() {
        LMashPayload payload = new LMashPayload();
        payload.setMessageType(LMashPayload.MSG_TELEMETRY);
        payload.setDeviceSerial(778899L);
        payload.setSequence(42L);
        payload.setUserId(1002L);
        payload.setDestinationId(0L);
        payload.setTimestamp(1700000000L);
        payload.setLatitudeE7((int)(55.753912 * 1e7));
        payload.setLongitudeE7((int)(37.620811 * 1e7));
        payload.setPulseBpm(98);
        payload.setTemperatureX100((short)(37.1 * 100));

        byte[] binaryPacket = payload.toBytes();
        assertEquals(LMashPayload.PAYLOAD_SIZE, binaryPacket.length);

        transportManager.processIncomingMessage("unit/telemetry/1002", binaryPacket);

        assertEquals(1, mockDao.inserted.size());
        TelemetryEntity saved = mockDao.inserted.get(0);
        assertEquals(778899L, saved.deviceSerial);
        assertEquals(42L, saved.sequence);
        assertEquals(1002L, saved.userId);
        assertEquals(55.753912, saved.latitude, 0.00001);
        assertEquals(37.620811, saved.longitude, 0.00001);
        assertEquals(98, saved.pulseBpm);
        assertEquals(37.1, saved.temperatureCelsius, 0.01);
    }

    @Test
    public void testCorruptedPayloadSizeIsDropped() {
        byte[] corruptedShortPayload = new byte[20];
        transportManager.processIncomingMessage("unit/telemetry/1002", corruptedShortPayload);

        assertEquals(0, mockDao.inserted.size());
    }

    private static class MockDao implements TelemetryDao {
        final List<TelemetryEntity> inserted = new ArrayList<>();

        @Override
        public long insert(TelemetryEntity entity) {
            inserted.add(entity);
            return 1L;
        }

        @Override
        public LiveData<TelemetryEntity> getLatestTelemetryForUser(long userId) {
            return new MutableLiveData<>();
        }

        @Override
        public LiveData<List<TelemetryEntity>> getHistoryForUser(long userId, long fromTimestamp) {
            return new MutableLiveData<>();
        }

        @Override
        public int deleteOlderThan(long timestampThreshold) {
            return 0;
        }
    }
}
