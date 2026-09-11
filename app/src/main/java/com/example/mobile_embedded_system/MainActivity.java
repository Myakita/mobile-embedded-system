package com.example.mobile_embedded_system;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.Bundle;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import org.maplibre.android.MapLibre;
import org.maplibre.android.annotations.Icon;
import org.maplibre.android.annotations.IconFactory;
import org.maplibre.android.annotations.MarkerOptions;
import org.maplibre.android.camera.CameraPosition;
import org.maplibre.android.geometry.LatLng;
import org.maplibre.android.maps.MapView;
import org.maplibre.android.maps.MapLibreMap;
import org.maplibre.android.maps.OnMapReadyCallback;
import org.maplibre.android.maps.Style;

/**
 * Экран тактической карты обстановки на базе MapLibre Native SDK (ТЗ §4.2, §6.10, §6.11).
 */
public class MainActivity extends AppCompatActivity implements OnMapReadyCallback {

    private MapView mapView;
    private MapLibreMap maplibreMap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        MapLibre.getInstance(this);

        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        mapView = findViewById(R.id.mapView);
        mapView.onCreate(savedInstanceState);
        mapView.getMapAsync(this);
    }

    @Override
    public void onMapReady(@NonNull MapLibreMap map) {
        this.maplibreMap = map;

        // Отключение стандартных виджетов под требования приборной панели (ТЗ §6.3, §6.10)
        map.getUiSettings().setLogoEnabled(false);
        map.getUiSettings().setAttributionEnabled(false);

        // Автономный открытый стиль тайлов (ТЗ §4.2)
        map.setStyle(new Style.Builder().fromUri("https://demotiles.maplibre.org/style.json"), style -> {
            LatLng basePosition = new LatLng(55.753912, 37.620811);

            // Центрирование камеры
            map.setCameraPosition(new CameraPosition.Builder()
                    .target(basePosition)
                    .zoom(13.0)
                    .build());

            // Добавление тактического маркера бойца (ТЗ §6.11)
            Bitmap markerBitmap = createBitmapFromVector(R.drawable.ic_tactical_marker);
            if (markerBitmap != null) {
                Icon icon = IconFactory.getInstance(this).fromBitmap(markerBitmap);
                map.addMarker(new MarkerOptions()
                        .position(basePosition)
                        .title("КОМАНДИР [1001]")
                        .snippet("ЧСС: 74 BPM | 36.6 °C")
                        .icon(icon));
            }
        });
    }

    /**
     * Конвертер векторных drawable в растровый буфер для MapLibre IconFactory
     */
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