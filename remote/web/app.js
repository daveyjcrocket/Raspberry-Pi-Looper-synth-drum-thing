// LiveLoopSynth web remote. Talks JSON over /ws to remote/server.py, which relays to Pd.
// Pd -> page: {u: [{n: name, k: 'value'|'label'|'color', v}], pd: bool}
// page -> Pd: {n: name, v: number | 'bang'}   (names must be in remote/names.json "in")
'use strict';

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const SVGNS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };

const INSTRUMENTS = ['GMRock kit', 'Virtuosity kit', 'Drums 3', 'Drums 4', 'Lead synth', 'FM 1', 'FM 2', 'FM 3',
  'Lead synth 2', 'FM 4', 'FM 5', 'FM 6', 'Synth three', 'FM 7', 'FM 8', 'FM 9', 'Moog bass', 'Acid bass',
  'Reese bass', 'Jazz organ', 'Gospel organ', 'Church organ', 'Supersaw lead', 'Warm pad', 'Pluck'];
const LAYER_COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)'];
const STATES = ['ready', 'rec', 'dub', 'play', 'fade', 'stop'];

// ---------------- connection ----------------
const listeners = new Map();
function on(name, kind, fn) {
  const key = name + '|' + kind;
  if (!listeners.has(key)) listeners.set(key, []);
  listeners.get(key).push(fn);
}
function dispatch(u) {
  for (const fn of listeners.get(u.n + '|' + u.k) || []) fn(u.v);
}

let ws = null, pdUp = false;
function setConn() {
  const el = $('#conn'), open = ws && ws.readyState === 1;
  el.className = 'conn ' + (open && pdUp ? 'ok' : open ? '' : 'bad');
  $('#conn-text').textContent = open ? (pdUp ? 'connected' : 'Pd is not running') : 'no connection';
}
function connect() {
  ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onopen = setConn;
  ws.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if ('pd' in d) { pdUp = d.pd; setConn(); }
    if (d.u) d.u.forEach(dispatch);
  };
  ws.onclose = () => { setConn(); setTimeout(connect, 1000); };
}
function send(name, v) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ n: name, v }));
}
// continuous controls: at most one message per name every 30 ms, always ending on the last value
const pending = new Map();
let flushTimer = 0;
function sendSoon(name, v) {
  pending.set(name, v);
  if (!flushTimer) flushTimer = setTimeout(() => {
    flushTimer = 0;
    for (const [n, val] of pending) send(n, val);
    pending.clear();
  }, 30);
}

// ---------------- widgets ----------------
// Knob: 270 degree arc. Drag up/down (or sideways), wheel, arrow keys; double-click = default.
function arc(cx, cy, r, a0, a1) {
  const p = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}
function knob(parent, o) {
  const { min = 0, max = 127, def = min, sendTo, listen = [], color, fmt = (v) => Math.round(v), small } = o;
  const A0 = Math.PI * 0.75, SWEEP = Math.PI * 1.5;
  const wrap = h('div', 'knob' + (small ? ' sm' : ''));
  if (color) wrap.style.setProperty('--c', color);
  const s = svg('svg', { viewBox: '0 0 66 66', tabindex: 0, role: 'slider', 'aria-valuemin': min, 'aria-valuemax': max });
  if (small) { s.style.width = s.style.height = '54px'; }
  s.append(svg('path', { class: 'k-bg', d: arc(33, 33, 27, A0, A0 + SWEEP) }));
  const val = svg('path', { class: 'k-val' });
  s.append(val, svg('circle', { class: 'k-cap', cx: 33, cy: 33, r: 19 }));
  const ptr = svg('line', { class: 'k-ptr' });
  s.append(ptr);
  const lab = h('div', 'knob-label', o.label || '');
  const num = h('div', 'knob-value');
  wrap.append(s, lab, num);
  parent.append(wrap);

  let v = def, dragging = false;
  function draw() {
    const t = (v - min) / (max - min), a = A0 + t * SWEEP;
    val.setAttribute('d', t > 0.001 ? arc(33, 33, 27, A0, a) : '');
    ptr.setAttribute('x1', 33 + 8 * Math.cos(a)); ptr.setAttribute('y1', 33 + 8 * Math.sin(a));
    ptr.setAttribute('x2', 33 + 16 * Math.cos(a)); ptr.setAttribute('y2', 33 + 16 * Math.sin(a));
    num.textContent = fmt(v);
    s.setAttribute('aria-valuenow', Math.round(v));
  }
  function user(nv) {
    nv = clamp(nv, min, max);
    if (nv === v) return;
    v = nv; draw(); sendSoon(sendTo, Math.round(v * 1000) / 1000);
  }
  let y0 = 0, x0 = 0, v0 = 0;
  s.addEventListener('pointerdown', (e) => {
    dragging = true; s.setPointerCapture(e.pointerId);
    y0 = e.clientY; x0 = e.clientX; v0 = v; e.preventDefault();
  });
  s.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const px = (y0 - e.clientY) + (e.clientX - x0) * 0.5;
    user(v0 + px / (e.shiftKey ? 800 : 180) * (max - min));
  });
  const end = () => { dragging = false; };
  s.addEventListener('pointerup', end); s.addEventListener('pointercancel', end);
  s.addEventListener('dblclick', () => user(def));
  s.addEventListener('wheel', (e) => { e.preventDefault(); user(v - Math.sign(e.deltaY) * (max - min) / 64); }, { passive: false });
  s.addEventListener('keydown', (e) => {
    const step = (max - min) / (e.shiftKey ? 127 : 32);
    if (e.key === 'ArrowUp' || e.key === 'ArrowRight') { user(v + step); e.preventDefault(); }
    if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') { user(v - step); e.preventDefault(); }
  });
  for (const n of listen) on(n, 'value', (x) => { if (!dragging && typeof x === 'number') { v = clamp(x, min, max); draw(); } });
  draw();
  return {
    el: wrap,
    setLabel(t) { lab.textContent = t; wrap.classList.toggle('dim', t === '-' || t === ''); s.setAttribute('aria-label', t); },
  };
}

