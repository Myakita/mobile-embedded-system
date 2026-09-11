package com.example.mobile_embedded_system.data.local;

import androidx.lifecycle.LiveData;
import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;

import java.util.List;

@Dao
public interface TelemetryDao {

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insert(TelemetryEntity record);

    @Query("SELECT * FROM telemetry_records WHERE user_id = :userId ORDER BY timestamp DESC LIMIT 1")
    LiveData<TelemetryEntity> getLatestTelemetryForUser(long userId);

    @Query("SELECT * FROM telemetry_records WHERE user_id = :userId AND timestamp >= :fromTimestamp ORDER BY timestamp ASC")
    LiveData<List<TelemetryEntity>> getHistoryForUser(long userId, long fromTimestamp);

    @Query("DELETE FROM telemetry_records WHERE timestamp < :cutoffTimestamp")
    int deleteOlderThan(long cutoffTimestamp);
}