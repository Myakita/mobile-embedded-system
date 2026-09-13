$path = "C:/Users/Vladislav/Desktop/IT/Project_ANDROID/app/src/main/java/com/example/mobile_embedded_system/ui/MapFragment.java"
$text = [IO.File]::ReadAllText($path)

$text = $text.Replace("private void selectActiveUnit(long userId, View view)", "private void selectActiveUnit(long userId)")
$text = $text.Replace("updateSquadButtonsUI(view);", "updateSquadButtonsUI(getView());")
$text = $text.Replace("getSharedPreferences(PREFS_NAME, MODE_PRIVATE)", "requireActivity().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)")
$text = $text.Replace("recreate();", "requireActivity().recreate();")
$text = $text.Replace("unrequireContext().registerReceiver", "requireContext().unregisterReceiver")
$text = $text.Replace("updateDashboard(entity, view);", "updateDashboard(entity);")
$text = $text.Replace("selectActiveUnit(currentAlertUserId, view);", "selectActiveUnit(currentAlertUserId);")

[IO.File]::WriteAllText($path, $text)