// Vertical fader: touch anywhere on it to jump there, then drag.
function fader(parent, o) {
  const { min = 0, max = 1, sendTo, listen = [] } = o;
  const f = h('div', 'fader'); f.tabIndex = 0; f.setAttribute('role', 'slider');
  const track = h('div', 'track'), fill = h('div', 'fill'), thumb = h('div', 'thumb');
  track.append(fill); f.append(track, thumb);
  const read = h('div', 'fader-val');
  parent.append(f, read);
  let v = max, dragging = false;
  function draw() {
    const t = (v - min) / (max - min);
    fill.style.height = (t * 100) + '%';
    thumb.style.bottom = `calc(6px + ${t} * (100% - 12px))`;
    read.textContent = Math.round(t * 100);
  }
  function fromY(y) {
    const r = f.getBoundingClientRect();
    return min + clamp((r.bottom - 6 - y) / (r.height - 12), 0, 1) * (max - min);
  }
  function user(nv) { nv = clamp(nv, min, max); if (nv === v) return; v = nv; draw(); sendSoon(sendTo, Math.round(v * 1000) / 1000); }
  f.addEventListener('pointerdown', (e) => { dragging = true; f.setPointerCapture(e.pointerId); user(fromY(e.clientY)); e.preventDefault(); });
  f.addEventListener('pointermove', (e) => { if (dragging) user(fromY(e.clientY)); });
  const end = () => { dragging = false; };
  f.addEventListener('pointerup', end); f.addEventListener('pointercancel', end);
  f.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') { user(v + (max - min) / 20); e.preventDefault(); }
    if (e.key === 'ArrowDown') { user(v - (max - min) / 20); e.preventDefault(); }
  });
  for (const n of listen) on(n, 'value', (x) => { if (!dragging && typeof x === 'number') { v = clamp(x, min, max); draw(); } });
  draw();
}

// Buttons that send a bang: fire on press, not on release, so REC/PLAY/TAP land on the beat.
function bangButton(btn, name) {
  btn.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    send(name, 'bang');
    btn.classList.add('hit'); setTimeout(() => btn.classList.remove('hit'), 120);
  });
  btn.addEventListener('click', (e) => { if (e.detail === 0) send(name, 'bang'); });   // keyboard
}

// ---------------- build the page ----------------
document.body.prepend(Object.assign(svg('svg', { width: 0, height: 0, style: 'position:absolute' }), {
  innerHTML: '<defs><radialGradient id="capgrad" cx="40%" cy="30%" r="80%"><stop offset="0" stop-color="#3a404d"/><stop offset="1" stop-color="#1a1d24"/></radialGradient></defs>',
}));

$$('[data-bang]').forEach((b) => bangButton(b, b.dataset.bang));

// switches: send to the control's receive name (name-r) unless data-send says otherwise
$$('[data-tgl]').forEach((inp) => {
  const name = inp.dataset.tgl, to = inp.dataset.send || name + '-r';
  inp.addEventListener('change', () => send(to, inp.checked ? 1 : 0));
  on(name, 'value', (x) => { inp.checked = !!x; });
  if (inp.dataset.send) on(inp.dataset.send, 'value', (x) => { inp.checked = !!x; });
});

