// A Three.js stage for HyperFrames. Every pixel is a function of the seek time:
// no clock, no requestAnimationFrame, no unseeded random. The canvas is drawn
// from `hf-seek`; the text and bars over it are set in the same handler.
// three 0.180.0 as one ES module: the test used the bundle vendored in HyperFrames'
// `path-traced-3d` example (MIT), which re-exports all of three, copied to this path.
import * as THREE from "./vendor/three.min.js";

const root = document.querySelector("[data-composition-id]");
const canvas = document.getElementById("stage");
const W = Number(root.dataset.width);
const H = Number(root.dataset.height);
const FPS = Number(root.dataset.fps || 30);
const vars = window.__hyperframes?.getVariables?.() ?? {};
const SAMPLES = Math.round(Number(vars.samples ?? 0)); // 0 = sized to the motion
const SHUTTER = Number(vars.shutter ?? 180) / 360 / FPS; // seconds the shutter is open

// ---- timing (seconds); words come from the voice's word times -------------
const IMPACTS = [1.0, 1.6, 2.2];
const FALL = 0.36;
const WHIP = [2.7, 2.7 + 5 / FPS];
const PULL = [4.0, 4.25];
const HIGHLIGHT = 3.15;
const HANDOFF = 4.5;
const WORDS = [
  { w: "Um", t: 0.95, group: 0 }, { w: "dois", t: 1.55, group: 0 }, { w: "três", t: 2.15, group: 0 },
  { w: "o", t: 3.05, group: 1 }, { w: "segundo", t: 3.12, group: 1 }, { w: "acende", t: 3.45, group: 1 },
];
const GROUPS = [[0.9, 2.6], [3.0, 4.3]];
const frameOf = (t) => Math.floor(t * FPS + 1e-6);
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const easeInOut = (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
const easeOut = (u) => 1 - Math.pow(1 - u, 3);
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), s | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---- renderer and passes ---------------------------------------------------
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.autoClear = false;
const rt = (w, h, extra = {}) =>
  new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: false, ...extra });
const sceneRT = rt(W, H, { depthBuffer: true, samples: 4 });
const accumRT = rt(W, H);
const half = [rt(W / 2, H / 2), rt(W / 2, H / 2)];
const quarter = [rt(W / 4, H / 4), rt(W / 4, H / 4)];
const quadScene = new THREE.Scene();
const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
quadScene.add(quad);
const VS = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
const shader = (fs, uniforms, extra = {}) =>
  new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms, depthTest: false,
    depthWrite: false, toneMapped: false, blending: THREE.NoBlending, ...extra });
const addMat = shader("uniform sampler2D tex; uniform float gain; varying vec2 vUv;" +
  "void main(){ gl_FragColor = vec4(texture2D(tex, vUv).rgb * gain, 1.0); }",
  { tex: { value: null }, gain: { value: 1 } },
  { blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor });
const brightMat = shader("uniform sampler2D tex; varying vec2 vUv;" +
  "void main(){ vec3 c = texture2D(tex, vUv).rgb; float l = max(c.r, max(c.g, c.b));" +
  " gl_FragColor = vec4(c * smoothstep(0.9, 1.6, l), 1.0); }", { tex: { value: null } });
const blurMat = shader("uniform sampler2D tex; uniform vec2 dir; varying vec2 vUv;" +
  "void main(){ vec3 s = texture2D(tex, vUv).rgb * 0.227;" +
  " s += (texture2D(tex, vUv + dir * 1.385).rgb + texture2D(tex, vUv - dir * 1.385).rgb) * 0.316;" +
  " s += (texture2D(tex, vUv + dir * 3.231).rgb + texture2D(tex, vUv - dir * 3.231).rgb) * 0.070;" +
  " gl_FragColor = vec4(s, 1.0); }", { tex: { value: null }, dir: { value: new THREE.Vector2() } });
const finalMat = shader("uniform sampler2D base, b1, b2; varying vec2 vUv;" +
  "void main(){ vec3 c = texture2D(base, vUv).rgb + 0.55 * texture2D(b1, vUv).rgb + 0.8 * texture2D(b2, vUv).rgb;" +
  " gl_FragColor = vec4(c, 1.0);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}",
  { base: { value: accumRT.texture }, b1: { value: half[0].texture }, b2: { value: quarter[0].texture } },
  { toneMapped: true });
