// Renders the film's page with Playwright on the GPU.   node promo/v2/build/render.js <mode> key=value ...
//   shots  k=0.25 out=DIR times=1,2,3 | span=a:b:n      PNGs at those seconds (previews)
//   film   k=1 out=DIR workers=5 [beats=id,id] [fps=60]  every beat as its own H.264 segment (CRF 16), several at a time
//   cues                                                 writes the clicks and pops the beats declare into timeline.json
const { chromium } = require('../web/node_modules/playwright');
const { startServer } = require('./serve');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const mode = process.argv[2];
const A = Object.fromEntries(process.argv.slice(3).map(a => { const i = a.indexOf('='); return [a.slice(0, i), a.slice(i + 1)]; }));
const K = parseFloat(A.k || '1');
const FPS = parseInt(A.fps || '60', 10);
const ARGS = ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-renderer-backgrounding',
  '--disable-background-timer-throttling', '--force-device-scale-factor=1'];

async function open(port, tag) {
  const browser = await chromium.launch({ channel: 'chromium', headless: true, args: ARGS });
  const page = await browser.newPage({ viewport: { width: Math.round(2560 * K), height: Math.round(1440 * K) }, deviceScaleFactor: 1 });
  page.on('console', m => { const t = m.text(); if (m.type() === 'error' || m.type() === 'warning' || /^LOG /.test(t)) console.log(tag, m.type(), t.slice(0, 300)); });
  page.on('pageerror', e => console.log(tag, 'PAGE ERROR', String(e).slice(0, 600)));
  await page.goto(`http://127.0.0.1:${port}/index.html?k=${K}`);
  await page.evaluate(() => window.ready);
  return { browser, page };
}

async function shots(port) {
  const { browser, page } = await open(port, 'shots');
  let times = [];
  if (A.times) times = A.times.split(',').map(Number);
  if (A.span) { const [a, b, n] = A.span.split(':').map(Number); for (let i = 0; i < n; i++) times.push(n > 1 ? a + (b - a) * i / (n - 1) : a); }
  fs.mkdirSync(A.out, { recursive: true });
  let i = 0;
  for (const t of times) {
    const t0 = Date.now();
    await page.evaluate(x => window.setTime(x), t);
    const name = path.join(A.out, `${String(++i).padStart(3, '0')}_${t.toFixed(2)}.png`);
    await page.screenshot({ path: name, type: 'png' });
    if (A.verbose) console.log(name, Date.now() - t0, 'ms');
    if (A.eval) console.log('EVAL', t, JSON.stringify(await page.evaluate(A.eval)));
  }
  await browser.close();
}

function encoder(file, fps) {
  const args = ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p',
    '-c:v', 'libx264', '-preset', A.preset || 'medium', '-crf', A.crf || '16', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-r', String(fps), file];
  const p = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'pipe'] });
  let err = '';
  p.stderr.on('data', d => { err += d; });
  p.stdin.on('error', () => {});
  const done = new Promise(res => p.on('close', code => res({ code, err })));
  return { p, done };
}

async function film(port) {
  const T = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'timeline.json'), 'utf8'));
  let beats = T.beats.map((b, i) => ({ ...b, n: i + 1 }));
  if (A.beats) beats = beats.filter(b => A.beats.split(',').includes(b.id));
  const outDir = path.join(A.out, 'segments');
  fs.mkdirSync(outDir, { recursive: true });
  const queue = beats.slice();
  const nWorkers = Math.min(parseInt(A.workers || '4', 10), queue.length);
  const t00 = Date.now(); let frames = 0; const total = beats.reduce((s, b) => s + Math.round((b.end - b.start) * FPS), 0);
  const worker = async w => {
    const { browser, page } = await open(port, 'w' + w);
    for (let b = queue.shift(); b; b = queue.shift()) {
      const file = path.join(outDir, `${String(b.n).padStart(2, '0')}_${b.id}.mp4`);
      const f0 = Math.round(b.start * FPS), f1 = Math.round(b.end * FPS);
      const enc = encoder(file, FPS);
      for (let f = f0; f < f1; f++) {
        await page.evaluate(x => window.setTime(x), f / FPS);
        const buf = await page.screenshot({ type: 'png' });
        if (!enc.p.stdin.write(buf)) await new Promise(r => enc.p.stdin.once('drain', r));
        frames++;
      }
      enc.p.stdin.end();
      const r = await enc.done;
      console.log(`w${w} ${b.id} ${f1 - f0} frames  [${frames}/${total}, ${((Date.now() - t00) / 1000).toFixed(0)} s]`, r.code ? 'FFMPEG FAILED ' + r.err.slice(0, 300) : '');
    }
    await browser.close();
  };
  await Promise.all([...Array(nWorkers)].map((_, i) => worker(i)));
  console.log('done in', ((Date.now() - t00) / 1000).toFixed(0), 's');
}

async function cues(port) {
  const { browser, page } = await open(port, 'cues');
  const all = await page.evaluate(() => window.getCues());
  await browser.close();
  const file = path.join(__dirname, '..', 'timeline.json');
  const T = JSON.parse(fs.readFileSync(file, 'utf8'));
  T.clicks = all.filter(c => c.kind !== 'pop').map(({ t, beat, kind, what }) => ({ t, beat, kind, what }));
  T.pops = all.filter(c => c.kind === 'pop').map(({ t, beat, name }) => ({ t, beat, name }));
  fs.writeFileSync(file, JSON.stringify(T, null, 1) + '\n');
  console.log('clicks', T.clicks.length, 'pops', T.pops.length);
}

(async () => {
  const { server, port } = await startServer(0);
  try { await { shots, film, cues }[mode](port); } catch (e) { console.error(e); process.exitCode = 1; }
  server.close();
})();
