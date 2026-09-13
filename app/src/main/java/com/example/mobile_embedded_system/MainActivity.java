package com.example.mobile_embedded_system;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.TypedValue;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.lifecycle.ViewModelProvider;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.domain.SquadAlertManager;
import com.example.mobile_embedded_system.domain.TacticalNavigationCalculator;
import com.example.mobile_embedded_system.domain.TacticalRangeRingGenerator;
import com.example.mobile_embedded_system.domain.TacticalStatusEvaluator;
import com.example.mobile_embedded_system.domain.TacticalWaypointManager;
import com.example.mobile_embedded_system.domain.Waypoint;
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
import org.maplibre.android.style.layers.BackgroundLayer;
import org.maplibre.android.style.layers.PropertyFactory;
import org.maplibre.android.style.layers.RasterLayer;
import org.maplibre.android.style.sources.RasterSource;
import org.maplibre.android.style.sources.TileSet;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Экран тактической обстановки с персональным целеуказанием и сохранением состояния (ТЗ §4.1, §6.7, §6.10).
 */
public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private static final long[] SQUAD_IDS = {1001L, 1002L, 1003L};
    private static final String PREFS_NAME = "unit_monitor_prefs";
    private static final String KEY_THEME = "selected_theme";

    private static final int THEME_INSTRUMENT = 0;
    private static final int THEME_DAY = 1;
    private static final int THEME_BLACKOUT = 2;

    private static final double[] RANGE_RING_RADII = {100.0, 250.0, 500.0};

    private MapView mapView;
    private MapLibreMap maplibreMap;
    private TelemetryViewModel viewModel;
    private SquadAlertManager alertManager;
    private TacticalWaypointManager waypointManager;

    private final Map<Long, Marker> waypointMarkers = new HashMap<>();
    private final Map<Long, Marker> tacticalMarkers = new HashMap<>();
    private final Map<Long, Polyline> tacticalTracks = new HashMap<>();
    private final Map<Long, TelemetryEntity> squadLatestData = new HashMap<>();
    private final List<Polyline> rangeRingPolylines = new ArrayList<>();

    private long activeUserId = 1001L;
    private Long currentAlertUserId = null;
    private boolean isMqttMode = false;
    private boolean isTrackUp = false;

    private TextView btnMapOrientation;
    private TextView textCoords;
    private TextView textCallsign;
    private TextView textPulse;
    private TextView textTemperature;
    private TextView textPressure;
    private TextView textLinkStatus;
    private View viewStatusIndicator;
    private TextView textRangeBearing;

    private View bannerEmergency;
    private TextView textEmergencyTitle;

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

        alertManager = new SquadAlertManager();
        viewModel = new ViewModelProvider(this).get(TelemetryViewModel.class);
        waypointManager = viewModel.getWaypointManager();

        activeUserId = viewModel.getActiveUserId();
        isTrackUp = viewModel.isTrackUp();

        initViews(savedInstanceState);
        setupThemeButtons();
        setupSquadButtons();
        updateThemeButtonsUI(currentThemeMode);
        updateSquadButtonsUI();

        viewModel.getConnectionState().observe(this, state -> {
            if (textLinkStatus == null) return;
            switch (state) {
                case CONNECTING:
                    textLinkStatus.setText("СВЯЗЬ: ПОИСК СЕТИ...");
                    textLinkStatus.setTextColor(resolveThemeColor(R.attr.appStatusWarning));
                    break;
                case CONNECTED:
                    textLinkStatus.setText("СВЯЗЬ: ЭФИР (MQTT)");
                    textLinkStatus.setTextColor(resolveThemeColor(R.attr.appStatusOk));
                    break;
                case DISCONNECTED:
                    textLinkStatus.setText("СВЯЗЬ: ОТКЛЮЧЕНО [TAP]");
                    textLinkStatus.setTextColor(resolveThemeColor(R.attr.appStatusCritical));
                    break;
                case MOCK_MODE:
                    textLinkStatus.setText("СВЯЗЬ: ИМИТАТОР [TAP]");
                    textLinkStatus.setTextColor(resolveThemeColor(R.attr.appInk2));
                    break;
            }
        });

        mapView.getMapAsync(this);
    }

    private void initViews(Bundle savedInstanceState) {
        textCoords = findViewById(R.id.textCoords);
        textCallsign = findViewById(R.id.textCallsign);
        textPulse = findViewById(R.id.textPulse);
        textTemperature = findViewById(R.id.textTemperature);
        textPressure = findViewById(R.id.textPressure);
        textLinkStatus = findViewById(R.id.textLinkStatus);
        viewStatusIndicator = findViewById(R.id.viewStatusIndicator);
        textRangeBearing = findViewById(R.id.textRangeBearing);

        btnMapOrientation = findViewById(R.id.btnMapOrientation);
        btnMapOrientation.setOnClickListener(v -> toggleMapOrientation());
        updateMapOrientationUI();

        bannerEmergency = findViewById(R.id.bannerEmergency);
        textEmergencyTitle = findViewById(R.id.textEmergencyTitle);

        bannerEmergency.setOnClickListener(v -> {
            if (currentAlertUserId != null) {
                selectActiveUnit(currentAlertUserId);
            }
        });

        textLinkStatus.setOnClickListener(v -> {
            isMqttMode = !isMqttMode;
            if (isMqttMode) {
                String clientId = "unit_terminal_" + System.currentTimeMillis();
                viewModel.startMqttMode("tcp://broker.hivemq.com:1883", clientId);
            } else {
                viewModel.startMockMode();
            }
        });

        btnUnit1001 = findViewById(R.id.btnUnit1001);
        btnUnit1002 = findViewById(R.id.btnUnit1002);
        btnUnit1003 = findViewById(R.id.btnUnit1003);

        findViewById(R.id.panelTelemetry).setOnClickListener(v -> snapCameraToActiveUnit());

        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);
    }

    private void setupSquadButtons() {
        btnUnit1001.setOnClickListener(v -> selectActiveUnit(1001L));
        btnUnit1002.setOnClickListener(v -> selectActiveUnit(1002L));
        btnUnit1003.setOnClickListener(v -> selectActiveUnit(1003L));
    }

    private void toggleMapOrientation() {
        isTrackUp = !isTrackUp;
        viewModel.setTrackUp(isTrackUp);
        updateMapOrientationUI();
        snapCameraToActiveUnit();
    }

    private void updateMapOrientationUI() {
        if (btnMapOrientation == null) return;
        if (isTrackUp) {
            btnMapOrientation.setText("КУРС: СЛЕДИТЬ");
            btnMapOrientation.setTextColor(resolveThemeColor(R.attr.appStatusOk));
        } else {
            btnMapOrientation.setText("КУРС: СЕВЕР");
            btnMapOrientation.setTextColor(resolveThemeColor(R.attr.appInk));
        }
    }

    private void selectActiveUnit(long userId) {
        activeUserId = userId;
        viewModel.setActiveUserId(userId);
        updateSquadButtonsUI();

        TelemetryEntity entity = squadLatestData.get(activeUserId);
        if (entity != null) {
            updateDashboard(entity);
            snapCameraToActiveUnit();
        }
        updateNavigationLine();
    }

    private void snapCameraToActiveUnit() {
        TelemetryEntity entity = squadLatestData.get(activeUserId);
        if (maplibreMap != null && entity != null) {
            CameraPosition.Builder builder = new CameraPosition.Builder()
                    .target(new LatLng(entity.latitude, entity.longitude));

            if (isTrackUp) {
                builder.bearing(entity.headingDegrees);
            } else {
                builder.bearing(0.0);
            }

            maplibreMap.easeCamera(CameraUpdateFactory.newCameraPosition(builder.build()), 400);
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
        if (maplibreMap != null) {
            CameraPosition pos = maplibreMap.getCameraPosition();
            viewModel.saveCameraState(
                    pos.target.getLatitude(),
                    pos.target.getLongitude(),
                    pos.zoom,
                    pos.bearing
            );
        }
        viewModel.setActiveUserId(activeUserId);
        viewModel.setTrackUp(isTrackUp);

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

        map.setOnMarkerClickListener(marker -> {
            for (Map.Entry<Long, Marker> entry : tacticalMarkers.entrySet()) {
                if (entry.getValue().equals(marker)) {
                    selectActiveUnit(entry.getKey());
                    return true;
                }
            }
            return false;
        });

        map.addOnMapLongClickListener(point -> {
            Waypoint wp = waypointManager.addWaypoint(point.getLatitude(), point.getLongitude());
            waypointManager.assignTargetToUnit(activeUserId, wp.getId());
            viewModel.setUnitTarget(activeUserId, wp.getLatitude(), wp.getLongitude());

            renderWaypointMarker(wp, activeUserId);
            updateNavigationLine();
            triggerTactileAlert();
            return true;
        });

        int mapBgColor = resolveThemeColor(R.attr.appBg);

        Style.Builder offlineStyle = new Style.Builder()
                .withSource(new RasterSource("local-raster",
                        new TileSet("2.2.0", "asset://tiles/{z}/{x}/{y}.png"), 256))
                .withLayer(new BackgroundLayer("background-layer")
                        .withProperties(PropertyFactory.backgroundColor(mapBgColor)))
                .withLayer(new RasterLayer("raster-layer", "local-raster"));

        map.setStyle(offlineStyle, style -> {
            if (viewModel.hasSavedCamera()) {
                map.setCameraPosition(new CameraPosition.Builder()
                        .target(new LatLng(viewModel.getLastLat(), viewModel.getLastLon()))
                        .zoom(viewModel.getLastZoom())
                        .bearing(viewModel.getLastBearing())
                        .build());
            } else {
                LatLng initialPosition = new LatLng(55.753912, 37.620811);
                map.setCameraPosition(new CameraPosition.Builder()
                        .target(initialPosition)
                        .zoom(14.0)
                        .build());
            }

            for (Waypoint wp : waypointManager.getWaypoints()) {
                Long assignedUnit = waypointManager.getUnitAssignedToWaypoint(wp.getId());
                renderWaypointMarker(wp, assignedUnit != null ? assignedUnit : 0L);
            }

            observeSquadTelemetry();
        });
    }

    private void updateNavigationLine() {
        TelemetryEntity activeEntity = squadLatestData.get(activeUserId);
        if (activeEntity == null) {
            textRangeBearing.setVisibility(View.GONE);
            return;
        }

        Waypoint assignedWp = waypointManager.getAssignedWaypointForUnit(activeUserId);
        if (assignedWp != null) {
            TacticalWaypointManager.NavInfo nav = waypointManager.calculateNav(
                    activeEntity.latitude, activeEntity.longitude, assignedWp
            );
            if (nav != null) {
                textRangeBearing.setVisibility(View.VISIBLE);
                if (nav.distanceMeters <= 10.0) {
                    textRangeBearing.setText(String.format(
                            Locale.US,
                            "БОЕЦ [%d] -> ЦЕЛЬ [%s] ДОСТИГНУТА (ПЕЛЕНГ: %03d°)",
                            activeUserId,
                            assignedWp.getCallsign(),
                            Math.round(nav.bearingDegrees)
                    ));
                } else {
                    textRangeBearing.setText(String.format(
                            Locale.US,
                            "БОЕЦ [%d] -> ЦЕЛЬ [%s]: %d м  |  ПЕЛЕНГ: %03d°",
                            activeUserId,
                            assignedWp.getCallsign(),
                            Math.round(nav.distanceMeters),
                            Math.round(nav.bearingDegrees)
                    ));
                }
            }
        } else {
            if (activeUserId == 1001L) {
                textRangeBearing.setVisibility(View.GONE);
            } else {
                TelemetryEntity commander = squadLatestData.get(1001L);
                if (commander != null) {
                    double dist = TacticalNavigationCalculator.calculateDistanceMeters(
                            commander.latitude, commander.longitude,
                            activeEntity.latitude, activeEntity.longitude
                    );
                    double bearing = TacticalNavigationCalculator.calculateBearingDegrees(
                            commander.latitude, commander.longitude,
                            activeEntity.latitude, activeEntity.longitude
                    );
                    textRangeBearing.setVisibility(View.VISIBLE);
                    textRangeBearing.setText(String.format(
                            Locale.US,
                            "ОТ КМД -> ДИСТ: %d м  |  ПЕЛЕНГ: %03d°",
                            Math.round(dist),
                            Math.round(bearing)
                    ));
                } else {
                    textRangeBearing.setVisibility(View.GONE);
                }
            }
        }
    }

    private void renderWaypointMarker(Waypoint wp, long targetUserId) {
        if (maplibreMap == null) return;

        LatLng position = new LatLng(wp.getLatitude(), wp.getLongitude());
        Bitmap bitmap = createWaypointBitmap();
        Icon icon = IconFactory.getInstance(this).fromBitmap(bitmap);

        Marker marker = maplibreMap.addMarker(new MarkerOptions()
                .position(position)
                .title(wp.getCallsign() + " -> БОЕЦ [" + targetUserId + "]")
                .snippet("ОРИЕНТИР / БОЕВОЕ УКАЗАНИЕ")
                .icon(icon));

        waypointMarkers.put(wp.getId(), marker);
    }

    private Bitmap createWaypointBitmap() {
        int sizePx = 56;
        Bitmap bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);

        int accentColor = resolveThemeColor(R.attr.appStatusWarning);
        int surfaceColor = resolveThemeColor(R.attr.appSurface);

        Paint fillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        fillPaint.setStyle(Paint.Style.FILL);
        fillPaint.setColor(surfaceColor);

        Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        strokePaint.setStyle(Paint.Style.STROKE);
        strokePaint.setStrokeWidth(3.5f);
        strokePaint.setColor(accentColor);

        Path diamond = new Path();
        diamond.moveTo(sizePx / 2f, 6f);
        diamond.lineTo(sizePx - 6f, sizePx / 2f);
        diamond.lineTo(sizePx / 2f, sizePx - 6f);
        diamond.lineTo(6f, sizePx / 2f);
        diamond.close();

        canvas.drawPath(diamond, fillPaint);
        canvas.drawPath(diamond, strokePaint);

        canvas.drawLine(sizePx / 2f, 14f, sizePx / 2f, sizePx - 14f, strokePaint);
        canvas.drawLine(14f, sizePx / 2f, sizePx - 14f, sizePx / 2f, strokePaint);

        return bitmap;
    }

    private void observeSquadTelemetry() {
        for (long userId : SQUAD_IDS) {
            viewModel.getLatestTelemetry(userId).observe(this, entity -> {
                if (entity == null || maplibreMap == null) {
                    return;
                }
                squadLatestData.put(entity.userId, entity);
                handleSquadAlerts(entity);
                updateUnitMarker(entity);

                if (entity.userId == 1001L) {
                    updateRangeRings(entity.latitude, entity.longitude);
                }

                if (entity.userId == activeUserId) {
                    updateDashboard(entity);
                    updateNavigationLine();

                    if (isTrackUp && maplibreMap != null) {
                        CameraPosition newPos = new CameraPosition.Builder()
                                .target(new LatLng(entity.latitude, entity.longitude))
                                .bearing(entity.headingDegrees)
                                .zoom(maplibreMap.getCameraPosition().zoom)
                                .build();
                        maplibreMap.easeCamera(CameraUpdateFactory.newCameraPosition(newPos), 400);
                    }
                } else if (activeUserId != 1001L && entity.userId == 1001L) {
                    if (waypointManager.getAssignedWaypointForUnit(activeUserId) == null) {
                        updateNavigationLine();
                    }
                }
            });

            viewModel.getHistory(userId, 0L).observe(this, history -> {
                if (history == null || maplibreMap == null || history.isEmpty()) {
                    return;
                }
                updateUnitTrack(userId, history);
            });
        }
    }

    private void updateRangeRings(double centerLat, double centerLon) {
        if (maplibreMap == null) return;

        int ringColor = resolveThemeColor(R.attr.appHairline);

        if (rangeRingPolylines.isEmpty()) {
            for (double radius : RANGE_RING_RADII) {
                List<TacticalRangeRingGenerator.GeoPoint> geoPoints =
                        TacticalRangeRingGenerator.generateRingPoints(centerLat, centerLon, radius);

                List<LatLng> mapPoints = new ArrayList<>(geoPoints.size());
                for (TacticalRangeRingGenerator.GeoPoint gp : geoPoints) {
                    mapPoints.add(new LatLng(gp.latitude, gp.longitude));
                }

                Polyline polyline = maplibreMap.addPolyline(new PolylineOptions()
                        .addAll(mapPoints)
                        .color(ringColor)
                        .width(1.2f));

                rangeRingPolylines.add(polyline);
            }
        } else {
            for (int i = 0; i < RANGE_RING_RADII.length; i++) {
                double radius = RANGE_RING_RADII[i];
                List<TacticalRangeRingGenerator.GeoPoint> geoPoints =
                        TacticalRangeRingGenerator.generateRingPoints(centerLat, centerLon, radius);

                List<LatLng> mapPoints = new ArrayList<>(geoPoints.size());
                for (TacticalRangeRingGenerator.GeoPoint gp : geoPoints) {
                    mapPoints.add(new LatLng(gp.latitude, gp.longitude));
                }

                if (i < rangeRingPolylines.size()) {
                    rangeRingPolylines.get(i).setPoints(mapPoints);
                }
            }
        }
    }

    private void handleSquadAlerts(TelemetryEntity entity) {
        SquadAlertManager.AlertInfo alert = alertManager.processTelemetry(entity);

        if (alert != null) {
            currentAlertUserId = alert.userId;
            bannerEmergency.setVisibility(View.VISIBLE);
            textEmergencyTitle.setText("ТРЕВОГА: БОЕЦ [" + alert.userId + "] • " + alert.reason);
            triggerTactileAlert();
        } else if (!alertManager.hasActiveCriticalAlert()) {
            bannerEmergency.setVisibility(View.GONE);
            currentAlertUserId = null;
        }
    }

    private void triggerTactileAlert() {
        Vibrator vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        if (vibrator != null && vibrator.hasVibrator()) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                vibrator.vibrate(150);
            }
        }
    }

    private void updateUnitMarker(TelemetryEntity entity) {
        LatLng position = new LatLng(entity.latitude, entity.longitude);
        int statusColor = resolveUnitStatusColor(entity);

        boolean isActive = (entity.userId == activeUserId);
        boolean isCritical = (resolveUnitStatus(entity) == TacticalStatusEvaluator.Status.CRITICAL);

        Bitmap markerBitmap = createTacticalMarkerBitmap((float) entity.headingDegrees, statusColor, isActive, isCritical);
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

    private TacticalStatusEvaluator.Status resolveUnitStatus(TelemetryEntity entity) {
        return TacticalStatusEvaluator.evaluate(entity.pulseBpm, entity.temperatureCelsius);
    }

    private int resolveUnitStatusColor(TelemetryEntity entity) {
        TacticalStatusEvaluator.Status status = resolveUnitStatus(entity);
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

    private Bitmap createTacticalMarkerBitmap(float headingDegrees, int arrowColor, boolean isActive, boolean isCritical) {
        int sizePx = 64;
        Bitmap bitmap = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);

        int surfaceBg = resolveThemeColor(R.attr.appSurface);
        int strokeColor;
        if (isCritical) {
            strokeColor = resolveThemeColor(R.attr.appStatusCritical);
        } else if (isActive) {
            strokeColor = resolveThemeColor(R.attr.appInk);
        } else {
            strokeColor = resolveThemeColor(R.attr.appHairline);
        }

        Paint bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        bgPaint.setStyle(Paint.Style.FILL);
        bgPaint.setColor(surfaceBg);
        canvas.drawRect(4, 4, sizePx - 4, sizePx - 4, bgPaint);

        Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        strokePaint.setStyle(Paint.Style.STROKE);
        strokePaint.setStrokeWidth((isActive || isCritical) ? 5f : 3f);
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
    }

    @Override
    protected void onPause() {
        super.onPause();
        mapView.onPause();
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
        mapView.onDestroy();
    }
}