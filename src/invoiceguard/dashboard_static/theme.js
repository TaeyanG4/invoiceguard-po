// Applied before first paint: dark by default; an explicit light choice is remembered per browser.
(function () {
  "use strict";
  var theme = "dark";
  try {
    if (window.localStorage.getItem("ig-theme") === "light") theme = "light";
  } catch (e) { /* storage blocked: stay on the dark default */ }
  document.documentElement.setAttribute("data-theme", theme);
})();
