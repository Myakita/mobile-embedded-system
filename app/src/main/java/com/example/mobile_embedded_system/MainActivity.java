package com.example.mobile_embedded_system;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.Bundle;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.lifecycle.ViewModelProvider;

import com.example.mobile_embedded_system.data.local.TelemetryEntity;
import com.example.mobile_embedded_system.ui.TelemetryViewModel;

import org.maplibre.android.MapLibre;
import org.maplibre.android.annotations.Icon;
import org.maplibre.android.annotations.IconFactory;
import org.maplibre.android.annotations.Marker;
import org.maplibre.android.annotations.MarkerOptions;
import org.maplibre.android.camera.CameraPosition;
import org.maplibre.android.geometry.LatLng;
import org.maplibre.android.maps.MapView;
import org.maplibre.android.maps.MapLibreMap;
import org.maplibre.android.maps.OnMapReadyCallback;
import org.maplibre.android.maps.Style;

import java.util.Locale;

/**
 * Экран тактической карты обстановки на базе MapLibre Native SDK и MVVM (ТЗ §4.2, §6.10, §6.11).
 */
public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private static final long TARGET_USER_ID = 1001L;

    private MapView mapView;
    private MapLibreMap maplibreMap;
    private TelemetryViewModel viewModel;
    private Marker tacticalMarker;
    private TextView textCoords;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        MapLibre.getInstance(this);

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        textCoords = findViewById(R.id.textCoords);
        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);

        // Инициализация ViewModel по стандарту AndroidX Lifecycle
        viewModel = new ViewModelProvider(this).get(TelemetryViewModel.class);

        mapView.getMapAsync(this);
    }

    @Override
    public void onMapReady(@NonNull MapLibreMap map) {
        this.maplibreMap = map;

        // Отключение стандартных виджетов (ТЗ §6.3, §6.10)
        map.getUiSettings().setLogoEnabled(false);
        map.getUiSettings().setAttributionEnabled(false);

        map.setStyle(new Style.Builder().fromUri("https://demotiles.maplibre.org/style.json"), style -> {
            LatLng initialPosition = new LatLng(55.753912, 37.620811);

            map.setCameraPosition(new CameraPosition.Builder()
                    .target(initialPosition)
                    .zoom(13.0)
                    .build());

            // Реактивная подписка на LiveData из Room через ViewModel
            observeTelemetry();
        });
    }

    private void observeTelemetry() {
        viewModel.getLatestTelemetry(TARGET_USER_ID).observe(this, entity -> {
            if (entity == null || maplibreMap == null) {
                return;
            }
            updateTacticalPosition(entity);
        });
    }

    private void updateTacticalPosition(TelemetryEntity entity) {
        LatLng newPosition = new LatLng(entity.latitude, entity.longitude);

        // Обновление верхнего приборного рельса (ТЗ §6.5: IBM Plex Mono, tnum)
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