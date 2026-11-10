#!/usr/bin/env node
// Check a web page mechanically, then leave screenshots to look at.
//
//   page-check.mjs URL_OR_FILE -o OUTDIR [--widths 1440x900,390x844] [--stops 5]
//                  [--budget-kb N] [--contrast-area 10] [--no-contrast]
//                  [--wait-ms 600] [--no-sandbox]
//   page-check.mjs --self-test
//
// For each width: loads the page in headless Chrome and records console
// errors, failed requests and broken images, in the page and in the frames it
// embeds. Measures horizontal overflow, text that is invisible or cut off, and
// the contrast of every text block against the pixels really behind it (the
// text is hidden and the page captured twice per screenful). Scrolls down the
// whole page so that lazy content loads, adds up what was transferred, takes a
// screenshot at each scroll stop, and checks at each stop whether the page
// moves at rest and whether it still moves under prefers-reduced-motion.
//
// Writes OUTDIR/report.json and OUTDIR/<width>x<height>-<stop>.png, replacing
// the screenshots an earlier run left there. Exit 0 when nothing is at error
// level, 1 when something is, 2 when the check could not run (bad arguments,
// no Chrome, Chrome died). Needs Node 22 or later and Chrome or Chromium (set
// CHROME to choose the binary). No npm packages.
import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import zlib from 'node:zlib';

function findChrome() {
  const which = (n) => {
    if (n.includes('/')) return fs.existsSync(n) ? n : null;
    const r = spawnSync('sh', ['-c', 'command -v "$1"', 'sh', n], { encoding: 'utf8' });
    return r.status === 0 && r.stdout.trim() ? r.stdout.trim() : null;
  };
  const chosen = process.env.CHROME;
  if (chosen) {
    const found = which(chosen);
    if (!found) throw new Error(`CHROME is set to "${chosen}", which was not found`);
    return found;
  }
  for (const n of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']) { const found = which(n); if (found) return found; }
  throw new Error('no Chrome or Chromium found; set CHROME to the binary');
}

// A minimal Chrome DevTools Protocol client over Node's built-in WebSocket.
// Every call has a time limit, and all of them fail at once if Chrome goes away:
// a promise that never settles would let the process end with nothing said.
class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = new Set(); this.closed = null;
    ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject, timer } = this.pending.get(m.id); this.pending.delete(m.id); clearTimeout(timer);
        m.error ? reject(new Error(`${m.error.message} (${m.error.code})`)) : resolve(m.result);
      } else if (m.method) {
        for (const h of this.handlers) h(m.method, m.params, m.sessionId);
      }
    });
    const drop = () => {
      if (this.closed) return;
      this.closed = new Error('Chrome went away before the check finished');
      for (const { reject, timer } of this.pending.values()) { clearTimeout(timer); reject(this.closed); }
      this.pending.clear();
    };
    ws.addEventListener('close', drop); ws.addEventListener('error', drop);
  }
  send(method, params = {}, sessionId, timeoutMs = 30000) {
    if (this.closed) return Promise.reject(this.closed);
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`Chrome did not answer ${method} in ${timeoutMs / 1000} s (a page stuck in a script does this)`)); }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  on(fn) { this.handlers.add(fn); return () => this.handlers.delete(fn); }
}

// What must not outlive the run: Chrome with its helpers, and the temporary
// directories. Chrome gets its own process group so that all of it can be
// killed, and its own TMPDIR so that what it scatters goes with the profile.
const temp = new Set();
let chrome = null;
const killTree = (proc) => { try { process.kill(-proc.pid, 'SIGKILL'); } catch { try { proc.kill('SIGKILL'); } catch {} } };
const removeDir = (dir) => { try { fs.rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch {} };
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, () => {
  if (chrome) killTree(chrome);
  for (const dir of temp) removeDir(dir);
  process.exit(sig === 'SIGINT' ? 130 : 143);
});

async function launch(noSandbox) {
  if (typeof WebSocket === 'undefined') throw new Error('this Node has no built-in WebSocket: Node 22 or later is needed');
  const binary = findChrome();
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'page-check-')); temp.add(base);
  const profile = path.join(base, 'profile'), tmp = path.join(base, 'tmp');
  fs.mkdirSync(profile); fs.mkdirSync(tmp);
  const args = ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--hide-scrollbars', '--mute-audio', ...(noSandbox ? ['--no-sandbox'] : []), 'about:blank'];
  let proc = null;
  const gone = () => new Promise((resolve) => (proc.exitCode !== null || proc.signalCode !== null ? resolve() : proc.once('exit', resolve)));
  const discard = async () => {
    if (proc && proc.pid) { killTree(proc); await Promise.race([gone(), sleep(2000)]); }
    removeDir(base); await sleep(200); removeDir(base);
    temp.delete(base); chrome = null;
  };
  try {
    proc = spawn(binary, args, { stdio: ['ignore', 'ignore', 'pipe'], detached: process.platform !== 'win32', env: { ...process.env, TMPDIR: tmp } });
    chrome = proc;
    const url = await new Promise((resolve, reject) => {
      let buf = '';
      const timer = setTimeout(() => reject(new Error('Chrome did not open its DevTools port in 20 s:\n' + buf.slice(-600))), 20000);
      proc.stderr.on('data', (d) => {
        buf = (buf + d).slice(-4000);
        const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
        if (m) { clearTimeout(timer); resolve(m[1]); }
      });
      proc.on('error', (e) => { clearTimeout(timer); reject(new Error(`could not start ${binary}: ${e.message}`)); });
      proc.on('exit', (code, sig) => { clearTimeout(timer); reject(new Error(`${binary} exited with ${code ?? sig} before opening its DevTools port` + (buf ? ':\n' + buf.slice(-600) : ''))); });
    });
    const ws = new WebSocket(url);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', () => reject(new Error('could not connect to Chrome'))); });
    const cdp = new Cdp(ws);
    const close = async () => {   // ask Chrome to leave, then make sure all of it did
      await Promise.race([cdp.send('Browser.close', {}, undefined, 3000).catch(() => {}), sleep(3000)]);
      await Promise.race([gone(), sleep(3000)]);
      try { ws.close(); } catch {}
      await discard();
    };
    return { cdp, close };
  } catch (e) { await discard(); throw e; }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Decode the PNG Chrome returns (8-bit RGB or RGBA, not interlaced) to raw pixels.
