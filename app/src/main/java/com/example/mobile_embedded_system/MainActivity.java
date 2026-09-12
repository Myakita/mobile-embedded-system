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
import java.util.List;
import java.util.Locale;

public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private static final long TARGET_USER_ID = 1001L;
    private static final String PREFS_NAME = "unit_monitor_prefs";
    private static final String KEY_THEME = "selected_theme";

    private static final int THEME_INSTRUMENT = 0;
    private static final int THEME_DAY = 1;
    private static final int THEME_BLACKOUT = 2;

    private MapView mapView;
    private MapLibreMap maplibreMap;
    private TelemetryViewModel viewModel;
    private MockTelemetryGenerator mockGenerator;

    private Marker tacticalMarker;
    private Polyline tacticalTrack;
    private LatLng lastKnownPosition;

    private TextView textCoords;
    private TextView textPulse;
    private TextView textTemperature;
    private TextView textPressure;
    private View viewStatusIndicator;

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

        // Контрастность иконок статус-бара (темные для светлой темы, светлые для темных)
        WindowInsetsControllerCompat insetsController = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        insetsController.setAppearanceLightStatusBars(currentThemeMode == THEME_DAY);

        initViews(savedInstanceState);
        setupThemeButtons();
        updateThemeButtonsUI(currentThemeMode);

        viewModel = new ViewModelProvider(this).get(TelemetryViewModel.class);
        mockGenerator = new MockTelemetryGenerator(viewModel);

        mapView.getMapAsync(this);
    }

    private void initViews(Bundle savedInstanceState) {
        textCoords = findViewById(R.id.textCoords);
        textPulse = findViewById(R.id.textPulse);
        textTemperature = findViewById(R.id.textTemperature);
        textPressure = findViewById(R.id.textPressure);
        viewStatusIndicator = findViewById(R.id.viewStatusIndicator);

        // Центрирование камеры на бойце по тапу на приборную карточку
        View panelTelemetry = findViewById(R.id.panelTelemetry);
        panelTelemetry.setOnClickListener(v -> {
            if (maplibreMap != null && lastKnownPosition != null) {
                maplibreMap.easeCamera(CameraUpdateFactory.newLatLng(lastKnownPosition), 500);
            }
        });

        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);
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

        map.setStyle(new Style.Builder().fromUri("https://demotiles.maplibre.org/style.json"), style -> {
            LatLng initialPosition = new LatLng(55.753912, 37.620811);

            map.setCameraPosition(new CameraPosition.Builder()
                    .target(initialPosition)
                    .zoom(14.0)
                    .build());

            observeTelemetry();
            mockGenerator.start();
        });
    }

    private void observeTelemetry() {
        viewModel.getLatestTelemetry(TARGET_USER_ID).observe(this, entity -> {
            if (entity == null || maplibreMap == null) {
                return;
            }
            updateTacticalUI(entity);
        });

        viewModel.getHistory(TARGET_USER_ID, 0L).observe(this, history -> {
            if (history == null || maplibreMap == null || history.isEmpty()) {
                return;
            }
            updateTacticalTrack(history);
        });
    }

    private void updateTacticalUI(TelemetryEntity entity) {
        lastKnownPosition = new LatLng(entity.latitude, entity.longitude);

        textCoords.setText(String.format(Locale.US, "%.5f° N  %.5f° E", entity.latitude, entity.longitude));
        textPulse.setText(String.format(Locale.US, "%d BPM", entity.pulseBpm));
        textTemperature.setText(String.format(Locale.US, "%.1f °C", entity.temperatureCelsius));
        textPressure.setText(String.format(Locale.US, "%d/%d", entity.pressureSys, entity.pressureDia));

        int statusColorAttr;
        if (entity.pulseBpm > 120 || entity.pulseBpm < 45 || entity.temperatureCelsius > 38.5) {
            statusColorAttr = R.attr.appStatusCritical;
        } else if (entity.pulseBpm > 95 || entity.temperatureCelsius > 37.5) {
            statusColorAttr = R.attr.appStatusWarning;
        } else {
            statusColorAttr = R.attr.appStatusOk;
        }

        int statusColor = resolveThemeColor(statusColorAttr);
        viewStatusIndicator.setBackgroundColor(statusColor);

        Bitmap markerBitmap = createTacticalMarkerBitmap((float) entity.headingDegrees, statusColor);
        Icon icon = IconFactory.getInstance(this).fromBitmap(markerBitmap);

        if (tacticalMarker == null) {
            tacticalMarker = maplibreMap.addMarker(new MarkerOptions()
                    .position(lastKnownPosition)
                    .title("БОЕЦ [" + entity.userId + "]")
                    .snippet("ЧСС: " + entity.pulseBpm + " BPM | " + String.format(Locale.US, "%.1f", entity.temperatureCelsius) + " °C")
                    .icon(icon));
        } else {
            tacticalMarker.setPosition(lastKnownPosition);
            tacticalMarker.setIcon(icon);
            tacticalMarker.setSnippet("ЧСС: " + entity.pulseBpm + " BPM | " + String.format(Locale.US, "%.1f", entity.temperatureCelsius) + " °C");
        }
    }

    private void updateTacticalTrack(List<TelemetryEntity> history) {
        List<LatLng> points = new ArrayList<>(history.size());
        for (TelemetryEntity item : history) {
            points.add(new LatLng(item.latitude, item.longitude));
        }

        int trackColor = resolveThemeColor(R.attr.appHairline);

        if (tacticalTrack == null) {
            tacticalTrack = maplibreMap.addPolyline(new PolylineOptions()
                    .addAll(points)
                    .color(trackColor)
                    .width(2.0f));
        } else {
            tacticalTrack.setPoints(points);
        }
    }

    private Bitmap createTacticalMarkerBitmap(float headingDegrees, int arrowColor) {
        int sizePx = 64;
        Bitmap bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);

        int surfaceBg = resolveThemeColor(R.attr.appSurface);
        int strokeColor = resolveThemeColor(R.attr.appHairline);

        Paint bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        bgPaint.setStyle(Paint.Style.FILL);
        bgPaint.setColor(surfaceBg);
        canvas.drawRect(4, 4, sizePx - 4, sizePx - 4, bgPaint);

        Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        strokePaint.setStyle(Paint.Style.STROKE);
        strokePaint.setStrokeWidth(3f);
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