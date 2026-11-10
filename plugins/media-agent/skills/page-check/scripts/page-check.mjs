#!/usr/bin/env node
// Check a web page mechanically, then leave screenshots to look at.
//
//   page-check.mjs URL_OR_FILE -o OUTDIR [--widths 1440x900,390x844] [--stops 5]
//                  [--budget-kb N] [--wait-ms 600] [--no-sandbox]
//   page-check.mjs --self-test
//
// For each width: loads the page in headless Chrome, records console errors,
// failed requests and broken images, measures horizontal overflow, text that is
// invisible or cut off, and the weight of what was downloaded, takes a
// screenshot at each scroll stop, and checks whether the page moves at rest and
// whether it still moves under prefers-reduced-motion.
//
// Writes OUTDIR/report.json and OUTDIR/<width>-<stop>.png. Exit 1 when there is
// an error-level finding, 0 otherwise. Needs Node 22 or later and Chrome or
// Chromium (set CHROME to choose the binary). No npm packages.
import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

function findChrome() {
  const names = [process.env.CHROME, 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'].filter(Boolean);
  for (const n of names) {
    if (n.includes('/')) { if (fs.existsSync(n)) return n; continue; }
    const r = spawnSync('sh', ['-c', 'command -v "$1"', 'sh', n], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim()) return r.stdout.trim();
  }
  throw new Error('no Chrome or Chromium found; set CHROME to the binary');
}

// A minimal Chrome DevTools Protocol client over Node's built-in WebSocket.
class Cdp {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = [];
    ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id); this.pending.delete(m.id);
        m.error ? reject(new Error(`${m.error.message} (${m.error.code})`)) : resolve(m.result);
      } else if (m.method) {
        for (const h of this.handlers) h(m.method, m.params, m.sessionId);
      }
    });
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  on(fn) { this.handlers.push(fn); }
}

async function launch(noSandbox) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'page-check-'));
  const args = ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--hide-scrollbars', '--mute-audio', ...(noSandbox ? ['--no-sandbox'] : []), 'about:blank'];
  const proc = spawn(findChrome(), args, { stdio: ['ignore', 'ignore', 'pipe'] });
  const url = await new Promise((resolve, reject) => {
    let buf = '';
    const timer = setTimeout(() => reject(new Error('Chrome did not open its DevTools port in 20 s:\n' + buf.slice(-600))), 20000);
    proc.stderr.on('data', (d) => {
      buf += d;
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(timer); resolve(m[1]); }
    });
    proc.on('exit', (code) => { clearTimeout(timer); reject(new Error(`Chrome exited with ${code}:\n` + buf.slice(-600))); });
  });
  const ws = new WebSocket(url);
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', () => reject(new Error('could not connect to Chrome'))); });
  const close = async () => {   // the profile can only be removed once Chrome has let go of it
    try { ws.close(); } catch {}
    const gone = new Promise((resolve) => proc.once('exit', resolve));
    try { proc.kill(); } catch {}
    await Promise.race([gone, sleep(5000)]);
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }); } catch {}
  };
  return { cdp: new Cdp(ws), close };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Runs in the page. Returns what can be measured without looking.
const MEASURE = `(() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const label = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')) + ' "' + (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40) + '"';
  const clippedBy = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o !== 'visible' && p.getBoundingClientRect().right <= vw + 1) return true; } return false; };
  const ownText = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(' ');
  const opacity = (el) => { let o = 1; for (let p = el; p; p = p.parentElement) { const s = getComputedStyle(p); if (s.visibility === 'hidden') return 0; o *= parseFloat(s.opacity); } return o; };
  const wide = [], hidden = [], cut = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const s = getComputedStyle(el);
    if (s.position !== 'fixed' && r.right > vw + 1 && !clippedBy(el)) wide.push(label(el) + ' right=' + Math.round(r.right));
    const text = ownText(el);
    if (text.length >= 12 && r.top < vh && r.bottom > 0 && opacity(el) < 0.05) hidden.push(label(el));
    if (text.length >= 12 && /hidden|clip/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 2) cut.push(label(el) + ' ' + el.scrollHeight + '>' + el.clientHeight);
  }
  return {
    viewport: vw + 'x' + vh, pageHeight: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth,
    wide: wide.slice(0, 8), hiddenAtRest: hidden.slice(0, 8), cutText: cut.slice(0, 8),
    brokenImages: [...document.images].filter((i) => i.complete && !i.naturalWidth && (i.currentSrc || i.src)).map((i) => i.currentSrc || i.src).slice(0, 8),
    title: document.title, lang: document.documentElement.lang || '',
  };
})()`;

