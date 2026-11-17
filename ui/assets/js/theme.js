/*
 * COS3 – light / dark theme.
 * Loaded in each page's <head>, before style.css, so the page never flashes the wrong theme.
 *
 * Sets data-theme="light" or "dark" on <html>; style.css defines the colors for each.
 * The choice is remembered in localStorage; without one, the theme follows the OS setting.
 * Changing it dispatches a "cos3:theme" event on window (the charts redraw on it).
 */
(function () {
  'use strict';

  const KEY = 'cos3-theme';

  function saved() {
    try {
      const v = localStorage.getItem(KEY);
      return v === 'light' || v === 'dark' ? v : null;
    } catch (e) {
      return null; // Storage blocked (private window, file:// …)
    }
  }

  function system() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    window.dispatchEvent(new CustomEvent('cos3:theme', { detail: theme }));
  }

  function get() {
    return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
  }

  function set(theme) {
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {
      // Not saved: the theme still changes for this page
    }
    apply(theme);
  }

  function toggle() {
    set(get() === 'dark' ? 'light' : 'dark');
  }

  apply(saved() || system());

  // Follow OS changes until the user picks a theme themselves
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!saved()) apply(system());
    });
  }

  window.COS3 = window.COS3 || {};
  window.COS3.theme = { get, set, toggle };
})();
