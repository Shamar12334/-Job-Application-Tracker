// Shared front-end for the CRUD pages.
// Each page puts its settings in <script id="crud-config" type="application/json">:
//   { resource: "companies", idKey: "company_id", label: "company",
//     deleteWarning: "...", fields: [ { name, label, type, required, options, ... } ] }
// Rows carry their data in data-record='{...}', and buttons use data-action.
(() => {
  'use strict';

  // ---------- toasts ----------
  const toastBox = document.getElementById('toasts');
  function toast(message, kind = 'success') {
    if (!toastBox) return;
    const el = document.createElement('div');
    el.className = `toast toast-${kind}`;
    el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    el.textContent = message;
    toastBox.appendChild(el);
    setTimeout(() => el.classList.add('toast-hide'), 3500);
    setTimeout(() => el.remove(), 4000);
  }

  // Show a message that was saved just before the page reloaded.
  try {
    const flash = sessionStorage.getItem('flash');
    if (flash) {
      sessionStorage.removeItem('flash');
      toast(flash);
    }
  } catch (_) { /* storage unavailable: skip */ }

  function reloadWith(message) {
    try { sessionStorage.setItem('flash', message); } catch (_) { /* ignore */ }
    window.location.reload();
  }

  // ---------- table search ----------
  document.querySelectorAll('[data-search]').forEach((input) => {
    const table = document.querySelector(input.dataset.search);
    if (!table) return;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      let shown = 0;
      table.querySelectorAll('tbody tr[data-record]').forEach((row) => {
        const match = row.textContent.toLowerCase().includes(q);
        row.hidden = !match;
        if (match) shown += 1;
      });
      const empty = table.querySelector('.no-results');
      if (empty) empty.hidden = shown !== 0 || q === '';
    });
  });

  const cfgEl = document.getElementById('crud-config');
  if (!cfgEl) return;
  const cfg = JSON.parse(cfgEl.textContent);

  const dialog = document.getElementById('crud-dialog');
  const form = dialog.querySelector('form');
  const fieldsBox = dialog.querySelector('.form-fields');
  const titleEl = dialog.querySelector('.dialog-title');
  const errorEl = dialog.querySelector('.form-error');
  const submitBtn = dialog.querySelector('[type="submit"]');
  let editingId = null;

  const confirmDialog = document.getElementById('confirm-dialog');

  // ---------- building the form ----------
  function displayValue(field, value) {
    if (value === null || value === undefined) return '';
    if (field.type === 'tags') return Array.isArray(value) ? value.join(', ') : String(value);
    if (field.type === 'json') return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    return String(value);
  }

  function buildField(field, record) {
    const id = `f-${field.name}`;
    const wrap = document.createElement('div');
    wrap.className = `field${field.wide ? ' field-wide' : ''}${field.type === 'checkbox' ? ' field-check' : ''}`;
    const value = record ? record[field.name] : field.default;

    let input;
    if (field.type === 'select') {
      input = document.createElement('select');
      const blank = document.createElement('option');
      blank.value = '';
      blank.textContent = field.required ? `Choose ${field.label.toLowerCase()}…` : '—';
      if (field.required) blank.disabled = true;
      input.appendChild(blank);
      (field.options || []).forEach((opt) => {
        const o = document.createElement('option');
        o.value = String(opt.value);
        o.textContent = opt.label;
        input.appendChild(o);
      });
      input.value = value === null || value === undefined ? '' : String(value);
    } else if (field.type === 'textarea' || field.type === 'json') {
      input = document.createElement('textarea');
      input.rows = field.type === 'json' ? 5 : 3;
      if (field.type === 'json') input.spellcheck = false;
      input.value = displayValue(field, value);
    } else if (field.type === 'checkbox') {
      input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = Boolean(value);
    } else {
      input = document.createElement('input');
      input.type = field.type === 'tags' ? 'text' : (field.type || 'text');
      if (field.type === 'number') input.step = field.step || '1';
      input.value = displayValue(field, value);
    }
    input.id = id;
    input.name = field.name;
    if (field.required) input.required = true;
    if (field.placeholder) input.placeholder = field.placeholder;
    if (field.maxlength) input.maxLength = field.maxlength;

    const label = document.createElement('label');
    label.htmlFor = id;
    label.textContent = field.label;
    if (field.required) {
      const star = document.createElement('span');
      star.className = 'required';
      star.textContent = ' *';
      label.appendChild(star);
    }

    if (field.type === 'checkbox') {
      wrap.append(input, label);
    } else {
      wrap.append(label, input);
    }
    if (field.hint) {
      const hint = document.createElement('small');
      hint.className = 'hint';
      hint.textContent = field.hint;
      wrap.appendChild(hint);
    }
    return wrap;
  }

  function openForm(record) {
    editingId = record ? record[cfg.idKey] : null;
    titleEl.textContent = record ? `Edit ${cfg.label}` : `Add ${cfg.label}`;
    submitBtn.textContent = record ? 'Save changes' : `Add ${cfg.label}`;
    errorEl.hidden = true;
    fieldsBox.replaceChildren(...cfg.fields.map((f) => buildField(f, record)));
    dialog.showModal();
    const first = fieldsBox.querySelector('input, select, textarea');
    if (first) first.focus();
  }

  // ---------- reading the form ----------
  function readForm() {
    const body = {};
    for (const field of cfg.fields) {
      const input = form.elements[field.name];
      if (field.type === 'checkbox') {
        body[field.name] = input.checked;
        continue;
      }
      const raw = input.value.trim();
      if (raw === '') {
        body[field.name] = null;
      } else if (field.type === 'number' || field.numeric) {
        body[field.name] = Number(raw);
      } else if (field.type === 'tags') {
        const list = raw.split(',').map((s) => s.trim()).filter(Boolean);
        body[field.name] = list.length ? list : null;
      } else if (field.type === 'json') {
        try {
          body[field.name] = JSON.parse(raw);
        } catch (_) {
          throw new Error(`${field.label} must be valid JSON, e.g. {"round": 1, "notes": "went well"}`);
        }
      } else {
        body[field.name] = raw;
      }
    }
    return body;
  }

  async function send(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.hidden = true;
    let body;
    try {
      body = readForm();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      return;
    }
    submitBtn.disabled = true;
    try {
      const base = `/api/${cfg.resource}`;
      if (editingId === null) {
        await send('POST', base, body);
        reloadWith(`${capitalize(cfg.label)} added`);
      } else {
        await send('PUT', `${base}/${editingId}`, body);
        reloadWith(`${capitalize(cfg.label)} updated`);
      }
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      submitBtn.disabled = false;
    }
  });

  dialog.querySelectorAll('[data-close]').forEach((btn) =>
    btn.addEventListener('click', () => dialog.close()));

  // ---------- confirm delete ----------
  function confirmDelete(name) {
    return new Promise((resolve) => {
      confirmDialog.querySelector('.confirm-title').textContent = `Delete ${name}?`;
      confirmDialog.querySelector('.confirm-text').textContent =
        cfg.deleteWarning || 'This cannot be undone.';
      const yes = confirmDialog.querySelector('[data-confirm]');
      const done = (answer) => {
        yes.removeEventListener('click', onYes);
        confirmDialog.removeEventListener('close', onClose);
        resolve(answer);
      };
      const onYes = () => { done(true); confirmDialog.close(); };
      const onClose = () => done(false);
      yes.addEventListener('click', onYes);
      confirmDialog.addEventListener('close', onClose);
      confirmDialog.showModal();
    });
  }
  confirmDialog.querySelectorAll('[data-close]').forEach((btn) =>
    btn.addEventListener('click', () => confirmDialog.close()));

  // ---------- button wiring ----------
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === 'create') {
      openForm(null);
      return;
    }
    const row = btn.closest('[data-record]');
    if (!row) return;
    const record = JSON.parse(row.dataset.record);
    if (action === 'edit') {
      openForm(record);
    } else if (action === 'delete') {
      const name = record[cfg.nameKey] || `this ${cfg.label}`;
      if (!(await confirmDelete(name))) return;
      try {
        await send('DELETE', `/api/${cfg.resource}/${record[cfg.idKey]}`);
        if (cfg.afterDelete) {
          // On a detail page the record is gone, so go back to the list.
          try { sessionStorage.setItem('flash', `${capitalize(cfg.label)} deleted`); } catch (_) { /* ignore */ }
          window.location.href = cfg.afterDelete;
        } else {
          reloadWith(`${capitalize(cfg.label)} deleted`);
        }
      } catch (err) {
        toast(err.message, 'error');
      }
    }
  });

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
})();
