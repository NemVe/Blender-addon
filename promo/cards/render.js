// Frame-by-frame renderer for the CopyThat cards.
//   node render.js title.html title 105 30            (all frames -> title/0001.png ...)
//   node render.js end.html end 90 30 --alpha         (transparent PNGs)
//   node render.js title.html _review 105 30 --only 20,50,104   (just those frames)
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [html, outDir, nStr, fpsStr] = process.argv.slice(2);
  const n = parseInt(nStr, 10), fps = parseFloat(fpsStr);
  const alpha = process.argv.includes('--alpha');
  const oi = process.argv.indexOf('--only');
  const only = oi > -1 ? process.argv[oi + 1].split(',').map(Number) : null;
  const prefix = (process.argv.includes('--prefix') ? process.argv[process.argv.indexOf('--prefix') + 1] : '');

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.resolve(html));
  await page.evaluate(() => document.fonts.ready);
  const t0 = Date.now();
  let count = 0;
  for (let i = 1; i <= n; i++) {
    if (only && !only.includes(i)) continue;
    const t = (i - 1) / fps;
    await page.evaluate(t => window.setTime(t), t);
    const name = prefix + String(i).padStart(4, '0') + '.png';
    await page.screenshot({ path: path.join(outDir, name), omitBackground: alpha });
    count++;
  }
  console.log(count + ' frames in ' + ((Date.now() - t0) / 1000).toFixed(1) + ' s -> ' + outDir);
  await browser.close();
})();
