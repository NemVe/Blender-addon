// A tiny static server for the film's page. ES modules and fetch() do not work
// from file://, so the renderers load the page from here.
//   /            -> promo/v2/web/
//   /assets/...  -> promo/v2/assets/   (agent A's flower glTF and motion JSON)
//   /out/...     -> dist/promo/v2/     (anything the page needs from earlier renders)
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const REPO = path.resolve(ROOT, '..', '..');
const MOUNTS = [
  ['/assets/', path.join(ROOT, 'assets')],
  ['/v2/', ROOT],                                       // timeline.json, audio/vo.json
  ['/icons/', path.join(REPO, 'rigmoves', 'icons')],    // the panel's gold icons
  ['/footage/', path.join(REPO, 'dist', 'promo', 'v2', 'footage')],   // JPEG sequences made by prep_footage.py
  ['/out/', path.join(REPO, 'dist', 'promo', 'v2')],
  ['/', path.join(ROOT, 'web')],
];
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json', '.css': 'text/css', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream',
};

function startServer(port = 0) {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split('?')[0]);
      for (const [prefix, dir] of MOUNTS) {
        if (!url.startsWith(prefix)) continue;
        let rel = url.slice(prefix.length) || 'index.html';
        const file = path.normalize(path.join(dir, rel));
        if (!file.startsWith(dir)) break;
        fs.readFile(file, (err, data) => {
          if (err) { res.writeHead(404); res.end('not found: ' + url); return; }
          res.writeHead(200, { 'Content-Type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
                               'Cache-Control': 'no-store' });
          res.end(data);
        });
        return;
      }
      res.writeHead(404); res.end('not found: ' + url);
    });
    server.listen(port, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}
module.exports = { startServer };
if (require.main === module) startServer(8765).then(({ port }) => console.log('serving on http://127.0.0.1:' + port));
