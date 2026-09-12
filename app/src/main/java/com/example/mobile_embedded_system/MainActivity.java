package com.example.mobile_embedded_system;

import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.lifecycle.ViewModelProvider;

import com.example.mobile_embedded_system.data.MockTelemetryGenerator;
import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.ui.TelemetryViewModel;

import org.maplibre.android.MapLibre;
import org.maplibre.android.annotations.Icon;
import org.maplibre.android.annotations.IconFactory;
import org.maplibre.android.annotations.Marker;
import org.maplibre.android.annotations.MarkerOptions;
import org.maplibre.android.annotations.Polyline;
import org.maplibre.android.annotations.PolylineOptions;
import org.maplibre.android.camera.CameraPosition;
import org.maplibre.android.camera.CameraUpdateFactory;
import org.maplibre.android.geometry.LatLng;
import org.maplibre.android.maps.MapView;
import org.maplibre.android.maps.MapLibreMap;
import org.maplibre.android.maps.OnMapReadyCallback;
import org.maplibre.android.maps.Style;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Экран тактической обстановки группы бойцов звена (ТЗ §4.2, §6.4, §6.7–§6.12, §13).
 */
public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private static final long[] SQUAD_IDS = {1001L, 1002L, 1003L};
    private static final String PREFS_NAME = "unit_monitor_prefs";
    private static final String KEY_THEME = "selected_theme";

    private static final int THEME_INSTRUMENT = 0;
    private static final int THEME_DAY = 1;
    private static final int THEME_BLACKOUT = 2;

    private MapView mapView;
    private MapLibreMap maplibreMap;
    private TelemetryViewModel viewModel;
    private MockTelemetryGenerator mockGenerator;

    // Многопользовательские структуры данных карты
    private final Map<Long, Marker> tacticalMarkers = new HashMap<>();
    private final Map<Long, Polyline> tacticalTracks = new HashMap<>();
    private final Map<Long, TelemetryEntity> squadLatestData = new HashMap<>();

    private long activeUserId = 1001L;

    private TextView textCoords;
    private TextView textCallsign;
    private TextView textPulse;
    private TextView textTemperature;
    private TextView textPressure;
    private View viewStatusIndicator;

    private TextView btnUnit1001;
    private TextView btnUnit1002;
    private TextView btnUnit1003;

    private int currentThemeMode;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        currentThemeMode = prefs.getInt(KEY_THEME, THEME_INSTRUMENT);

        if (currentThemeMode == THEME_BLACKOUT) {
            setTheme(R.style.Theme_UnitMonitor_Blackout);
        } else if (currentThemeMode == THEME_DAY) {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO);
            setTheme(R.style.Theme_UnitMonitor);
        } else {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES);
            setTheme(R.style.Theme_UnitMonitor);
        }

        MapLibre.getInstance(this);

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        WindowInsetsControllerCompat insetsController = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        insetsController.setAppearanceLightStatusBars(currentThemeMode == THEME_DAY);

        initViews(savedInstanceState);
        setupThemeButtons();
        setupSquadButtons();
        updateThemeButtonsUI(currentThemeMode);
        updateSquadButtonsUI();

        viewModel = new ViewModelProvider(this).get(TelemetryViewModel.class);
        mockGenerator = new MockTelemetryGenerator(viewModel);

        mapView.getMapAsync(this);
    }

    private void initViews(Bundle savedInstanceState) {
        textCoords = findViewById(R.id.textCoords);
        textCallsign = findViewById(R.id.textCallsign);
        textPulse = findViewById(R.id.textPulse);
        textTemperature = findViewById(R.id.textTemperature);
        textPressure = findViewById(R.id.textPressure);
        viewStatusIndicator = findViewById(R.id.viewStatusIndicator);

        btnUnit1001 = findViewById(R.id.btnUnit1001);
        btnUnit1002 = findViewById(R.id.btnUnit1002);
        btnUnit1003 = findViewById(R.id.btnUnit1003);

        // Центрирование камеры на активном бойце при клике на панель сведений
        findViewById(R.id.panelTelemetry).setOnClickListener(v -> snapCameraToActiveUnit());

        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);
    }

    private void setupSquadButtons() {
        btnUnit1001.setOnClickListener(v -> selectActiveUnit(1001L));
        btnUnit1002.setOnClickListener(v -> selectActiveUnit(1002L));
        btnUnit1003.setOnClickListener(v -> selectActiveUnit(1003L));
    }

    private void selectActiveUnit(long userId) {
        if (activeUserId == userId) {
            snapCameraToActiveUnit();
            return;
        }
        activeUserId = userId;
        updateSquadButtonsUI();

        TelemetryEntity entity = squadLatestData.get(activeUserId);
        if (entity != null) {
            updateDashboard(entity);
            snapCameraToActiveUnit();
        }
    }

    private void snapCameraToActiveUnit() {
        TelemetryEntity entity = squadLatestData.get(activeUserId);
        if (maplibreMap != null && entity != null) {
            maplibreMap.easeCamera(CameraUpdateFactory.newLatLng(new LatLng(entity.latitude, entity.longitude)), 500);
        }
    }

    private void updateSquadButtonsUI() {
        int inkColor = resolveThemeColor(R.attr.appInk);
        int surfaceColor = resolveThemeColor(R.attr.appSurface);
        int bgColor = resolveThemeColor(R.attr.appBg);

        applyButtonStyle(btnUnit1001, activeUserId == 1001L, inkColor, surfaceColor, bgColor, inkColor);
        applyButtonStyle(btnUnit1002, activeUserId == 1002L, inkColor, surfaceColor, bgColor, inkColor);
        applyButtonStyle(btnUnit1003, activeUserId == 1003L, inkColor, surfaceColor, bgColor, inkColor);
    }

    private void setupThemeButtons() {
        findViewById(R.id.btnThemeDay).setOnClickListener(v -> switchTheme(THEME_DAY));
        findViewById(R.id.btnThemeInstrument).setOnClickListener(v -> switchTheme(THEME_INSTRUMENT));
        findViewById(R.id.btnThemeBlackout).setOnClickListener(v -> switchTheme(THEME_BLACKOUT));
    }

    private void updateThemeButtonsUI(int activeMode) {
        int inkColor = resolveThemeColor(R.attr.appInk);
        int surfaceColor = resolveThemeColor(R.attr.appSurface);
        int bgColor = resolveThemeColor(R.attr.appBg);

        applyButtonStyle(findViewById(R.id.btnThemeDay), activeMode == THEME_DAY, inkColor, surfaceColor, bgColor, inkColor);
        applyButtonStyle(findViewById(R.id.btnThemeInstrument), activeMode == THEME_INSTRUMENT, inkColor, surfaceColor, bgColor, inkColor);
        applyButtonStyle(findViewById(R.id.btnThemeBlackout), activeMode == THEME_BLACKOUT, inkColor, surfaceColor, bgColor, inkColor);
    }

    private void applyButtonStyle(TextView btn, boolean isActive, int activeBg, int activeText, int inactiveBg, int inactiveText) {
        if (isActive) {
            btn.setBackgroundColor(activeBg);
            btn.setTextColor(activeText);
        } else {
            btn.setBackgroundColor(inactiveBg);
            btn.setTextColor(inactiveText);
        }
    }

    private void switchTheme(int mode) {
        if (currentThemeMode == mode) {
            return;
        }
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putInt(KEY_THEME, mode)
                .apply();
        recreate();
    }

    @Override
    public void onMapReady(@NonNull MapLibreMap map) {
        this.maplibreMap = map;

        map.getUiSettings().setLogoEnabled(false);
        map.getUiSettings().setAttributionEnabled(false);

        // Выбор бойца по клику на его маркер на тактической карте
        map.setOnMarkerClickListener(marker -> {
            for (Map.Entry<Long, Marker> entry : tacticalMarkers.entrySet()) {
                if (entry.getValue().equals(marker)) {
                    selectActiveUnit(entry.getKey());
                    return true;
                }
            }
            return false;
        });

        map.setStyle(new Style.Builder().fromUri("https://demotiles.maplibre.org/style.json"), style -> {
            LatLng initialPosition = new LatLng(55.753912, 37.620811);

            map.setCameraPosition(new CameraPosition.Builder()
                    .target(initialPosition)
                    .zoom(14.0)
                    .build());

            observeSquadTelemetry();
            mockGenerator.start();
        });
    }

    private void observeSquadTelemetry() {
        for (long userId : SQUAD_IDS) {
            // Наблюдение за последней точкой каждого бойца
            viewModel.getLatestTelemetry(userId).observe(this, entity -> {
                if (entity == null || maplibreMap == null) {
                    return;
                }
                squadLatestData.put(entity.userId, entity);
                updateUnitMarker(entity);

                if (entity.userId == activeUserId) {
                    updateDashboard(entity);
                }
            });

            // Наблюдение за историей перемещений каждого бойца
            viewModel.getHistory(userId, 0L).observe(this, history -> {
                if (history == null || maplibreMap == null || history.isEmpty()) {
                    return;
                }
                updateUnitTrack(userId, history);
            });
        }
    }

    private void updateUnitMarker(TelemetryEntity entity) {
        LatLng position = new LatLng(entity.latitude, entity.longitude);
        int statusColor = resolveUnitStatusColor(entity);

        boolean isActive = (entity.userId == activeUserId);
        Bitmap markerBitmap = createTacticalMarkerBitmap((float) entity.headingDegrees, statusColor, isActive);
        Icon icon = IconFactory.getInstance(this).fromBitmap(markerBitmap);

        String callsign = getCallsignByUserId(entity.userId);
        String snippet = "ЧСС: " + entity.pulseBpm + " BPM | " + String.format(Locale.US, "%.1f", entity.temperatureCelsius) + " °C";

        Marker marker = tacticalMarkers.get(entity.userId);
        if (marker == null) {
            marker = maplibreMap.addMarker(new MarkerOptions()
                    .position(position)
                    .title(callsign)
                    .snippet(snippet)
                    .icon(icon));
            tacticalMarkers.put(entity.userId, marker);
        } else {
            marker.setPosition(position);
            marker.setIcon(icon);
            marker.setTitle(callsign);
            marker.setSnippet(snippet);
        }
    }

    private void updateUnitTrack(long userId, List<TelemetryEntity> history) {
        List<LatLng> points = new ArrayList<>(history.size());
        for (TelemetryEntity item : history) {
            points.add(new LatLng(item.latitude, item.longitude));
        }

        int trackColor = resolveThemeColor(R.attr.appHairline);
        Polyline polyline = tacticalTracks.get(userId);

        if (polyline == null) {
            polyline = maplibreMap.addPolyline(new PolylineOptions()
                    .addAll(points)
                    .color(trackColor)
                    .width(2.0f));
            tacticalTracks.put(userId, polyline);
        } else {
            polyline.setPoints(points);
        }
    }

    private void updateDashboard(TelemetryEntity entity) {
        textCoords.setText(String.format(Locale.US, "%.5f° N  %.5f° E", entity.latitude, entity.longitude));
        textCallsign.setText(getCallsignByUserId(entity.userId));
        textPulse.setText(String.format(Locale.US, "%d BPM", entity.pulseBpm));
        textTemperature.setText(String.format(Locale.US, "%.1f °C", entity.temperatureCelsius));
        textPressure.setText(String.format(Locale.US, "%d/%d", entity.pressureSys, entity.pressureDia));

        int statusColor = resolveUnitStatusColor(entity);
        viewStatusIndicator.setBackgroundColor(statusColor);
    }

    private int resolveUnitStatusColor(TelemetryEntity entity) {
        com.example.mobile_embedded_system.domain.TacticalStatusEvaluator.Status status =
                com.example.mobile_embedded_system.domain.TacticalStatusEvaluator.evaluate(
                        entity.pulseBpm,
                        entity.temperatureCelsius
                );

        int statusAttr;
        switch (status) {
            case CRITICAL:
                statusAttr = R.attr.appStatusCritical;
                break;
            case WARNING:
                statusAttr = R.attr.appStatusWarning;
                break;
            case OK:
            default:
                statusAttr = R.attr.appStatusOk;
                break;
        }
        return resolveThemeColor(statusAttr);
    }

    private String getCallsignByUserId(long userId) {
        if (userId == 1001L) return "БОЕЦ [1001] • КОМАНДИР";
        if (userId == 1002L) return "БОЕЦ [1002] • СТРЕЛОК";
        if (userId == 1003L) return "БОЕЦ [1003] • САНИНСТРУКТОР";
        return "БОЕЦ [" + userId + "]";
    }

    /**
     * Создание тактического маркера бойца (ТЗ §6.11).
     * Для активного бойца рисуется утолщённая контрастная обводка.
     */
    private Bitmap createTacticalMarkerBitmap(float headingDegrees, int arrowColor, boolean isActive) {
        int sizePx = 64;
        Bitmap bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);

        int surfaceBg = resolveThemeColor(R.attr.appSurface);
        int strokeColor = isActive ? resolveThemeColor(R.attr.appInk) : resolveThemeColor(R.attr.appHairline);

        Paint bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        bgPaint.setStyle(Paint.Style.FILL);
        bgPaint.setColor(surfaceBg);
        canvas.drawRect(4, 4, sizePx - 4, sizePx - 4, bgPaint);

        Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        strokePaint.setStyle(Paint.Style.STROKE);
        strokePaint.setStrokeWidth(isActive ? 5f : 3f);
        strokePaint.setColor(strokeColor);
        canvas.drawRect(4, 4, sizePx - 4, sizePx - 4, strokePaint);

        canvas.save();
        canvas.rotate(headingDegrees, sizePx / 2.0f, sizePx / 2.0f);

        Paint arrowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        arrowPaint.setStyle(Paint.Style.FILL);
        arrowPaint.setColor(arrowColor);

        Path arrowPath = new Path();
        arrowPath.moveTo(sizePx / 2.0f, 12f);
        arrowPath.lineTo(sizePx - 16f, sizePx - 14f);
        arrowPath.lineTo(sizePx / 2.0f, sizePx - 22f);
        arrowPath.lineTo(16f, sizePx - 14f);
        arrowPath.close();

        canvas.drawPath(arrowPath, arrowPaint);
        canvas.restore();

        return bitmap;
    }

    private int resolveThemeColor(int attrResId) {
        TypedValue typedValue = new TypedValue();
        if (getTheme().resolveAttribute(attrResId, typedValue, true)) {
            return typedValue.data;
        }
        return 0xFF000000;
    }

    @Override
    protected void onStart() {
        super.onStart();
        mapView.onStart();
    }

    @Override
    protected void onResume() {
        super.onResume();
        mapView.onResume();
        if (mockGenerator != null && maplibreMap != null) {
            mockGenerator.start();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        mapView.onPause();
        if (mockGenerator != null) {
            mockGenerator.stop();
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        mapView.onStop();
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        mapView.onSaveInstanceState(outState);
    }

    @Override
    public void onLowMemory() {
        super.onLowMemory();
        mapView.onLowMemory();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mockGenerator != null) {
            mockGenerator.stop();
        }
        mapView.onDestroy();
    }
}