function pass(material, target, clear = true) {
  quad.material = material;
  renderer.setRenderTarget(target);
  if (clear) renderer.clear();
  renderer.render(quadScene, quadCam);
}
function blur(pair, w, h) {
  blurMat.uniforms.tex.value = pair[0].texture; blurMat.uniforms.dir.value.set(1 / w, 0); pass(blurMat, pair[1]);
  blurMat.uniforms.tex.value = pair[1].texture; blurMat.uniforms.dir.value.set(0, 1 / h); pass(blurMat, pair[0]);
}

// ---- scene -----------------------------------------------------------------
const BG = new THREE.Color(0x0b0f1a);
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(BG, 12, 28);
const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 100);
scene.add(new THREE.HemisphereLight(0x6f7fa8, 0x07080c, 0.5));
const spot = new THREE.SpotLight(0xffe2b0, 260, 30, 0.45, 0.6, 1.4);
spot.position.set(0.5, 9, 3.5);
scene.add(spot, spot.target);
const rim = new THREE.DirectionalLight(0x8fb0ff, 0.9);
rim.position.set(-4, 3, -5);
scene.add(rim);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(60, 60),
  new THREE.MeshStandardMaterial({ color: 0x151b2c, roughness: 0.3, metalness: 0.35 }));
floor.rotation.x = -Math.PI / 2;
scene.add(floor);
const wall = new THREE.Mesh(new THREE.PlaneGeometry(60, 30), new THREE.MeshStandardMaterial({ color: 0x111830, roughness: 0.95 }));
wall.position.set(0, 12, -7);
scene.add(wall);
const rodMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.4, 1.8, 1.0) });
for (let i = 0; i < 9; i++) {
  const h = 3 + ((i * 37) % 5) * 0.8;
  const rod = new THREE.Mesh(new THREE.BoxGeometry(0.06, h, 0.06), rodMat);
  rod.position.set(-4 + i, h / 2, -6.2 + (i % 2) * 0.7);
  scene.add(rod);
}

const BOOK = { w: 2.6, h: 0.5, d: 1.7 };
const SPINE_FONT = '"EB Garamond", serif'; // the same family the DOM bars use at the hand-off
const BOOKS = [
  { label: "UM", color: "#2d3f6b", y: 0.25 },
  { label: "DOIS", color: "#1d4a44", y: 0.75 },
  { label: "TRÊS", color: "#5a3b22", y: 1.25 },
];
function spineCanvas(label, bg, ink) {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 197;
  const g = c.getContext("2d");
  g.fillStyle = bg; g.fillRect(0, 0, c.width, c.height);
  g.strokeStyle = ink; g.lineWidth = 6; g.strokeRect(22, 22, c.width - 44, c.height - 44);
  g.fillStyle = ink; g.font = `700 120px ${SPINE_FONT}`; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(label, c.width / 2, c.height / 2 + 6);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}