function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error('not a PNG');
  let pos = 8, w = 0, h = 0, bpp = 0; const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos), type = buf.toString('latin1', pos + 4, pos + 8), data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      w = data.readUInt32BE(0); h = data.readUInt32BE(4);
      if (data[8] !== 8 || (data[9] !== 2 && data[9] !== 6) || data[12] !== 0) throw new Error(`PNG kind not handled (depth ${data[8]}, colour ${data[9]}, interlace ${data[12]})`);
      bpp = data[9] === 6 ? 4 : 3;
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    pos += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat)), stride = w * bpp, px = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)), o = y * stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? px[o + x - bpp] : 0, b = y ? px[o - stride + x] : 0, c = x >= bpp && y ? px[o - stride + x - bpp] : 0;
      let v = line[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      px[o + x] = v & 255;
    }
  }
  return { w, h, bpp, px };
}

// WCAG 2 contrast between two sRGB colours given as 0..255 channels.
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const lum = (r, g, b) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
function contrast(l1, l2) { const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); }
// Large text needs 3:1, the rest 4.5:1 (WCAG 2 AA): 24px, or 18.66px when bold.
const needed = (sizePx, weight) => (sizePx >= 24 || (sizePx >= 18.66 && weight >= 700) ? 3 : 4.5);

// Contrast of one text block against the pixels actually behind it. The text's
// own alpha is applied over every sampled pixel, so see-through text is judged
// against what shows through it. The boxes are in layout pixels and the capture
// may not be (a phone shrinks a page that has no viewport meta), hence the scale.
function blockContrast(img, block, scale) {
  const [r, g, b] = block.rgb, a = block.alpha, ratios = [];
  for (const q of block.rects) {
    const x0 = Math.max(0, Math.floor(q.x * scale)), y0 = Math.max(0, Math.floor(q.y * scale)), x1 = Math.min(img.w, Math.ceil((q.x + q.w) * scale)), y1 = Math.min(img.h, Math.ceil((q.y + q.h) * scale));
    const step = Math.max(1, Math.round(Math.sqrt(((x1 - x0) * (y1 - y0)) / 300)));
    for (let y = y0; y < y1; y += step) for (let x = x0; x < x1; x += step) {
      const i = (y * img.w + x) * img.bpp, pr = img.px[i], pg = img.px[i + 1], pb = img.px[i + 2];
      ratios.push(contrast(lum(a * r + (1 - a) * pr, a * g + (1 - a) * pg, a * b + (1 - a) * pb), lum(pr, pg, pb)));
    }
  }
  return ratios;
}

// Runs in the page: every run of HTML text that is really on screen in the
// viewport, with the boxes of its lines, its colour as the browser resolves it,
// and its size. A line that an ancestor's overflow cuts away, or that something
// else covers from end to end (a fixed header), is not on screen: the pixels
// there belong to something else. Form fields are text too.
const TEXT_BLOCKS = `(() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  if (!document.body) return { vw, blocks: [] };
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgba = (css) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = css; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const clip = (el, r) => {
    let pos = 'static';   // an absolutely positioned box is only clipped by its containing blocks, a fixed one by none
    for (let p = el; p && pos !== 'fixed'; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (pos === 'absolute' && s.position === 'static' && s.transform === 'none') continue;
      if (p !== document.body && p !== document.documentElement) {
        const b = p.getBoundingClientRect();
        if (s.overflowX !== 'visible') { r.l = Math.max(r.l, b.left); r.r = Math.min(r.r, b.right); }
        if (s.overflowY !== 'visible') { r.t = Math.max(r.t, b.top); r.b = Math.min(r.b, b.bottom); }
      }
      pos = s.position;
    }
    r.l = Math.max(r.l, 0); r.t = Math.max(r.t, 0); r.r = Math.min(r.r, vw); r.b = Math.min(r.b, vh);
    return r.r - r.l > 2 && r.b - r.t > 2 ? r : null;
  };
  const rowCovered = (el, r, y) => {   // something unrelated lies over this row of the box from end to end
    for (const f of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const x = r.l + (r.r - r.l) * f, top = document.elementFromPoint(x, y);
      if (!top || top === el || el.contains(top) || top.contains(el)) return false;
      if (!document.elementsFromPoint(x, y).includes(el)) return false;   // it takes no pointer: cannot tell, so measure it
    }
    return true;
  };
  const uncovered = (el, r) => {       // the box, or the bands of it between two rows that nothing covers
    const h = r.b - r.t;
    if (![r.t + 0.5, (r.t + r.b) / 2, r.b - 0.5].some((y) => rowCovered(el, r, y))) return [r];
    const n = Math.max(1, Math.round(h / 2)), ys = Array.from({ length: n + 1 }, (_, i) => r.t + 0.5 + (h - 1) * i / n), free = ys.map((y) => !rowCovered(el, r, y)), parts = [];
    for (let i = 0, start = -1; i <= n; i++) {
      if (free[i] && start < 0) start = i;
      if (start >= 0 && (!free[i] || i === n)) { const end = free[i] ? i : i - 1; if (ys[end] - ys[start] > 2) parts.push({ l: r.l, r: r.r, t: ys[start], b: ys[end] }); start = -1; }
    }
    return parts;
  };
  const out = [], seen = new Map();
  const add = (el, text, boxes, color, s) => {
    let op = 1; for (let p = el; p; p = p.parentElement) op *= parseFloat(getComputedStyle(p).opacity);
    const c = rgba(color); if (op * c[3] < 0.05) return;
    const rects = boxes.map((q) => clip(el, { l: q.left, t: q.top, r: q.right, b: q.bottom })).filter(Boolean).flatMap((q) => uncovered(el, q)).map((q) => ({ x: q.l, y: q.t, w: q.r - q.l, h: q.b - q.t }));
    if (!rects.length) return;
    let b = seen.get(el);
    if (!b) { b = { key: '', text: '', rects: [], rgb: c.slice(0, 3), alpha: op * c[3], size: parseFloat(s.fontSize), weight: parseInt(s.fontWeight, 10) || 400 }; seen.set(el, b); out.push(b); }
    b.text = (b.text + ' ' + text).trim().slice(0, 60); b.rects.push(...rects);
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n.textContent.trim(); if (text.length < 3) continue;
    const el = n.parentElement; if (!el || el.namespaceURI !== 'http://www.w3.org/1999/xhtml' || /^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA|OPTION)$/.test(el.tagName)) continue;
    const s = getComputedStyle(el); if (s.visibility === 'hidden' || s.display === 'none') continue;
    const range = document.createRange(); range.selectNodeContents(n);
    add(el, text, [...range.getClientRects()], s.webkitTextFillColor || s.color, s);
  }
  for (const el of document.querySelectorAll('input, textarea')) {
    if (/^(checkbox|radio|range|color|file|hidden|image)$/.test(el.type)) continue;
    const s = getComputedStyle(el); if (s.visibility === 'hidden' || s.display === 'none') continue;
    const shown = el.value || el.placeholder || ''; if (shown.trim().length < 3) continue;
    const q = el.getBoundingClientRect(), px = (v) => parseFloat(v) || 0;
    const box = { left: q.left + px(s.borderLeftWidth) + px(s.paddingLeft), top: q.top + px(s.borderTopWidth) + px(s.paddingTop), right: q.right - px(s.borderRightWidth) - px(s.paddingRight), bottom: q.bottom - px(s.borderBottomWidth) - px(s.paddingBottom) };
    add(el, el.type === 'password' ? 'a password field' : shown.trim(), [box], el.value ? s.webkitTextFillColor || s.color : getComputedStyle(el, '::placeholder').color, s);
  }
  for (const [el, b] of seen) {
    b.key = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '') + ' "' + b.text + '"';
  }
  return { vw, blocks: out.slice(0, 400) };
})()`;
// Hiding the text must not start the page's own colour transition, or the
// capture would catch the glyphs half faded; nor may showing it again.
const HIDE_TEXT = `(() => {
  const host = document.head || document.documentElement, style = (id, css) => { const s = document.createElement('style'); s.id = id; s.textContent = css; host.appendChild(s); };
  style('__page_check_still', '*, *::before, *::after, ::placeholder { transition: none !important; }');
  void document.documentElement.getBoundingClientRect();
  style('__page_check_hide', '*, *::before, *::after, ::placeholder { color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important; caret-color: transparent !important; text-decoration-color: transparent !important; }');
  return true;
})()`;
const SHOW_TEXT = `(() => {
  document.getElementById('__page_check_hide')?.remove();
  void document.documentElement.getBoundingClientRect();
  document.getElementById('__page_check_still')?.remove();
  return true;
})()`;
// Resolves when the transitions and finite animations now running have ended
// (2 s at most): text caught halfway through its entrance is not its contrast.
const AT_REST = `Promise.race([Promise.all(document.getAnimations().filter((a) => a.playState === 'running' && a.effect && Number.isFinite(a.effect.getComputedTiming().endTime)).map((a) => a.finished.catch(() => 0))), new Promise((r) => setTimeout(r, 2000))]).then(() => true)`;

