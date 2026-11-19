(function () {
  'use strict';

  const KEY = 'cos3-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function saved() {
    try {
      const v = localStorage.getItem(KEY);
      return v === 'light' || v === 'dark' ? v : null;
    } catch (e) {
      return null;
    }
  }

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    window.dispatchEvent(new Event('cos3:theme'));
  }

  function get() {
    return document.documentElement.dataset.theme;
  }

  function toggle() {
    const theme = get() === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {}
    apply(theme);
  }

  apply(saved() || (media.matches ? 'dark' : 'light'));
  media.addEventListener('change', () => saved() || apply(media.matches ? 'dark' : 'light'));

  window.COS3 = window.COS3 || {};
  window.COS3.theme = { get, toggle };
})();
