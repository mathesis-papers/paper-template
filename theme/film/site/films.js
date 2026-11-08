// trureturing books · films page: the 中 / EN switch. Chinese is the default; ?lang=en (or the stored choice) selects
// English. Only toggles html[data-lang], html[lang] and the title; the page is complete without this script.
(function () {
  'use strict';
  var KEY = 'tr-films-lang';
  var root = document.documentElement;
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function store(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* private mode: keep the choice for this page only */ } }
  function apply(lang) {
    lang = lang === 'en' ? 'en' : 'zh';
    root.setAttribute('data-lang', lang);
    root.setAttribute('lang', lang === 'en' ? 'en' : 'zh-CN');
    var title = root.getAttribute('data-title-' + lang);
    if (title) document.title = title;
    var buttons = document.querySelectorAll('[data-lang-set]');
    for (var i = 0; i < buttons.length; i++) buttons[i].setAttribute('aria-pressed', String(buttons[i].getAttribute('data-lang-set') === lang));
  }
  var q = null;
  try { q = new URLSearchParams(location.search).get('lang'); } catch (e) { /* very old browsers */ }
  apply(q || stored() || 'zh');
  document.addEventListener('DOMContentLoaded', function () {
    apply(root.getAttribute('data-lang'));
    document.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('[data-lang-set]');
      if (!b) return;
      var lang = b.getAttribute('data-lang-set');
      store(lang);
      apply(lang);
    });
  });
})();
