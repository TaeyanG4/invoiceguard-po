// Applies the saved theme before first paint (loaded synchronously in <head>; no inline script under the CSP).
// "light" / "dark" are explicit user choices; with nothing saved the page follows the OS (prefers-color-scheme).
(function () {
  "use strict";
  try {
    var saved = window.localStorage.getItem("ig-theme");
    if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
  } catch (e) { /* storage unavailable: follow the OS */ }
})();