async function checkViewport(cdp, url, vp, opts, outdir) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const S = (m, p) => cdp.send(m, p, sessionId);
  const errors = [], warnings = [], requests = new Map();
  let inflight = 0, lastActivity = Date.now(), loaded = false;
  cdp.on((method, p, sid) => {
    if (sid !== sessionId) return;
    if (method === 'Network.requestWillBeSent') { requests.set(p.requestId, { url: p.request.url, type: p.type || 'Other', bytes: 0, data: 0 }); inflight++; lastActivity = Date.now(); }
    else if (method === 'Network.responseReceived') { const r = requests.get(p.requestId); if (r) { r.status = p.response.status; if (p.response.status >= 400) errors.push(`request failed: ${p.response.status} ${p.response.url}`); } }
    else if (method === 'Network.dataReceived') { const r = requests.get(p.requestId); if (r) r.data += p.dataLength; }
    else if (method === 'Network.loadingFinished') { const r = requests.get(p.requestId); if (r) r.bytes = p.encodedDataLength; inflight--; lastActivity = Date.now(); }
    else if (method === 'Network.loadingFailed') { const r = requests.get(p.requestId); inflight--; lastActivity = Date.now(); if (r && !p.canceled) errors.push(`request failed: ${p.errorText} ${r.url}`); }
    else if (method === 'Runtime.exceptionThrown') errors.push('page error: ' + (p.exceptionDetails.exception?.description || p.exceptionDetails.text).split('\n')[0]);
    else if (method === 'Runtime.consoleAPICalled' && p.type === 'error') errors.push('console error: ' + p.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200));
    else if (method === 'Page.loadEventFired') loaded = true;
  });
  await S('Page.enable'); await S('Runtime.enable'); await S('Network.enable');
  await S('Emulation.setDeviceMetricsOverride', { width: vp.w, height: vp.h, deviceScaleFactor: 1, mobile: vp.w < 768 });
  const evaluate = async (expression) => {
    const r = await S('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error('evaluate failed: ' + r.exceptionDetails.text);
    return r.result.value;
  };
  const settle = async () => {   // load event, then half a second with nothing in flight (15 s at most)
    const t0 = Date.now();
    while (Date.now() - t0 < 15000 && !(loaded && inflight <= 0 && Date.now() - lastActivity > 500)) await sleep(100);
    if (!loaded) warnings.push('the load event did not fire in 15 s');
    await evaluate('document.fonts ? document.fonts.ready.then(() => true) : true');
  };
  const shot = async () => Buffer.from((await S('Page.captureScreenshot', { format: 'png' })).data, 'base64');
  const moves = async () => {    // two captures of the same view: different bytes mean something is animating
    const a = await shot(); await sleep(opts.waitMs); const b = await shot();
    return crypto.createHash('sha1').update(a).digest('hex') !== crypto.createHash('sha1').update(b).digest('hex');
  };

  const nav = await S('Page.navigate', { url });
  if (nav.errorText) { errors.push(`could not load ${url}: ${nav.errorText}`); await cdp.send('Target.closeTarget', { targetId }); return { viewport: `${vp.w}x${vp.h}`, errors, warnings, shots: [] }; }
  await settle();
  const m = await evaluate(MEASURE);
  if (m.scrollWidth > vp.w + 1) errors.push(`horizontal overflow: the page is ${m.scrollWidth}px wide in a ${vp.w}px viewport` + (m.wide.length ? '; sticking out: ' + m.wide.join(' | ') : ''));
  for (const src of m.brokenImages) errors.push('broken image: ' + src);
  for (const t of m.hiddenAtRest) warnings.push('text invisible on the first screen: ' + t);
  for (const t of m.cutText) warnings.push('text cut off by its box: ' + t);
  if (!m.title) warnings.push('the page has no <title>');

  const movesAtRest = await moves();
  const shots = [];
  const maxY = Math.max(0, m.pageHeight - vp.h);
  for (let i = 0; i < opts.stops; i++) {
    const y = opts.stops === 1 ? 0 : Math.round(maxY * i / (opts.stops - 1));
    await evaluate(`window.scrollTo(0, ${y})`); await sleep(opts.waitMs);
    const file = path.join(outdir, `${vp.w}-${i + 1}.png`);
    fs.writeFileSync(file, await shot()); shots.push(file);
    if (maxY === 0) break;
  }

  const all = [...requests.values()].map((r) => ({ url: r.url, type: r.type, bytes: Math.max(r.bytes, r.data) }));
  const total = all.reduce((s, r) => s + r.bytes, 0);
  const byType = {};
  for (const r of all) byType[r.type] = (byType[r.type] || 0) + r.bytes;
  const weight = { totalKb: Math.round(total / 1024), byTypeKb: Object.fromEntries(Object.entries(byType).map(([k, v]) => [k, Math.round(v / 1024)])),
    largest: all.sort((a, b) => b.bytes - a.bytes).slice(0, 5).map((r) => `${Math.round(r.bytes / 1024)} KB ${r.url.split('/').pop().slice(0, 60) || r.url}`) };
  if (opts.budgetKb && total > opts.budgetKb * 1024) errors.push(`weight: ${weight.totalKb} KB loaded, over the ${opts.budgetKb} KB budget; largest: ${weight.largest.join(', ')}`);

  // Reduced motion is read at load by most scripts, so emulate it and load again.
  await S('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  loaded = false; lastActivity = Date.now();
  const before = errors.length;
  await S('Page.reload'); await settle();
  errors.length = before;        // the reload repeats the same load errors
  const movesReduced = await moves();
  if (movesReduced) errors.push('still moving under prefers-reduced-motion: two captures ' + opts.waitMs + ' ms apart differ');
  await cdp.send('Target.closeTarget', { targetId });
  return { viewport: `${vp.w}x${vp.h}`, pageHeight: m.pageHeight, errors: [...new Set(errors)], warnings: [...new Set(warnings)], movesAtRest, movesReduced, weight, shots };
}

function parseArgs(argv) {
  const o = { widths: [{ w: 1440, h: 900 }, { w: 390, h: 844 }], stops: 5, budgetKb: 0, waitMs: 600, noSandbox: false, target: null, out: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], next = () => { if (i + 1 >= argv.length) throw new Error(`${a} needs a value`); return argv[++i]; };
    if (a === '-o' || a === '--out') o.out = next();
    else if (a === '--widths') o.widths = next().split(',').map((s) => { const m = s.trim().match(/^(\d+)x(\d+)$/); if (!m) throw new Error(`--widths takes WxH pairs, got "${s}"`); return { w: +m[1], h: +m[2] }; });
    else if (a === '--stops') o.stops = Math.max(1, parseInt(next(), 10) || 0);
    else if (a === '--budget-kb') o.budgetKb = Math.max(0, parseFloat(next()) || 0);
    else if (a === '--wait-ms') o.waitMs = Math.max(50, parseInt(next(), 10) || 0);
    else if (a === '--no-sandbox') o.noSandbox = true;
    else if (a.startsWith('-')) throw new Error(`unknown option ${a}`);
    else if (!o.target) o.target = a;
    else throw new Error(`unexpected argument ${a}`);
  }
  return o;
}

