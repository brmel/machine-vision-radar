(function () {
  try {
    var pref = localStorage.getItem("machineVisionRadar.themePreference") || "system";
    var isDark =
      pref === "dark" ||
      (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
  } catch (e) {
    document.documentElement.classList.add("dark");
  }
})();
