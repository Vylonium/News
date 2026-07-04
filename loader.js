// Loader: muat semua file data secara berurutan, lalu app.js
(function() {
  var files = ["data_indonesia.js", "data_jepang.js", "data_mesir.js", "data_romawi.js", "data_tiongkok.js", "data_inggris.js", "data_prancis.js", "data_jerman.js", "data_spanyol.js", "data_portugal.js", "data_india.js", "data_korea.js"];
  var i = 0;
  function loadNext() {
    if (i >= files.length) { loadApp(); return; }
    var s = document.createElement('script');
    s.src = files[i];
    s.onload = function() { i++; loadNext(); };
    document.body.appendChild(s);
  }
  function loadApp() {
    var s = document.createElement('script');
    s.src = 'app.js';
    document.body.appendChild(s);
  }
  loadNext();
})();
