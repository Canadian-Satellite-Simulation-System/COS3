/*
 * COS3 – display helpers for the command parameter form (pure functions, no DOM, no fetch).
 *
 *   COS3.commandForm.defaults(definition)       -> { name: string } starting values
 *   COS3.commandForm.toField(param, value, err) -> what the page template needs for one parameter
 *   COS3.commandForm.summary(definition)        -> e.g. "2 parameters · 1 required"
 *
 * `definition` and `param` are what GET /api/commands/{target}/{name} returns.
 * No validation here: values are checked only on the server (commands/validation.py),
 * through COS3.api.validateCommand().
 */
(function () {
  'use strict';

  const INTEGER_TYPES = ['INT', 'UINT'];

  function maxBytes(p) {
    return p.bit_size > 0 ? Math.floor(p.bit_size / 8) : null;
  }

  function defaults(definition) {
    return Object.fromEntries(definition.parameters.map((p) => [p.name, p.default == null ? '' : String(p.default)]));
  }

  function typeLabel(p) {
    if (p.data_type === 'BLOCK' || p.data_type === 'STRING') {
      const limit = maxBytes(p);
      return `${p.data_type} · ${limit != null ? `up to ${limit} bytes` : 'variable size'}`;
    }
    return p.bit_size ? `${p.data_type} · ${p.bit_size}-bit` : p.data_type;
  }

  function rangeLabel(p) {
    if (p.states || (p.minimum == null && p.maximum == null)) return null;
    const unit = p.units ? ` ${p.units}` : '';
    if (p.minimum != null && p.maximum != null) return `${p.minimum} to ${p.maximum}${unit}`;
    return p.minimum != null ? `≥ ${p.minimum}${unit}` : `≤ ${p.maximum}${unit}`;
  }

  function defaultLabel(p) {
    if (p.default == null || p.default === '') return null;
    if (p.states) {
      const name = Object.keys(p.states).find((k) => String(p.states[k]) === String(p.default));
      return name ? `${name} (${p.default})` : String(p.default);
    }
    return `${p.default}${p.units ? ` ${p.units}` : ''}`;
  }

  // Everything the template shows for one parameter
  function toField(p, value, error) {
    const hazardous = new Set(p.hazardous_states || []);
    const field = {
      id: `param-${p.name}`,
      name: p.name,
      required: !!p.required,
      typeLabel: typeLabel(p),
      description: p.description || '',
      range: rangeLabel(p),
      units: p.units || null,
      defaultText: defaultLabel(p),
      conversion: p.conversion || null,
      value: value == null ? '' : String(value),
      error: error || null,
      errorId: `param-${p.name}-error`,
      invalid: error ? 'true' : null
    };

    if (p.states) {
      field.isSelect = true;
      field.options = Object.entries(p.states).map(([name, v]) => ({
        value: String(v),
        label: `${name} (${v})${hazardous.has(name) ? ' · HAZARDOUS' : ''}`,
        sel: String(v) === field.value
      }));
      return field;
    }

    field.isInput = true;
    if (INTEGER_TYPES.includes(p.data_type)) {
      Object.assign(field, {type: 'text', inputmode: 'numeric', placeholder: 'Whole number'});
    } else if (p.data_type === 'FLOAT') {
      Object.assign(field, {type: 'text', inputmode: 'decimal', placeholder: 'Number'});
    } else if (p.data_type === 'BLOCK') {
      Object.assign(field, {type: 'text', inputmode: 'text', placeholder: 'Hex bytes, e.g. 0A FF 3C', mono: true});
    } else {
      Object.assign(field, {type: 'text', inputmode: 'text', placeholder: ''});
    }
    return field;
  }

  function summary(definition) {
    const n = definition.parameters.length;
    if (n === 0) return 'No parameters';
    const required = definition.parameters.filter((p) => p.required).length;
    return `${n} parameter${n === 1 ? '' : 's'}${required ? ` · ${required} required` : ' · all optional'}`;
  }

  window.COS3 = window.COS3 || {};
  window.COS3.commandForm = {defaults, toField, summary};
})();
