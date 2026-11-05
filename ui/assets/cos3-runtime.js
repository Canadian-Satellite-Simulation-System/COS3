/*
 * COS3 wireframes – tiny page runtime (no dependencies, works offline).
 *
 * Each page keeps its markup inside <template id="page"> and a small
 * `class Component extends DCLogic { renderVals() { ... } }` script.
 * This file turns that template into the visible page:
 *
 *   {{name}}                       -> value returned by renderVals()
 *   <template data-for="{{list}}" data-as="item"> ... </template>
 *                                  -> repeats its content for each item ({{item.x}}, {{$index}})
 *   <template data-if="{{flag}}"> ... </template>
 *                                  -> shows its content only when flag is true
 *   onClick="{{handler}}"          -> calls the function returned by renderVals()
 *   disabled / checked="{{flag}}"  -> attribute present only when flag is true
 *
 * Calling this.setState({...}) inside a handler re-draws the page.
 * Shared header and sidebar come from layout.js (placeholders: <div data-cos3="header|nav">).
 */
(function () {
  'use strict';

  class DCLogic {
    constructor(props) {
      this.props = props || {};
      this.state = {};
    }
    setState(patch) {
      const p = typeof patch === 'function' ? patch(this.state, this.props) : patch;
      this.state = Object.assign({}, this.state, p);
      render();
    }
    forceUpdate() { render(); }
  }
  window.DCLogic = DCLogic;

  const HOLE = /\{\{\s*([^}]*?)\s*\}\}/g;
  const WHOLE = /^\s*\{\{\s*([^}]*?)\s*\}\}\s*$/;
  const BOOL_ATTRS = new Set(['disabled', 'checked', 'selected', 'readonly', 'hidden', 'required', 'multiple', 'open']);

  function lookup(path, scope) {
    if (path === 'true') return true;
    if (path === 'false') return false;
    if (path === 'null') return null;
    if (/^-?\d+(\.\d+)?$/.test(path)) return Number(path);
    if (/^(['"]).*\1$/.test(path)) return path.slice(1, -1);
    let v = scope;
    for (const key of path.split('.')) {
      if (v == null) return undefined;
      v = v[key];
    }
    return v;
  }

  function interpolate(str, scope) {
    return str.replace(HOLE, (m, p) => {
      const v = lookup(p, scope);
      return v == null ? '' : String(v);
    });
  }

  function holeValue(attrValue, scope) {
    const m = WHOLE.exec(attrValue || '');
    return m ? lookup(m[1], scope) : attrValue;
  }

  function processChildren(source, scope, target) {
    for (const child of Array.from(source.childNodes)) {
      for (const n of processNode(child, scope)) target.appendChild(n);
    }
  }

  function processNode(node, scope) {
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent;
      return [document.createTextNode(t.indexOf('{{') >= 0 ? interpolate(t, scope) : t)];
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return [];

    if (node.tagName === 'TEMPLATE' && node.hasAttribute('data-for')) {
      const list = holeValue(node.getAttribute('data-for'), scope) || [];
      const as = node.getAttribute('data-as') || 'item';
      const out = [];
      Array.from(list).forEach((item, i) => {
        const s = Object.create(scope);
        s[as] = item;
        s.$index = i;
        const frag = document.createDocumentFragment();
        processChildren(node.content, s, frag);
        out.push(...Array.from(frag.childNodes));
      });
      return out;
    }
    if (node.tagName === 'TEMPLATE' && node.hasAttribute('data-if')) {
      if (!holeValue(node.getAttribute('data-if'), scope)) return [];
      const frag = document.createDocumentFragment();
      processChildren(node.content, scope, frag);
      return Array.from(frag.childNodes);
    }

    const el = document.importNode(node, false);
    for (const attr of Array.from(node.attributes)) {
      const name = attr.name;
      const val = attr.value;
      if (name.indexOf('on') === 0) {
        el.removeAttribute(name);
        const fn = holeValue(val, scope);
        if (typeof fn === 'function') el.addEventListener(name.slice(2), (e) => fn(e));
        continue;
      }
      if (val.indexOf('{{') < 0) continue;
      if (WHOLE.test(val)) {
        const v = holeValue(val, scope);
        if (BOOL_ATTRS.has(name)) {
          if (v) el.setAttribute(name, ''); else el.removeAttribute(name);
        } else if (v == null || v === false) {
          el.removeAttribute(name);
        } else {
          el.setAttribute(name, String(v));
        }
      } else {
        el.setAttribute(name, interpolate(val, scope));
      }
    }
    if (node.tagName !== 'TEMPLATE') processChildren(node, scope, el);
    return [el];
  }

  let instance = null;
  let pageTemplate = null;
  let app = null;

  function expandLayout(fragment) {
    for (const ph of Array.from(fragment.querySelectorAll('[data-cos3]'))) {
      const make = window.COS3.layouts[ph.getAttribute('data-cos3')];
      if (!make) continue;
      const t = document.createElement('template');
      t.innerHTML = make(Object.assign({}, ph.dataset));
      ph.replaceWith(t.content);
    }
  }

  function render() {
    if (!instance) return;
    const vals = instance.renderVals ? instance.renderVals() : {};
    const frag = document.createDocumentFragment();
    processChildren(pageTemplate.content, vals || {}, frag);
    app.replaceChildren(frag);
  }

  // Scales the 1440 x 900 page so it always fits the browser window (no manual zoom needed).
  const PAGE_W = 1440, PAGE_H = 900;
  function fitToWindow() {
    if (!app) return;
    const scale = Math.min(1, window.innerWidth / PAGE_W, window.innerHeight / PAGE_H);
    app.style.transform = 'scale(' + scale + ')';
    app.style.marginLeft = Math.max(0, (window.innerWidth - PAGE_W * scale) / 2) + 'px';
    app.style.marginTop = Math.max(0, (window.innerHeight - PAGE_H * scale) / 2) + 'px';
  }

  function mount(Component, props) {
    pageTemplate = document.getElementById('page');
    expandLayout(pageTemplate.content);
    app = document.getElementById('app');
    if (!app) {
      app = document.createElement('div');
      app.id = 'app';
      document.body.appendChild(app);
    }
    instance = new Component(props || {});
    render();
    fitToWindow();
    window.addEventListener('resize', fitToWindow);
    if (typeof instance.componentDidMount === 'function') instance.componentDidMount();
  }

  window.COS3 = Object.assign(window.COS3 || {}, { mount, layouts: (window.COS3 && window.COS3.layouts) || {} });
})();