// Runs in the page. Returns what can be measured without looking.
const MEASURE = `(() => {
  const root = document.documentElement, vw = root.clientWidth, vh = window.innerHeight;
  const label = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')) + ' "' + (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40) + '"';
  const clippedBy = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o !== 'visible' && p.getBoundingClientRect().right <= vw + 1) return true; } return false; };
  const ownText = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(' ');
  const opacity = (el) => { let o = 1; for (let p = el; p; p = p.parentElement) { const s = getComputedStyle(p); if (s.visibility === 'hidden') return 0; o *= parseFloat(s.opacity); } return o; };
  // The viewport takes its overflow from <html>, or from <body> when <html> leaves it visible.
  const ox = getComputedStyle(root).overflowX, viewportX = ox !== 'visible' || !document.body ? ox : getComputedStyle(document.body).overflowX;
  const wide = [], hidden = [], cut = []; let inner = '';
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const s = getComputedStyle(el);
    if (s.position !== 'fixed' && r.right > vw + 1 && !clippedBy(el)) wide.push(label(el) + ' right=' + Math.round(r.right));
    if (!inner && /auto|scroll/.test(s.overflowY) && el.clientHeight >= vh * 0.5 && el.scrollHeight > el.clientHeight + vh * 0.5) inner = label(el).split(' "')[0];
    const text = ownText(el);
    if (text.length >= 12 && r.top < vh && r.bottom > 0 && opacity(el) < 0.05) hidden.push(label(el));
    if (text.length >= 12 && /hidden|clip/.test(s.overflowY) && el.clientHeight >= 8 && el.clientWidth >= 8 && (s.webkitLineClamp || 'none') === 'none' && el.scrollHeight > el.clientHeight + 2) cut.push(label(el) + ' ' + el.scrollHeight + '>' + el.clientHeight);
  }
  const meta = document.querySelector('meta[name="viewport" i]');
  return {
    layoutWidth: vw, pageHeight: root.scrollHeight, scrollWidth: root.scrollWidth, sidewaysClipped: /hidden|clip/.test(viewportX),
    innerScroller: root.scrollHeight <= vh + 1 ? inner : '', viewportMeta: meta ? meta.content : null, iconLinked: !!document.querySelector('link[rel~="icon" i]'),
    wide: wide.slice(0, 8), hiddenAtRest: hidden.slice(0, 8), cutText: cut.slice(0, 8),
    title: document.title, lang: root.lang || '',
  };
})()`;
const BROKEN = `[...(document.images || [])].filter((i) => i.complete && !i.naturalWidth && (i.currentSrc || i.src)).map((i) => i.currentSrc || i.src).slice(0, 12)`;

