package com.example.mobile_embedded_system.ui;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

public class Replace {
    public static void main(String[] args) throws Exception {
        Path path = Paths.get("C:/Users/Vladislav/Desktop/IT/Project_ANDROID/app/src/main/java/com/example/mobile_embedded_system/ui/MapFragment.java");
        String text = new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
        
        text = text.replace("public class MapFragment extends androidx.fragment.app.Fragment", "public class MapFragment extends androidx.fragment.app.Fragment");
        
        text = text.replace("protected void onCreate(Bundle savedInstanceState) {", 
            "public android.view.View onCreateView(@androidx.annotation.NonNull android.view.LayoutInflater inflater, @androidx.annotation.Nullable android.view.ViewGroup container, @androidx.annotation.Nullable Bundle savedInstanceState) {\n" +
            "    return inflater.inflate(com.example.mobile_embedded_system.R.layout.fragment_map, container, false);\n" +
            "}\n\n" +
            "@Override\n" +
            "public void onViewCreated(@androidx.annotation.NonNull android.view.View view, @androidx.annotation.Nullable Bundle savedInstanceState) {");
        
        text = text.replace("super.onCreate(savedInstanceState);", "super.onViewCreated(view, savedInstanceState);");
        text = text.replace("setContentView(R.layout.activity_main);", "");
        text = text.replace("MapLibre.getInstance(this);", "MapLibre.getInstance(requireContext());");
        
        text = text.replace("SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);", "SharedPreferences prefs = requireActivity().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);");
        text = text.replace("setTheme(R.style.Theme_UnitMonitor_Blackout);", "requireActivity().setTheme(R.style.Theme_UnitMonitor_Blackout);");
        text = text.replace("setTheme(R.style.Theme_UnitMonitor_Day);", "requireActivity().setTheme(R.style.Theme_UnitMonitor_Day);");
        text = text.replace("setTheme(R.style.Theme_UnitMonitor_Instrument);", "requireActivity().setTheme(R.style.Theme_UnitMonitor_Instrument);");
        
        text = text.replace("viewModel = new ViewModelProvider(this)", "viewModel = new ViewModelProvider(requireActivity())");
        text = text.replace("alertManager = new SquadAlertManager(this)", "alertManager = new SquadAlertManager(requireContext())");
        text = text.replace("initViews(savedInstanceState);", "initViews(view, savedInstanceState);");
        
        text = text.replace("private void initViews(Bundle savedInstanceState)", "private void initViews(android.view.View view, Bundle savedInstanceState)");
        text = text.replace("findViewById(", "view.findViewById(");
        text = text.replace("mapView.getMapAsync(this);", "mapView.getMapAsync(this);"); // unchanged basically
        
        text = text.replace("setupThemeButtons();", "setupThemeButtons(view);");
        text = text.replace("private void setupThemeButtons()", "private void setupThemeButtons(android.view.View view)");
        text = text.replace("updateThemeButtonsUI(currentThemeMode);", "updateThemeButtonsUI(currentThemeMode, view);");
        text = text.replace("private void updateThemeButtonsUI(int activeMode)", "private void updateThemeButtonsUI(int activeMode, android.view.View view)");
        
        text = text.replace("SharedPreferences.Editor editor = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit();", "SharedPreferences.Editor editor = requireActivity().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();");
        text = text.replace("recreate();", "requireActivity().recreate();");
        
        text = text.replace("this.registerReceiver", "requireContext().registerReceiver");
        text = text.replace("this.unregisterReceiver", "requireContext().unregisterReceiver");
        text = text.replace("registerReceiver(batteryReceiver", "requireContext().registerReceiver(batteryReceiver");
        text = text.replace("unregisterReceiver(batteryReceiver", "requireContext().unregisterReceiver(batteryReceiver");
        
        text = text.replace("getSystemService(Context.VIBRATOR_SERVICE)", "requireContext().getSystemService(Context.VIBRATOR_SERVICE)");
        
        text = text.replace("import androidx.appcompat.app.AppCompatActivity;", "import androidx.fragment.app.Fragment;\nimport com.example.mobile_embedded_system.R;");
        
        // WindowInsetsControllerCompat requires window
        text = text.replace("WindowInsetsControllerCompat windowInsetsController =", "if(requireActivity().getWindow() != null) {\nWindowInsetsControllerCompat windowInsetsController =");
        text = text.replace("windowInsetsController.setAppearanceLightStatusBars(false);", "windowInsetsController.setAppearanceLightStatusBars(false);\n}");
        text = text.replace("windowInsetsController.setAppearanceLightStatusBars(true);", "windowInsetsController.setAppearanceLightStatusBars(true);\n}");
        
        text = text.replace("WindowCompat.setDecorFitsSystemWindows(getWindow(), false);", "WindowCompat.setDecorFitsSystemWindows(requireActivity().getWindow(), false);");
        
        Files.write(path, text.getBytes(StandardCharsets.UTF_8));
    }
}