const books = BOOKS.map((b) => {
  const side = new THREE.MeshStandardMaterial({ color: b.color, roughness: 0.6 });
  // Textures are drawn in setup(), once the web font has loaded.
  const spine = new THREE.MeshStandardMaterial({ emissive: new THREE.Color(1.0, 0.78, 0.42), roughness: 0.45 });
  const pages = new THREE.MeshStandardMaterial({ color: 0xe9e2d0, roughness: 0.8 });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(BOOK.w, BOOK.h, BOOK.d), [pages, side, side, side, spine, side]);
  scene.add(mesh);
  return { mesh, spine };
});
const rings = IMPACTS.map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.92, 1.0, 128),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(3, 2.2, 1.1), transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
  m.rotation.x = -Math.PI / 2;
  m.position.y = 0.012;
  scene.add(m);
  return m;
});
const SPARKS = 56;
const sparks = IMPACTS.map((_, k) => {
  const r = rng(11 + k);
  const vel = Array.from({ length: SPARKS }, () => {
    const a = r() * Math.PI * 2, v = 1.2 + r() * 2.4;
    return [Math.cos(a) * v, 1.5 + r() * 3.0, Math.sin(a) * v];
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SPARKS * 3), 3));
  const pts = new THREE.Points(geo, new THREE.PointsMaterial({ color: new THREE.Color(3, 2.4, 1.4), size: 0.05,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  // Its bounding sphere would be computed once, from whatever frame a worker drew
  // first; never cull, so every worker draws the same sparks.
  pts.frustumCulled = false;
  scene.add(pts);
  return { pts, vel };
});

// ---- the pose at time t ----------------------------------------------------
const SHOTS = {
  wide: [[0, 2.4, 10.5], [0, 0.95, 0]], wideEnd: [[0.4, 2.1, 8.6], [0, 0.85, 0]],
  close: [[2.0, 0.95, 2.7], [0.25, 0.75, 0.85]], closeEnd: [[1.7, 0.9, 2.45], [0.25, 0.75, 0.85]],
  front: [[0, 0.75, 7.2], [0, 0.75, 0]],
};
const _p = new THREE.Vector3(), _l = new THREE.Vector3();
function between(a, b, u) {
  _p.fromArray(SHOTS[a][0]).lerp(new THREE.Vector3().fromArray(SHOTS[b][0]), u);
  _l.fromArray(SHOTS[a][1]).lerp(new THREE.Vector3().fromArray(SHOTS[b][1]), u);
}
function cameraAt(t) {
  if (t < WHIP[0]) between("wide", "wideEnd", t / WHIP[0]);
  else if (t < WHIP[1]) between("wideEnd", "close", easeInOut((t - WHIP[0]) / (WHIP[1] - WHIP[0])));
  else if (t < PULL[0]) between("close", "closeEnd", (t - WHIP[1]) / (PULL[0] - WHIP[1]));
  else if (t < PULL[1]) between("closeEnd", "front", easeInOut((t - PULL[0]) / (PULL[1] - PULL[0])));
  else between("front", "front", 0);
  camera.position.copy(_p);
  camera.lookAt(_l);
  camera.updateMatrixWorld();
}
function glowAt(i, t) {
  if (t < HIGHLIGHT) return 0.12;
  const u = clamp01((t - HIGHLIGHT) / 0.15) * (1 - clamp01((t - PULL[0]) / 0.2)); // off before the hand-off
  return i === 1 ? 0.12 + 1.9 * u : 0.12 - 0.09 * u;
}
function poseAt(t) {
  cameraAt(t);
  books.forEach((b, i) => {
    const T = IMPACTS[i], rest = BOOKS[i].y, u = (t - (T - FALL)) / FALL;
    b.mesh.visible = u > 0;
    b.mesh.position.set(0.05 * (i - 1), t >= T ? rest : rest + 9 * (1 - u * u), 0.08 * (1 - i));
    const wobble = t >= T ? 0.05 * Math.exp(-(t - T) * 9) * Math.sin((t - T) * 38) : 0.3 * (1 - clamp01(u));
    // Square to the camera by the hand-off, so each spine projects to a rectangle.
    const square = 1 - easeInOut(clamp01((t - PULL[0]) / (PULL[1] - PULL[0])));
    b.mesh.rotation.set(0, (i - 1) * 0.07 * square + wobble, 0);
    b.spine.emissiveIntensity = glowAt(i, t);
  });
  IMPACTS.forEach((T, k) => {
    const u = (t - T) / 0.45;
    rings[k].visible = u >= 0 && u < 1;
    rings[k].scale.setScalar(1 + 5 * easeOut(clamp01(u)));
    rings[k].material.opacity = Math.pow(1 - clamp01(u), 2);
    const dt = t - T, s = sparks[k], pos = s.pts.geometry.attributes.position;
    s.pts.visible = dt >= 0 && dt < 0.7;
    const y0 = BOOKS[k].y - BOOK.h / 2;
    s.vel.forEach((v, j) => pos.setXYZ(j, v[0] * dt, Math.max(0.02, y0 + v[1] * dt - 4.9 * dt * dt), v[2] * dt));
    pos.needsUpdate = true;
    s.pts.material.opacity = 1 - clamp01(dt / 0.7);
  });
}
function exposureAt(t) {
  return IMPACTS.reduce((e, T) => e + (t >= T ? 1.3 * Math.exp(-(t - T) / 0.06) : 0), 1.0);
}

// ---- motion blur: average sub-frame renders --------------------------------
const corners = [];
for (const x of [-1, 1]) for (const y of [0, 1.5]) for (const z of [-1, 1]) corners.push(new THREE.Vector3(x * 1.4, y, z * 0.9));
function screenPoints(t) {
  poseAt(t);
  const pts = corners.map((c) => c.clone().project(camera));
  books.forEach((b) => { if (b.mesh.visible) pts.push(b.mesh.position.clone().project(camera)); });
  return pts.map((p) => [(p.x + 1) * W / 2, (1 - p.y) * H / 2]);
}
function samplesAt(t) {
  if (SAMPLES > 0) return SAMPLES;
  const a = screenPoints(t - SHUTTER / 2), b = screenPoints(t + SHUTTER / 2);
  const travel = Math.max(...a.map((p, i) => (b[i] ? Math.hypot(p[0] - b[i][0], p[1] - b[i][1]) : 0)));
  return travel < 1.5 ? 1 : Math.min(64, Math.max(16, Math.ceil(travel / 2)));
}
function drawCanvas(t) {
  const n = samplesAt(t);
  renderer.setRenderTarget(accumRT);
  renderer.setClearColor(0x000000, 1);
  renderer.clear();
  for (let s = 0; s < n; s++) {
    poseAt(n === 1 ? t : t + ((s + 0.5) / n - 0.5) * SHUTTER);
    renderer.setRenderTarget(sceneRT);
    renderer.setClearColor(BG, 1);
    renderer.clear();
    renderer.render(scene, camera);
    addMat.uniforms.tex.value = sceneRT.texture;
    addMat.uniforms.gain.value = 1 / n;
    pass(addMat, accumRT, false);
  }
  poseAt(t);
  renderer.setClearColor(0x000000, 1); // bloom targets start black, not at the background
  brightMat.uniforms.tex.value = accumRT.texture;
  pass(brightMat, half[0]);
  blur(half, W / 2, H / 2);
  addMat.uniforms.tex.value = half[0].texture;
  addMat.uniforms.gain.value = 1;
  pass(addMat, quarter[0]);
  blur(quarter, W / 4, H / 4);
  blur(quarter, W / 4, H / 4);
  renderer.toneMappingExposure = exposureAt(t);
  pass(finalMat, null);
  return n;
}

// ---- text and bars over the canvas ------------------------------------------
const count = document.getElementById("count");
const caption = document.getElementById("caption");
const spans = WORDS.map((w) => {
  const s = document.createElement("span");
  s.textContent = w.w;
  caption.appendChild(s);
  return s;
});
const barsEl = document.getElementById("bars");
const ROWS = ["Três — a do topo", "Dois — a que acendeu", "Um — a primeira"];
const bars = [2, 1, 0].map((i, r) => {
  const el = document.createElement("div");
  el.className = "bar";
  el.style.background = BOOKS[i].color;
  el.innerHTML = `<div class="frame"></div><div class="spine">${BOOKS[i].label}</div><div class="row">${ROWS[r]}</div>`;
  barsEl.appendChild(el);
  return { el, i, r, frame: el.children[0], spine: el.children[1], row: el.children[2] };
});
function spineRect(i) {
  const m = books[i].mesh;
  const xs = [], ys = [];
  for (const x of [-1, 1]) for (const y of [-1, 1]) {
    const p = new THREE.Vector3(x * BOOK.w / 2, y * BOOK.h / 2, BOOK.d / 2).applyMatrix4(m.matrixWorld).project(camera);
    xs.push((p.x + 1) * W / 2); ys.push((1 - p.y) * H / 2);
  }
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
}
function drawText(t) {
  const f = frameOf(t);
  scene.updateMatrixWorld();
  const landed = IMPACTS.filter((T) => f >= frameOf(T));
  if (landed.length && t < GROUPS[0][1]) {
    const k = (f - frameOf(landed[landed.length - 1])) / 4;
    count.textContent = String(landed.length);
    count.style.opacity = "1";
    count.style.transform = `scale(${1 + 0.4 * Math.max(0, 1 - k)})`;
  } else count.style.opacity = "0";
  WORDS.forEach((w, j) => {
    const [a, b] = GROUPS[w.group];
    const shown = t >= a && t < b;
    const o = shown ? clamp01((f - frameOf(w.t) + 1) / 2) : 0;
    const out = clamp01((frameOf(b) - f) / 2);
    spans[j].style.display = shown ? "inline-block" : "none";
    spans[j].style.opacity = String(o * out);
    spans[j].style.filter = `blur(${(8 * (1 - o)).toFixed(2)}px)`;
  });
  // Hand-off: bars cover the projected spines exactly on one frame (no cross-fade,
  // which shows both layers), in the colour the frame really has there, then fly
  // to rows in the same order.
  const show = f >= frameOf(HANDOFF) ? 1 : 0;
  const fly = easeInOut(clamp01((t - 4.75) / 0.4));
  const labelOut = clamp01((t - 4.6) / 0.1), rowIn = clamp01((t - 5.15) / 0.12);
  canvas.style.filter = `blur(${(12 * fly).toFixed(2)}px) brightness(${(1 - 0.55 * fly).toFixed(3)})`;
  bars.forEach((b) => {
    const s = spineRect(b.i);
    const d = { x: 90, y: 760 + b.r * 150, w: 900, h: 120 };
    const lerp = (k) => s[k] + (d[k] - s[k]) * fly;
    Object.assign(b.el.style, { left: `${lerp("x")}px`, top: `${lerp("y")}px`, width: `${lerp("w")}px`,
      height: `${lerp("h")}px`, opacity: String(show) });
    b.spine.style.opacity = String(1 - labelOut);
    b.spine.style.fontSize = `${(s.h * 120 / 197).toFixed(1)}px`;
    b.frame.style.inset = `${(s.h * 22 / 197).toFixed(1)}px`;
    b.frame.style.borderWidth = `${Math.max(1, s.h * 6 / 197).toFixed(1)}px`;
    b.frame.style.opacity = String(1 - labelOut);
    b.row.style.opacity = String(rowIn);
  });
}

// ---- HyperFrames wiring ------------------------------------------------------
const pixel = new Uint8Array(4);
// The bars take the colour the hand-off frame really shows at each spine, after
// light and tone mapping. Measured once in setup from a render of that frame, so
// every render worker gets the same colour whatever frames it draws.
function sampleBarColours() {
  drawCanvas(HANDOFF);
  scene.updateMatrixWorld();
  const probe = document.createElement("canvas");
  probe.width = W; probe.height = H;
  const g = probe.getContext("2d", { willReadFrequently: true });
  g.drawImage(canvas, 0, 0);
  bars.forEach((b) => {
    const s = spineRect(b.i);
    // Inside both the spine and the frame: a spine can be wider than the frame.
    const x = Math.min(Math.max(s.x + s.w * 0.03, 4), W - 9);
    const d = g.getImageData(Math.round(x), Math.round(s.y + s.h * 0.5) - 2, 5, 5).data;
    const avg = [0, 1, 2].map((c) => Math.round(d.filter((_, k) => k % 4 === c).reduce((a, v) => a + v, 0) / 25));
    b.el.style.background = `rgb(${avg.join(", ")})`;
  });
}
function waitForGpu() {
  const gl = renderer.getContext();
  renderer.setRenderTarget(null);
  gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
}
async function setup() {
  await document.fonts.load(`700 120px ${SPINE_FONT}`);
  books.forEach((b, i) => {
    b.spine.map = spineCanvas(BOOKS[i].label, BOOKS[i].color, "#e7c77d");
    b.spine.emissiveMap = spineCanvas(BOOKS[i].label, "#000", "#fff");
    b.spine.needsUpdate = true;
  });
  poseAt(0);
  await renderer.compileAsync(scene, camera);
  sampleBarColours();
  drawCanvas(0);
  waitForGpu();
}
const ready = setup();
window.__hf = window.__hf || {};
window.__hf.buildReady = window.__hf.buildReady || {};
window.__hf.buildReady["three-stage"] = ready;
let shown = null;
let queue = ready;
window.addEventListener("hf-seek", (event) => {
  const { time } = event.detail;
  queue = queue.catch(() => {}).then(() => ready).then(() => {
    if (time === shown) return;
    drawCanvas(time);
    drawText(time);
    waitForGpu();
    shown = time;
  });
  event.detail.waitUntil(queue);
});