async function checkViewport(cdp, url, vp, opts, outdir) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p, ms) => cdp.send(m, p, sessionId, ms);
  const name = `${vp.w}x${vp.h}`, mobile = vp.w < 768;
  const errors = [], warnings = [], requests = new Map(), open = new Map(), failed = new Set(), sessions = new Set();
  let lastActivity = Date.now(), loaded = false, stuck = false, favicon = '';
  const isFavicon = (u) => { try { return new URL(u).pathname === '/favicon.ico'; } catch { return false; } };
  const fail = (u, msg) => { failed.add(u); if (isFavicon(u)) favicon = msg; else errors.push(msg); };
  // A frame from another site, or a worker, is a target of its own: it is held
  // at its start until it is being listened to, then let go.
  const follow = (sid) => {
    sessions.add(sid);
    const C = (m, p) => cdp.send(m, p, sid, 5000).catch(() => {});
    return Promise.all([C('Page.enable'), C('Runtime.enable'), C('Network.enable'), C('Log.enable'),
      C('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true })]).then(() => C('Runtime.runIfWaitingForDebugger'));
  };
  const off = cdp.on((method, p, sid) => {
    if (!sessions.has(sid)) return;
    if (method === 'Target.attachedToTarget') follow(p.sessionId);
    else if (method === 'Target.detachedFromTarget') sessions.delete(p.sessionId);
    else if (method === 'Network.requestWillBeSent') {   // a redirect, or a frame seen from both sides, repeats the id
      let r = requests.get(p.requestId);
      if (!r) { r = { url: p.request.url, type: p.type || 'Other', bytes: 0, data: 0, done: false }; requests.set(p.requestId, r); }
      else { r.url = p.request.url; if (p.redirectResponse) r.bytes += p.redirectResponse.encodedDataLength || 0; }
      open.set(p.requestId, p.request.url); lastActivity = Date.now();
    }
    else if (method === 'Network.responseReceived') { if (p.response.status >= 400) fail(p.response.url, `request failed: ${p.response.status} ${p.response.url}`); }
    else if (method === 'Network.dataReceived') { const r = requests.get(p.requestId); if (r) r.data += p.dataLength; }
    else if (method === 'Network.loadingFinished') { const r = requests.get(p.requestId); if (r && !r.done) { r.bytes += p.encodedDataLength || 0; r.done = true; } open.delete(p.requestId); lastActivity = Date.now(); }
    else if (method === 'Network.loadingFailed') { const r = requests.get(p.requestId); open.delete(p.requestId); lastActivity = Date.now(); if (r && !p.canceled) fail(r.url, `request failed: ${p.errorText} ${r.url}`); }
    else if (method === 'Runtime.exceptionThrown') { const d = p.exceptionDetails, x = d.exception; errors.push('page error: ' + String(x?.description ?? (x && 'value' in x ? `${d.text} ${x.value}` : d.text)).split('\n')[0]); }
    else if (method === 'Runtime.consoleAPICalled' && p.type === 'error') errors.push('console error: ' + p.args.map((a) => ('value' in a ? String(a.value) : a.description ?? a.type)).join(' ').slice(0, 200));
    else if (method === 'Log.entryAdded' && p.entry.level === 'error' && p.entry.source !== 'network' && p.entry.source !== 'worker') errors.push('browser error: ' + p.entry.text.slice(0, 200));
    else if (method === 'Page.javascriptDialogOpening') {
      warnings.push(`the page opened a dialog (${p.type}: "${p.message.slice(0, 60)}"); it was accepted so that the check could go on`);
      cdp.send('Page.handleJavaScriptDialog', { accept: true }, sid, 5000).catch(() => {});
    }
    else if (method === 'Page.loadEventFired' && sid === sessionId) loaded = true;
  });
  try {
    await follow(sessionId);
    await S('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile });
    const evaluate = async (expression) => {
      const r = await S('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (r.exceptionDetails) throw new Error('evaluate failed: ' + r.exceptionDetails.text);
      return r.result.value;
    };
    const calm = () => open.size === 0 && Date.now() - lastActivity > 500;
    const settle = async () => {   // the load event, then half a second with nothing in flight
      const t0 = Date.now(), limit = stuck ? 3000 : 15000;
      while (Date.now() - t0 < limit && !(loaded && calm())) await sleep(100);
      if (!stuck && !(loaded && calm())) {
        stuck = true;              // it will not get better: later waits are short
        const waiting = open.size ? `${open.size} request(s) still open, such as ${[...open.values()][0].slice(0, 120)}` : 'requests keep starting';
        warnings.push(`${loaded ? 'the network did not go quiet' : 'the load event did not fire'} in 15 s: ${waiting}; the weight counts what had arrived`);
      }
      await evaluate('Promise.race([document.fonts ? document.fonts.ready : 0, new Promise((r) => setTimeout(r, 3000))]).then(() => true)');
    };
    const quiet = async (ms) => { const t0 = Date.now(); while (!stuck && Date.now() - t0 < ms && !calm()) await sleep(100); };
    const shot = async () => Buffer.from((await S('Page.captureScreenshot', { format: 'png' })).data, 'base64');
    const sha = (b) => crypto.createHash('sha1').update(b).digest('hex');
    const scrollTo = (y) => evaluate(`window.scrollTo({ top: ${y}, behavior: 'instant' })`);
    // Two captures of the same view: different bytes mean something is animating.
    const movingAt = async (ys, keep) => {
      const moving = [];
      for (const [i, y] of ys.entries()) {
        await scrollTo(y); await sleep(opts.waitMs); await quiet(3000);
        const a = await shot(); if (keep) keep(i, a);
        await sleep(opts.waitMs);
        if (sha(a) !== sha(await shot())) moving.push(y);
      }
      return moving;
    };

    const nav = await S('Page.navigate', { url });
    if (nav.errorText) { errors.push(`could not load ${url}: ${nav.errorText}`); return { viewport: name, notChecked: true, errors, warnings, shots: [] }; }
    await settle();
    const m = await evaluate(MEASURE);
    if (m.hiddenAtRest.length) {   // an entrance that had not started yet is not invisible text
      await sleep(1500);
      const later = (await evaluate(MEASURE)).hiddenAtRest;
      m.hiddenAtRest = m.hiddenAtRest.filter((t) => later.includes(t));
    }
    if (m.layoutWidth > vp.w + 1) errors.push(`the page is laid out ${m.layoutWidth}px wide on a ${vp.w}px screen and shrunk to fit: ` + (m.viewportMeta === null ? 'it has no <meta name="viewport">' : `its viewport meta is "${m.viewportMeta}"`));
    else if (m.scrollWidth > m.layoutWidth + 1 && !m.sidewaysClipped) errors.push(`horizontal overflow: the page is ${m.scrollWidth}px wide in a ${vp.w}px viewport` + (m.wide.length ? '; sticking out: ' + m.wide.join(' | ') : ''));
    for (const t of m.hiddenAtRest) warnings.push('text invisible on the first screen: ' + t);
    for (const t of m.cutText) warnings.push('text cut off by its box: ' + t);
    if (!m.title) warnings.push('the page has no <title>');
    if (m.innerScroller) warnings.push(`the page scrolls inside ${m.innerScroller}, not the document: only its first screen was checked`);

    // One pass down the whole page, nine tenths of a screen at a time, so that
    // lazy content loads. With contrast on, each screenful is captured twice
    // with its text hidden, so that something moving behind the text is caught,
    // and each block keeps its worst capture.
    const worst = new Map();
    let height = m.pageHeight, swept = false;
    for (let i = 0; i < 40 && !swept; i++) {
      const y = Math.round(Math.min(Math.max(0, height - vp.h), i * vp.h * 0.9));
      await scrollTo(y); await sleep(Math.min(opts.waitMs, 300));
      if (opts.contrast) await evaluate(AT_REST);
      for (let k = 0; opts.contrast && k < 2; k++) {
        const { vw, blocks } = await evaluate(TEXT_BLOCKS);
        await evaluate(HIDE_TEXT);
        const img = decodePng(await shot());
        await evaluate(SHOW_TEXT);
        for (const b of blocks) {
          const ratios = blockContrast(img, b, img.w / vw); if (ratios.length < 8) continue;
          const need = needed(b.size, b.weight), under = ratios.filter((x) => x < need).length / ratios.length;
          ratios.sort((x, y) => x - y);
          const cur = worst.get(b.key);
          if (!cur || under > cur.under) worst.set(b.key, { key: b.key, under, need, min: ratios[0], median: ratios[ratios.length >> 1], size: b.size, weight: b.weight, alpha: b.alpha });
        }
        if (k === 0) await sleep(opts.waitMs);
      }
      height = await evaluate('document.documentElement.scrollHeight');   // lazy content can make the page grow
      swept = y >= height - vp.h;
    }
    if (!swept) warnings.push('the page is taller than 40 screens (or keeps growing): the rest was not scrolled through');
    await quiet(8000);
    for (const src of await evaluate(BROKEN)) if (!failed.has(src)) errors.push('broken image: ' + src);

    let contrastReport = null;
    if (opts.contrast) {
      const list = [...worst.values()].sort((a, b) => b.under - a.under);
      const fmt = (b) => `${b.key}: ${Math.round(b.under * 100)}% of its area under ${b.need}:1 (lowest ${b.min.toFixed(1)}, median ${b.median.toFixed(1)}; ${b.size}px, weight ${b.weight}${b.alpha < 0.995 ? ', text alpha ' + b.alpha.toFixed(2) : ''})`;
      for (const b of list) {
        if (b.under * 100 >= opts.contrastArea) errors.push('low contrast: ' + fmt(b));
        else if (b.under * 100 >= 2) warnings.push('contrast dips: ' + fmt(b));
      }
      contrastReport = { blocks: list.length, failing: list.filter((b) => b.under * 100 >= opts.contrastArea).length, worst: list.slice(0, 10).map((b) => ({ ...b, under: +b.under.toFixed(3), min: +b.min.toFixed(2), median: +b.median.toFixed(2) })) };
    }

    // Screenshots at the scroll stops, and whether the page moves there.
    const maxY = Math.max(0, height - vp.h), shots = [];
    const ys = maxY === 0 || opts.stops === 1 ? [0] : Array.from({ length: opts.stops }, (_, i) => Math.round(maxY * i / (opts.stops - 1)));
    const restAt = await movingAt(ys, (i, png) => { const file = path.join(outdir, `${name}-${i + 1}.png`); fs.writeFileSync(file, png); shots.push(file); });

    // Weight: what came over the wire. A local file has no transfer size, so
    // it counts at its own size.
    await quiet(3000);
    const all = [...requests.values()].filter((r) => !r.url.startsWith('data:')).map((r) => ({ url: r.url, type: r.type, bytes: r.bytes > 0 ? r.bytes : r.data }));
    const total = all.reduce((s, r) => s + r.bytes, 0);
    const byType = {};
    for (const r of all) byType[r.type] = (byType[r.type] || 0) + r.bytes;
    const weight = { totalKb: Math.round(total / 1024), byTypeKb: Object.fromEntries(Object.entries(byType).map(([k, v]) => [k, Math.round(v / 1024)])),
      largest: all.sort((a, b) => b.bytes - a.bytes).slice(0, 5).map((r) => `${Math.round(r.bytes / 1024)} KB ${r.url.split('/').pop().slice(0, 60) || r.url}`) };
    if (opts.budgetKb && total > opts.budgetKb * 1024) errors.push(`weight: ${weight.totalKb} KB loaded, over the ${opts.budgetKb} KB budget; largest: ${weight.largest.join(', ')}`);
    if (favicon && m.iconLinked) errors.push(favicon);   // the browser's own guess at /favicon.ico is not the page's fault

    // Reduced motion is read at load by most scripts, so emulate it and load
    // again. An error that only this load produces is kept and marked.
    await S('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    loaded = false; lastActivity = Date.now();
    const first = new Set(errors), before = errors.length;
    await S('Page.reload'); await settle();
    for (const e of new Set(errors.splice(before))) if (!first.has(e)) errors.push('only under prefers-reduced-motion: ' + e);
    const reducedAt = await movingAt(ys);
    if (reducedAt.length) errors.push(`still moving under prefers-reduced-motion at scroll ${reducedAt.join(', ')}px: two captures ${opts.waitMs} ms apart differ`);
    return { viewport: name, pageHeight: height, errors: [...new Set(errors)], warnings: [...new Set(warnings)], movesAtRest: restAt.length > 0, movesReduced: reducedAt.length > 0, weight, contrast: contrastReport, shots };
  } finally {
    off();
    await cdp.send('Target.closeTarget', { targetId }, undefined, 5000).catch(() => {});
  }
}

function parseArgs(argv) {
  const o = { widths: [{ w: 1440, h: 900 }, { w: 390, h: 844 }], stops: 5, budgetKb: 0, waitMs: 600, noSandbox: false, contrast: true, contrastArea: 10, target: null, out: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], next = () => { if (i + 1 >= argv.length) throw new Error(`${a} needs a value`); return argv[++i]; };
    if (a === '-o' || a === '--out') o.out = next();
    else if (a === '--widths') o.widths = next().split(',').map((s) => { const m = s.trim().match(/^(\d+)x(\d+)$/); if (!m) throw new Error(`--widths takes WxH pairs, got "${s}"`); return { w: +m[1], h: +m[2] }; });
    else if (a === '--stops') o.stops = Math.max(1, parseInt(next(), 10) || 0);
    else if (a === '--budget-kb') o.budgetKb = Math.max(0, parseFloat(next()) || 0);
    else if (a === '--wait-ms') o.waitMs = Math.max(50, parseInt(next(), 10) || 0);
    else if (a === '--no-sandbox') o.noSandbox = true;
    else if (a === '--no-contrast') o.contrast = false;
    else if (a === '--contrast-area') o.contrastArea = Math.min(100, Math.max(0.5, parseFloat(next()) || 10));
    else if (a.startsWith('-')) throw new Error(`unknown option ${a}`);
    else if (!o.target) o.target = a;
    else throw new Error(`unexpected argument ${a}`);
  }
  return o;
}

function toUrl(target) {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(target) || /^(data|about):/i.test(target)) return target;
  const p = path.resolve(target);
  if (fs.existsSync(p)) return pathToFileURL(p).href;
  // localhost:8080/x, 127.0.0.1/x, devbox:3000 — a host given without its scheme
  if (/^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?(\/.*)?$/i.test(target) || /^[a-z0-9.-]+:\d+(\/.*)?$/i.test(target)) return 'http://' + target;
  throw new Error(`${target} is neither a URL nor an existing file`);
}

async function run(target, opts) {
  const url = toUrl(target);
  fs.mkdirSync(opts.out, { recursive: true });
  try {   // an earlier run's screenshots, as its own report lists them, and nothing else in the directory
    const old = JSON.parse(fs.readFileSync(path.join(opts.out, 'report.json'), 'utf8'));
    for (const v of old.viewports) for (const f of v.shots) if (/^\d+x\d+-\d+\.png$/.test(path.basename(f))) fs.rmSync(path.join(opts.out, path.basename(f)), { force: true });
  } catch {}
  const { cdp, close } = await launch(opts.noSandbox);
  try {
    const viewports = [];
    for (const vp of opts.widths) {
      try { viewports.push(await checkViewport(cdp, url, vp, opts, opts.out)); }
      catch (e) {
        if (cdp.closed) throw e;   // without Chrome there is nothing more to check
        viewports.push({ viewport: `${vp.w}x${vp.h}`, notChecked: true, errors: ['the check could not finish: ' + e.message], warnings: [], shots: [] });
      }
    }
    const report = { url, checkedAt: new Date().toISOString(), viewports };
    fs.writeFileSync(path.join(opts.out, 'report.json'), JSON.stringify(report, null, 1));
    return report;
  } finally { await close(); }
}

function print(report) {
  for (const v of report.viewports) {
    console.log(v.notChecked ? `\n${v.viewport}  not checked`
      : `\n${v.viewport}  page ${v.pageHeight}px tall  ${v.weight.totalKb} KB  moves at rest: ${v.movesAtRest ? 'yes' : 'no'}  under reduced motion: ${v.movesReduced ? 'YES' : 'no'}`);
    for (const e of v.errors) console.log('  ERROR ' + e);
    for (const w of v.warnings) console.log('  warn  ' + w);
    if (v.weight) console.log('  largest: ' + v.weight.largest.join(', '));
    if (v.contrast) console.log(`  contrast: ${v.contrast.blocks} text blocks measured against what is behind them, ${v.contrast.failing} failing`);
    if (v.shots.length) console.log(`  ${v.shots.length} screenshots: ${v.shots[0]} ...`);
  }
}

async function selfTest() {
  const mine = () => fs.readdirSync(os.tmpdir()).filter((f) => f.startsWith('page-check-'));
  const there = new Set(mine());
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'page-check-test-')); temp.add(dir);
  // A local server for what a file cannot show: a redirect, a compressed
  // response, a missing favicon, a frame from another site.
  const filler = 'const filler = "' + 'abcdefghij'.repeat(30000) + '";';   // 300 KB that gzip folds to about 1 KB
  const served = {
    '/plain.html': () => '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Plain</title><h1>A plain page on a server</h1><p>Nothing on this page is wrong.</p><script src="/big.js"></script></html>',
    '/frame.html': () => `<!doctype html><html lang="en"><title>Frame</title><p>Inside a frame from another site.</p><img src="/gone-in-frame.png" alt=""><script>console.error('boom in the frame')</script></html>`,
    '/host.html': (port) => `<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Host</title><h1>A page with a frame from another site</h1><iframe src="http://localhost:${port}/frame.html" width="400" height="200" title="frame"></iframe></html>`,
  };
  const server = http.createServer((req, res) => {
    const p = new URL(req.url, 'http://x').pathname;
    if (p === '/redir') { res.writeHead(302, { location: '/plain.html' }); return res.end(); }
    if (p === '/big.js') { res.writeHead(200, { 'content-type': 'text/javascript', 'content-encoding': 'gzip' }); return res.end(zlib.gzipSync(filler)); }
    if (!served[p]) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('not here'); }
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end(served[p](server.address().port));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  try {
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
    fs.writeFileSync(path.join(dir, 'dot.png'), png);
    fs.writeFileSync(path.join(dir, 'good.html'), `<!doctype html><html lang="en"><title>Good</title><style>body{margin:0;font:16px sans-serif}
      .spin{width:40px;height:40px;background:teal;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}
      @media (prefers-reduced-motion:reduce){.spin{animation:none}}</style>
      <h1>A page that behaves</h1><p style="background:#123;color:#fff;padding:8px">White text on a dark band reads well.</p><p style="font-size:30px;font-weight:700;color:#777">Large grey text only needs three to one.</p><div class="spin"></div><img src="dot.png" width="10" height="10" alt=""><div style="height:2400px"></div><p>The end of the page.</p></html>`);
    fs.writeFileSync(path.join(dir, 'bad.html'), `<!doctype html><html><style>body{margin:0;font:16px sans-serif}
      .spin{width:40px;height:40px;background:red;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}</style>
      <div style="width:2000px;height:20px;background:#ccc">a strip much wider than any phone or laptop screen</div>
      <p style="opacity:0">This paragraph waits for a script that never runs.</p>
      <p style="color:#bbb">Pale grey words on a white page are hard to read.</p>
      <p style="color:rgba(255,255,255,.8);padding:6px;width:300px;background:linear-gradient(90deg,#123 0 50%,#9cf 50% 100%)">Half of this line sits on a light patch.</p>
      <p style="height:18px;overflow:hidden;width:120px">A long sentence that cannot fit in one short line of a narrow box.</p>
      <p style="color:#000;-webkit-text-fill-color:#fff">Filled white on white, whatever the colour says.</p>
      <input value="a pale grey value in a field" style="color:#ddd;border:0;width:300px">
      <div class="spin"></div><img src="missing.png" alt=""><script>console.error('boom'); null.x</script></html>`);
    // Things that are easy to get wrong in the checker itself: motion only at
    // the top of a tall page, an image that loads only when scrolled to, an
    // error that only the reduced-motion load raises, a dialog, and three
    // things that are not defects (a screen-reader-only link, an off-canvas
    // menu behind overflow-x: hidden, an entrance that starts after a delay).
    fs.writeFileSync(path.join(dir, 'tricky.html'), `<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Tricky</title>
      <style>body{margin:0;font:16px sans-serif;overflow-x:hidden}
      .spin{width:40px;height:40px;background:red;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}
      .sr{position:absolute;width:1px;height:1px;overflow:hidden}
      nav{position:absolute;left:100%;top:0;width:300px;height:40px;background:#ddd}
      .late{animation:in .3s .9s both}@keyframes in{from{opacity:0}}</style>
      <a class="sr" href="#main">Skip to the main content of this page</a><nav>An off-canvas menu waiting to slide in</nav>
      <div class="spin"></div><h1 id="main">A tall page with traps in it</h1><p class="late">This sentence fades in after a short delay.</p>
      <div style="height:3000px"></div><img loading="lazy" src="gone.png" width="50" height="50" alt=""><p>The end of the page.</p>
      <script>alert('hello'); if (matchMedia('(prefers-reduced-motion: reduce)').matches) console.error('reduced only');</script></html>`);
    // Traps for the contrast measure: text under a fixed header, a clipped
    // carousel slide and a closed accordion in white on white, text with its
    // own colour transition, and text that fades in when scrolled to.
    fs.writeFileSync(path.join(dir, 'calm.html'), `<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Calm</title>
      <style>body{margin:0;font:16px sans-serif;color:#222;background:#fff}
      header{position:fixed;top:0;left:0;right:0;height:80px;background:#123;color:#fff;z-index:2}main{padding-top:90px}
      .t{transition:all 1s}.rv{opacity:0;transition:opacity .9s}.rv.in{opacity:1}
      .car{width:300px;overflow:hidden;white-space:nowrap}.car div{display:inline-block;width:300px}.car .two{color:#fff}
      .acc{height:0;overflow:hidden;color:#fff}
      @media (prefers-reduced-motion:reduce){.rv{transition:none}}</style>
      <header><p>A fixed header in white on dark</p></header><main><h2 class="t">A heading in dark on white</h2>
      ${Array.from({ length: 40 }, (_, i) => `<p class="${i % 2 ? 't' : 'rv'}">Paragraph ${i} in dark grey on white, easy to read and long enough.</p>`).join('')}
      <div class="car"><div>Slide one is dark and visible.</div><div class="two">Slide two is white and clipped away.</div></div>
      <div class="acc"><p>Closed accordion text in white that nobody sees.</p></div></main>
      <script>const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && e.target.classList.add('in'))); document.querySelectorAll('.rv').forEach((el) => io.observe(el));</script></html>`);
    fs.writeFileSync(path.join(dir, 'nometa.html'), '<!doctype html><html lang="en"><title>No viewport meta</title><body style="margin:0;width:980px"><div style="float:left;width:490px;height:300px;background:#123;color:#fff"><p>White words on a dark panel that is fine to read.</p></div><h1>A page a phone will shrink</h1><p>It never says how wide it wants to be laid out.</p></html>');
    const opts = { ...parseArgs([]), widths: [{ w: 800, h: 600 }], stops: 3, waitMs: 300 };
    const one = async (target, out, more = {}) => {
      const v = (await run(target.includes('://') ? target : path.join(dir, target), { ...opts, out: path.join(dir, out), ...more })).viewports[0];
      if (v.notChecked) throw new Error(`self-test: ${target} was not checked: ${v.errors.join('; ')}`);
      return v;
    };
    const good = await one('good.html', 'g');
    const bad = await one('bad.html', 'b');
    const tricky = await one('tricky.html', 't', { contrast: false });
    const calm = await one('calm.html', 'c');
    fs.writeFileSync(path.join(dir, 'g', '1920x1080-2.png'), png);                    // somebody else's file with a name like ours
    const phone = await one('nometa.html', 'g', { widths: [{ w: 390, h: 700 }] });   // into the first run's directory
    const t0 = Date.now(), plain = await one(origin + '/redir', 'p'), plainMs = Date.now() - t0;
    const host = await one(origin + '/host.html', 'h');
    const has = (list, s) => list.some((x) => x.includes(s));
    const checks = [
      ['good page: no errors', good.errors.length === 0, good.errors],
      ['good page: no warnings', good.warnings.length === 0, good.warnings],
      ['good page: moves at rest', good.movesAtRest === true],
      ['good page: still under reduced motion', good.movesReduced === false],
      ['good page: three screenshots named by viewport', good.shots.length === 3 && path.basename(good.shots[0]) === '800x600-1.png', good.shots],
      ['good page: weight counted', good.weight.totalKb >= 0 && good.weight.largest.length >= 1],
      ['good page: contrast measured and nothing failing', good.contrast.blocks >= 3 && good.contrast.failing === 0, good.contrast],
      ['bad page: overflow', has(bad.errors, 'horizontal overflow')],
      ['bad page: overflow names the strip', has(bad.errors, 'a strip much wider')],
      ['bad page: the missing image, once', bad.errors.filter((e) => e.includes('missing.png')).length === 1, bad.errors],
      ['bad page: console error', has(bad.errors, 'console error: boom')],
      ['bad page: page error', has(bad.errors, 'page error')],
      ['bad page: moves under reduced motion', has(bad.errors, 'prefers-reduced-motion')],
      ['bad page: invisible text', has(bad.warnings, 'text invisible')],
      ['bad page: cut text', has(bad.warnings, 'text cut off')],
      ['bad page: no title', has(bad.warnings, 'no <title>')],
      ['bad page: pale grey text', bad.errors.some((e) => e.startsWith('low contrast') && e.includes('Pale grey'))],
      ['bad page: see-through text over a light patch', bad.errors.some((e) => e.startsWith('low contrast') && e.includes('Half of this line') && e.includes('text alpha 0.80'))],
      ['bad page: the pale text is nearly all under', bad.contrast.worst.some((b) => b.key.includes('Pale grey') && b.under > 0.9)],
      ['bad page: see-through white on dark is not over-rated', bad.contrast.worst.some((b) => b.key.includes('Half of this line') && b.median < 21)],
      ['bad page: the half-and-half line is about half under', bad.contrast.worst.some((b) => b.key.includes('Half of this line') && b.under > 0.3 && b.under < 0.7)],
      ['tricky page: motion at the top of a tall page is seen under reduced motion', has(tricky.errors, 'still moving under prefers-reduced-motion at scroll 0'), tricky.errors],
      ['tricky page: the lazy image at the bottom, once, with contrast off', tricky.errors.filter((e) => e.includes('gone.png')).length === 1, tricky.errors],
      ['tricky page: an error only the reduced-motion load raises', has(tricky.errors, 'only under prefers-reduced-motion: console error: reduced only'), tricky.errors],
      ['tricky page: the dialog is accepted and reported', has(tricky.warnings, 'opened a dialog'), tricky.warnings],
      ['tricky page: clipped off-canvas menu is not overflow', !has(tricky.errors, 'horizontal overflow'), tricky.errors],
      ['tricky page: a screen-reader-only link is not cut text', !has(tricky.warnings, 'text cut off'), tricky.warnings],
      ['tricky page: a delayed entrance is not invisible text', !has(tricky.warnings, 'text invisible'), tricky.warnings],
      ['bad page: text-fill-color is the colour that counts', bad.errors.some((e) => e.startsWith('low contrast') && e.includes('Filled white')), bad.errors],
      ['bad page: the value of a form field is text', bad.errors.some((e) => e.startsWith('low contrast') && e.includes('a pale grey value')), bad.errors],
      ['calm page: covered, clipped, transitioning and fading-in text raise nothing', calm.errors.length === 0 && calm.contrast.failing === 0, calm.errors],
      ['calm page: its text was measured', calm.contrast.blocks >= 30, calm.contrast.blocks],
      ['phone without a viewport meta: named, not called overflow', has(phone.errors, 'no <meta name="viewport">') && !has(phone.errors, 'horizontal overflow'), phone.errors],
      ['phone without a viewport meta: contrast is read at the capture\'s scale', !has(phone.errors, 'low contrast'), phone.errors],
      ['same directory: the first run\'s screenshots are gone and nothing else', fs.readdirSync(path.join(dir, 'g')).filter((f) => f.endsWith('.png') && !f.startsWith('390x700-')).join() === '1920x1080-2.png', fs.readdirSync(path.join(dir, 'g'))],
      ['server: a redirect and a missing favicon are not errors', plain.errors.length === 0 && plain.warnings.length === 0, [plain.errors, plain.warnings]],
      ['server: the redirect does not hold the run up', plainMs < 15000, plainMs],
      ['server: a compressed script counts at its transfer size', plain.weight.totalKb < 50, plain.weight],
      ['frame from another site: its console error', has(host.errors, 'boom in the frame'), host.errors],
      ['frame from another site: its missing image', has(host.errors, 'gone-in-frame.png'), host.errors],
      ['budget: a 0.1 KB budget is exceeded', (await one('good.html', 'w', { budgetKb: 0.1 })).errors.some((e) => e.startsWith('weight:'))],
      ['budget: a 500 KB budget is not', !(await one('good.html', 'w2', { budgetKb: 500 })).errors.some((e) => e.startsWith('weight:'))],
      ['a host without its scheme is a URL', toUrl('localhost:8080/x') === 'http://localhost:8080/x' && toUrl('data:text/html,x') === 'data:text/html,x'],
    ];
    let failedChecks = 0;
    for (const [name, ok, detail] of checks) { if (!ok) { failedChecks++; console.log('FAIL ' + name + (detail !== undefined ? ' ' + JSON.stringify(detail) : '')); } }
    const left = mine().filter((f) => !there.has(f) && f !== path.basename(dir));
    if (left.length) { failedChecks++; console.log('FAIL a temporary directory was left: ' + left.join(', ')); }
    if (failedChecks) { console.log(`self-test: ${failedChecks} of ${checks.length + 1} failed`); return 1; }
    console.log(`self-test OK — ${checks.length + 1} checks: a clean page, a page with twelve planted defects, two pages of traps for the checker, a phone, a server`);
    return 0;
  } finally { server.close(); server.closeAllConnections?.(); removeDir(dir); temp.delete(dir); }
}

const USAGE = 'usage: page-check.mjs URL_OR_FILE -o OUTDIR [--widths 1440x900,390x844] [--stops 5] [--budget-kb N] [--contrast-area 10] [--no-contrast] [--wait-ms 600] [--no-sandbox]\n       page-check.mjs --self-test';

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--self-test')) return selfTest();
  let opts;
  try { opts = parseArgs(argv); if (!opts.target || !opts.out) throw new Error(USAGE); }
  catch (e) { console.error('page-check: ' + e.message); return 2; }
  const report = await run(opts.target, opts);
  print(report);
  const errors = report.viewports.reduce((n, v) => n + v.errors.length, 0);
  console.log(`\n${errors} error(s); report: ${path.join(opts.out, 'report.json')}`);
  return errors ? 1 : 0;
}

process.exitCode = 2;   // if the process ever ends without reaching the line below, that is not a pass
main().then((code) => process.exit(code), (e) => { console.error('page-check: ' + e.message); process.exit(2); });