function toUrl(target) {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(target)) return target;
  const p = path.resolve(target);
  if (!fs.existsSync(p)) throw new Error(`${target} is neither a URL nor an existing file`);
  return pathToFileURL(p).href;
}

async function run(target, opts) {
  const url = toUrl(target);
  fs.mkdirSync(opts.out, { recursive: true });
  const { cdp, close } = await launch(opts.noSandbox);
  try {
    const viewports = [];
    for (const vp of opts.widths) viewports.push(await checkViewport(cdp, url, vp, opts, opts.out));
    const report = { url, checkedAt: new Date().toISOString(), viewports };
    fs.writeFileSync(path.join(opts.out, 'report.json'), JSON.stringify(report, null, 1));
    return report;
  } finally { await close(); }
}

function print(report) {
  for (const v of report.viewports) {
    console.log(`\n${v.viewport}  page ${v.pageHeight ?? '?'}px tall  ${v.weight ? v.weight.totalKb + ' KB' : ''}  moves at rest: ${v.movesAtRest ? 'yes' : 'no'}  under reduced motion: ${v.movesReduced ? 'YES' : 'no'}`);
    for (const e of v.errors) console.log('  ERROR ' + e);
    for (const w of v.warnings) console.log('  warn  ' + w);
    if (v.weight) console.log('  largest: ' + v.weight.largest.join(', '));
    if (v.shots.length) console.log(`  ${v.shots.length} screenshots: ${v.shots[0]} ...`);
  }
}