// looper state, hint, position, facts
on('looper-state', 'value', (s) => {
  document.body.dataset.state = s;
  document.body.style.setProperty('--st', `var(--st-${STATES[s] || 'ready'})`);
});
on('looper-cnv', 'label', (t) => { $('#state-word').textContent = t; });
on('looper-hint', 'label', (t) => { $('#hint').textContent = t; });
on('loop-pos', 'value', (x) => { $('#pos').style.width = (clamp(x, 0, 1) * 100) + '%'; });
on('loop-len-s', 'value', (x) => { $('#len').textContent = x ? x.toFixed(1) : '0'; });
on('looper-layers', 'value', (x) => { $('#layers').textContent = x; });

// tempo
const tap = $('#tap');
on('tap-led', 'color', (c) => { tap.classList.toggle('lit', c[0] !== '#555555'); });
const bpm = $('#bpm');
let bpmNow = 0;
const showBpm = (x) => { bpmNow = x; if (document.activeElement !== bpm) bpm.value = Math.round(x); };
on('tempo-bpm-gui', 'value', showBpm);
on('tempo-set', 'value', showBpm);
const setBpm = (x) => { x = clamp(Math.round(x) || 0, 0, 300); showBpm(x); send('tempo-bpm-gui', x); };
bpm.addEventListener('change', () => setBpm(+bpm.value));
bpm.addEventListener('keydown', (e) => { if (e.key === 'Enter') bpm.blur(); });

// steppers
let keepN = 1, thr = -40;
on('keepN', 'value', (x) => { keepN = x; $('#keepN').textContent = x; });
on('keepN-gui', 'value', (x) => { keepN = x; $('#keepN').textContent = x; });
on('looper-thr', 'value', (x) => { thr = x; $('#thr').textContent = x; });
const steps = {
  tempo: (d) => setBpm(bpmNow ? bpmNow + d : 120),       // from free time (0), start at 120
  keepN: (d) => send('keepN-gui', clamp(keepN + d, 1, 7)),
  thr: (d) => send('looper-thr-r', clamp(thr + d, -80, 0)),
};
$$('[data-step]').forEach((b) => b.addEventListener('click', () => steps[b.dataset.step](+b.dataset.d)));
on('knob-learn-cnv', 'label', (t) => { $('#learn').textContent = t; });

// instrument
const bank = $('#bank');
INSTRUMENTS.forEach((n, i) => bank.append(new Option(`${i}  ${n}`, i)));
let bankNow = 0;
on('bankSelect', 'value', (x) => { bankNow = x; bank.value = x; });
on('instr-cnv', 'label', (t) => { $('#instr').textContent = t; });
bank.addEventListener('change', () => send('bankSelect', +bank.value));
$$('[data-bank]').forEach((b) => b.addEventListener('click', () => send('bankSelect', (bankNow + +b.dataset.bank + 25) % 25)));

// layers
const grid = $('#layers-grid');
for (let n = 1; n <= 8; n++) {
  const L = h('div', 'layer'); L.dataset.st = 'empty';
  L.style.setProperty('--c', LAYER_COLORS[(n - 1) % 4]);
  const top = h('div', 'layer-top');
  const clear = h('button', 'clear', '×'); clear.setAttribute('aria-label', `clear layer ${n}`);
  top.append(h('span', 'layer-num', n), clear);
  const chip = h('div', 'chip', 'empty');
  const mute = h('button', 'mute', 'mute'); mute.setAttribute('aria-label', `mute layer ${n}`);
  L.append(top, chip, mute);
  fader(L, { sendTo: `lp-vol-${n}-r`, listen: [`lp-vol-${n}`, `lp-vol-${n}-r`] });
  grid.append(L);
  bangButton(mute, `lp-trig-${n}-r`);
  clear.addEventListener('click', () => send(`clear-${n}-r`, 'bang'));
  on(`lyr-${n}-cnv`, 'label', (t) => {
    const sel = t.startsWith('>'), word = t.replace(/^>\s*/, '');
    L.classList.toggle('sel', sel); L.dataset.st = word; chip.textContent = word;
    mute.textContent = word === 'muted' ? 'unmute' : 'mute';
  });
}

