package com.example.mobile_embedded_system;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.os.Bundle;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
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
import org.maplibre.android.geometry.LatLng;
import org.maplibre.android.maps.MapView;
import org.maplibre.android.maps.MapLibreMap;
import org.maplibre.android.maps.OnMapReadyCallback;
import org.maplibre.android.maps.Style;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Экран тактической карты обстановки на базе MapLibre Native SDK, MVVM и тактического трека (ТЗ §4.2, §6.10–§6.12).
 */
public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private static final long TARGET_USER_ID = 1001L;

    private MapView mapView;
    private MapLibreMap maplibreMap;
    private TelemetryViewModel viewModel;
    private MockTelemetryGenerator mockGenerator;

    private Marker tacticalMarker;
    private Polyline tacticalTrack;
    private TextView textCoords;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        MapLibre.getInstance(this);

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        textCoords = findViewById(R.id.textCoords);
        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);

        viewModel = new ViewModelProvider(this).get(TelemetryViewModel.class);
        mockGenerator = new MockTelemetryGenerator(viewModel);

        mapView.getMapAsync(this);
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
            // Запуск генератора тестовой телеметрии после готовности карты
            mockGenerator.start();
        });
    }

    private void observeTelemetry() {
        // 1. Наблюдение за последней позицией бойца
        viewModel.getLatestTelemetry(TARGET_USER_ID).observe(this, entity -> {
            if (entity == null || maplibreMap == null) {
                return;
            }
            updateTacticalMarker(entity);
        });

        // 2. Наблюдение за историей перемещений для отрисовки тактического трека (ТЗ §6.12)
        viewModel.getHistory(TARGET_USER_ID, 0L).observe(this, history -> {
            if (history == null || maplibreMap == null || history.isEmpty()) {
                return;
            }
            updateTacticalTrack(history);
        });
    }

    private void updateTacticalMarker(TelemetryEntity entity) {
        LatLng newPosition = new LatLng(entity.latitude, entity.longitude);

        textCoords.setText(String.format(Locale.US, "%.5f° N  %.5f° E", entity.latitude, entity.longitude));

        if (tacticalMarker == null) {
            Bitmap markerBitmap = createBitmapFromVector(R.drawable.ic_tactical_marker);
            Icon icon = markerBitmap != null ? IconFactory.getInstance(this).fromBitmap(markerBitmap) : null;

            tacticalMarker = maplibreMap.addMarker(new MarkerOptions()
                    .position(newPosition)
                    .title("БОЕЦ [" + entity.userId + "]")
                    .snippet("ЧСС: " + entity.pulseBpm + " BPM | " + String.format(Locale.US, "%.1f", entity.temperatureCelsius) + " °C")
                    .icon(icon));
        } else {
            tacticalMarker.setPosition(newPosition);
            tacticalMarker.setSnippet("ЧСС: " + entity.pulseBpm + " BPM | " + String.format(Locale.US, "%.1f", entity.temperatureCelsius) + " °C");
        }
    }

    private void updateTacticalTrack(List<TelemetryEntity> history) {
        List<LatLng> points = new ArrayList<>(history.size());
        for (TelemetryEntity item : history) {
            points.add(new LatLng(item.latitude, item.longitude));
        }

        if (tacticalTrack == null) {
            tacticalTrack = maplibreMap.addPolyline(new PolylineOptions()
                    .addAll(points)
                    .color(Color.parseColor("#454C50")) // Hairline цвет графита (ТЗ §6.4, §6.6)
                    .width(2.0f));
        } else {
            tacticalTrack.setPoints(points);
        }
    }

    private Bitmap createBitmapFromVector(int drawableResId) {
        Drawable drawable = ContextCompat.getDrawable(this, drawableResId);
        if (drawable == null) {
            return null;
        }
        Bitmap bitmap = Bitmap.createBitmap(
                drawable.getIntrinsicWidth(),
                drawable.getIntrinsicHeight(),
                Bitmap.Config.ARGB_8888
        );
        Canvas canvas = new Canvas(bitmap);
        drawable.setBounds(0, 0, canvas.getWidth(), canvas.getHeight());
        drawable.draw(canvas);
        return bitmap;
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