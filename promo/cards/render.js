// Frame-by-frame renderer for the CopyThat cards.
//   node render.js title.html title 105 30            (all frames -> title/0001.png ...)
//   node render.js end.html end 120 30 --alpha        (transparent PNGs)
//   node render.js title.html _review 105 30 --only 20,50,104   (just those frames)
//
// The page keeps its 1920x1080 layout whatever the output size: --scale sets
// the device pixel ratio, so text and edges are drawn at the full output
// resolution, not upscaled afterwards. 2560x1440 is a scale of 4/3:
//   node render.js title.html title 105 30 --scale 1.3333333
//
// The cards that take text read it from the page address, so --query gives
// them the part after the "?". Quote it. A space can stay a space (or be %20);
// an & or a # inside the text has to be written %26 or %23:
//   node render.js statement.html s1 45 30 --alpha --scale 1.3333333 --query "text=21 moving parts.&dur=1.5"
//   node render.js lower_third.html lt 90 30 --alpha --scale 1.3333333 --query "text=Pose it once. Record.&dur=3"
//   node render.js tag.html tag 90 30 --alpha --scale 1.3333333 --query "text=Rendered in Cycles&dur=3"
//
// Frame i is posed at t = (i - 1) / fps, so a card of D seconds is D * fps
// frames, and the last of them is the clear (or black) one. At 30 fps:
//   statement.html    <out> 45 30  --alpha   (dur 1.5 by default)
//   lower_third.html  <out> 90 30  --alpha   (dur 3)
//   tag.html          <out> 90 30  --alpha   (dur 3)
//   title_short.html  <out> 60 30            (2 s, opaque, black at both ends)
//   end.html          <out> 120 30 --alpha   (4 s, holds on its last frame)
// For another dur, frames = dur * 30, and the same dur goes in --query.
const { chromium } = require('playwright');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const [html, outDir, nStr, fpsStr] = process.argv.slice(2);
  const n = parseInt(nStr, 10), fps = parseFloat(fpsStr);
  const alpha = process.argv.includes('--alpha');
  const arg = name => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : null; };
  const only = arg('--only') !== null ? arg('--only').split(',').map(Number) : null;
  const prefix = arg('--prefix') || '';
  const scale = arg('--scale') !== null ? parseFloat(arg('--scale')) : 1;
  const query = arg('--query');

  // pathToFileURL gives file:///C:/... on Windows and escapes odd characters;
  // setting .search escapes the spaces and any non-ASCII text of the query.
  const url = pathToFileURL(path.resolve(html));
  if (query) url.search = query.replace(/^\?/, '');

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: scale });
  await page.goto(url.href);
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
  console.log(count + ' frames in ' + ((Date.now() - t0) / 1000).toFixed(1) + ' s -> ' + outDir +
    (scale !== 1 ? '  (scale ' + scale + ')' : ''));
  await browser.close();
})();