// knob pages
const synthPage = $('#page-synth'), fxPage = $('#page-fx');
const titles = { synth: '', fx: '' };
let page = 'synth';
function showPage(p) {
  page = p;
  synthPage.hidden = p !== 'synth'; fxPage.hidden = p !== 'fx';
  $$('.tab').forEach((t) => t.classList.toggle('on', t.dataset.page === p));
  $('#page-title').textContent = titles[p];
}
$$('.tab').forEach((t) => t.addEventListener('click', () => showPage(t.dataset.page)));
const short = (t) => t.split(' - ').slice(1).join(' - ') || t;
on('knobtitle-synth', 'label', (t) => { titles.synth = short(t); showPage(page); });
on('knobtitle-fx', 'label', (t) => { titles.fx = short(t); showPage(page); });
on('knob-page', 'value', (x) => {
  const p = x === 2 ? 'fx' : 'synth';
  $$('.tab').forEach((t) => t.classList.toggle('live-on', t.dataset.page === p));
  showPage(p);
});
const FX_LABELS = ['mic verb', 'mic delay', 'in 2 verb', 'in 2 delay', 'synth verb', 'synth delay', 'delay time', 'feedback'];
for (let n = 1; n <= 8; n++) {
  const c = LAYER_COLORS[(n - 1) % 4];
  const k = knob(synthPage, { sendTo: `knob-${n}-r`, listen: [`knob-${n}`, `knob-${n}-r`], color: c, label: '-' });
  k.setLabel('-');
  on(`knob-${n}-r`, 'label', (t) => k.setLabel(t));
  const f = knob(fxPage, { sendTo: `fxin-${n}-r`, listen: [`fxin-${n}`, `fxin-${n}-r`], color: c, label: FX_LABELS[n - 1] });
  on(`fxin-${n}-r`, 'label', (t) => f.setLabel(t));
}
showPage('synth');

// master
const mk = $('#master-knobs');
const pct = (v) => Math.round(v / 127 * 100);
// gains as Pd uses them: main 0-1 (starts at 1), inputs 0-2 (start at 2); Pd doesn't report these until they change
knob(mk, { sendTo: 'mainVol', listen: ['mainVol'], label: 'main', small: true, max: 1, def: 1, fmt: (v) => Math.round(v * 100) });
knob(mk, { sendTo: 'l-in-vol', listen: ['l-in-vol'], label: 'in 1', small: true, max: 2, def: 2, fmt: (v) => Math.round(v * 50) });
knob(mk, { sendTo: 'r-in-vol', listen: ['r-in-vol'], label: 'in 2', small: true, max: 2, def: 2, fmt: (v) => Math.round(v * 50) });
knob(mk, { sendTo: 'fx-cutoff-r', listen: ['fx-cutoff', 'fx-cutoff-r'], label: 'cutoff', small: true, color: 'var(--c1)', fmt: pct });
knob(mk, { sendTo: 'fx-retrig-r', listen: ['fx-retrig', 'fx-retrig-r'], label: 'retrigger', small: true, color: 'var(--c2)', fmt: pct });
knob(mk, { sendTo: 'reverb-predelay-r', listen: ['reverb-predelay'], label: 'pre-delay', small: true, color: 'var(--c4)', min: 0, max: 250, def: 20, fmt: (v) => Math.round(v) + ' ms' });
// AI drummer: on/off and auto fills are data-tgl switches, pause / fill / rebonk and the corrections are data-bang buttons
for (const [name, label, def] of [['level', 'level', 0.5], ['density', 'density', 0.5], ['humanize', 'humanize', 0.3]]) {
  knob($('#drummer-knobs'), { sendTo: `drummer-${name}-r`, listen: [`drummer-${name}`], label, small: true, max: 1, def, fmt: (v) => Math.round(v * 100) });
}
// the status line, and what it heard (tempo, feel)
for (const [name, id] of [['drummer-cnv', '#drummer'], ['drummer-feel-cnv', '#drummer-feel']]) {
  const el = $(id);
  on(name, 'label', (t) => { el.textContent = t; });
  on(name, 'color', (c) => {
    if (typeof c[0] === 'string') el.style.background = c[0];
    if (typeof c[1] === 'string') el.style.color = c[1];
  });
}

const meter = (id) => { const el = $(id); return (db) => { el.style.height = (clamp((db + 60) / 66, 0, 1) * 100) + '%'; }; };
on('l-in-sig', 'value', meter('#m-in1'));
on('r-in-sig', 'value', meter('#m-in2'));
on('l-out-db', 'value', meter('#m-out'));

// drum pads (display only: they light up when the LX25+ pads are hit; in AI drummer mode they show its controls)
const pads = $('#pads');
for (let n = 1; n <= 8; n++) {
  const p = h('div', 'pad', '-');
  pads.append(p);
  let t = 0;
  on(`pad-${n}-cnv`, 'label', (x) => { p.textContent = x; });
  on(`pad-${n}-cnv`, 'color', (c) => {
    if (typeof c[0] !== 'string') return;
    p.style.setProperty('--pad', c[0]);
    if (typeof c[1] === 'string') p.style.setProperty('--pad-fg', c[1]);
    const flash = c[1] === '#ffffff';         // the flash color; the resting colors never use white text
    p.classList.toggle('flash', flash);
    clearTimeout(t); if (flash) t = setTimeout(() => p.classList.remove('flash'), 400);
  });
}

connect();
setConn();