async function selfTest() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'page-check-test-'));
  try {
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
    fs.writeFileSync(path.join(dir, 'dot.png'), png);
    fs.writeFileSync(path.join(dir, 'good.html'), `<!doctype html><html lang="en"><title>Good</title><style>body{margin:0;font:16px sans-serif}
      .spin{width:40px;height:40px;background:teal;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}
      @media (prefers-reduced-motion:reduce){.spin{animation:none}}</style>
      <h1>A page that behaves</h1><div class="spin"></div><img src="dot.png" width="10" height="10" alt=""><div style="height:2400px"></div><p>The end of the page.</p></html>`);
    fs.writeFileSync(path.join(dir, 'bad.html'), `<!doctype html><html><style>body{margin:0;font:16px sans-serif}
      .spin{width:40px;height:40px;background:red;animation:s 1s linear infinite}@keyframes s{to{transform:rotate(360deg)}}</style>
      <div style="width:2000px;height:20px;background:#ccc">a strip much wider than any phone or laptop screen</div>
      <p style="opacity:0">This paragraph waits for a script that never runs.</p>
      <p style="height:18px;overflow:hidden;width:120px">A long sentence that cannot fit in one short line of a narrow box.</p>
      <div class="spin"></div><img src="missing.png" alt=""><script>console.error('boom'); null.x</script></html>`);
    const opts = { ...parseArgs([]), out: path.join(dir, 'out'), widths: [{ w: 800, h: 600 }], stops: 3, waitMs: 300 };
    const good = (await run(path.join(dir, 'good.html'), { ...opts, out: path.join(dir, 'g') })).viewports[0];
    const bad = (await run(path.join(dir, 'bad.html'), { ...opts, out: path.join(dir, 'b') })).viewports[0];
    const has = (list, s) => list.some((x) => x.includes(s));
    const checks = [
      ['good page: no errors', good.errors.length === 0, good.errors],
      ['good page: no warnings', good.warnings.length === 0, good.warnings],
      ['good page: moves at rest', good.movesAtRest === true],
      ['good page: still under reduced motion', good.movesReduced === false],
      ['good page: three screenshots', good.shots.length === 3 && good.shots.every((f) => fs.statSync(f).size > 500)],
      ['good page: weight counted', good.weight.totalKb >= 0 && good.weight.largest.length >= 1],
      ['bad page: overflow', has(bad.errors, 'horizontal overflow')],
      ['bad page: overflow names the strip', has(bad.errors, 'a strip much wider')],
      ['bad page: broken or failed image', has(bad.errors, 'missing.png')],
      ['bad page: console error', has(bad.errors, 'console error: boom')],
      ['bad page: page error', has(bad.errors, 'page error')],
      ['bad page: moves under reduced motion', has(bad.errors, 'prefers-reduced-motion')],
      ['bad page: invisible text', has(bad.warnings, 'text invisible')],
      ['bad page: cut text', has(bad.warnings, 'text cut off')],
      ['bad page: no title', has(bad.warnings, 'no <title>')],
      ['budget: a 0.1 KB budget is exceeded', (await run(path.join(dir, 'good.html'), { ...opts, out: path.join(dir, 'w'), budgetKb: 0.1 })).viewports[0].errors.some((e) => e.startsWith('weight:'))],
      ['budget: a 500 KB budget is not', !(await run(path.join(dir, 'good.html'), { ...opts, out: path.join(dir, 'w2'), budgetKb: 500 })).viewports[0].errors.some((e) => e.startsWith('weight:'))],
    ];
    let failed = 0;
    for (const [name, ok, detail] of checks) { if (!ok) { failed++; console.log('FAIL ' + name + (detail ? ' ' + JSON.stringify(detail) : '')); } }
    if (failed) { console.log(`self-test: ${failed} of ${checks.length} failed`); return 1; }
    console.log(`self-test OK — ${checks.length} checks on a clean page and a page with eight planted defects`);
    return 0;
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--self-test')) return selfTest();
  let opts;
  try { opts = parseArgs(argv); if (!opts.target || !opts.out) throw new Error('usage: page-check.mjs URL_OR_FILE -o OUTDIR [--widths 1440x900,390x844] [--stops 5] [--budget-kb N]'); }
  catch (e) { console.error('page-check: ' + e.message); return 2; }
  const report = await run(opts.target, opts);
  print(report);
  const errors = report.viewports.reduce((n, v) => n + v.errors.length, 0);
  console.log(`\n${errors} error(s); report: ${path.join(opts.out, 'report.json')}`);
  return errors ? 1 : 0;
}

main().then((code) => process.exit(code), (e) => { console.error('page-check: ' + e.message); process.exit(2); });
