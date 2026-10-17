// Which Chromium setup gives real-GPU WebGL2, and how fast is a 2560x1440 frame?
const { chromium } = require('../web/node_modules/playwright');
const { startServer } = require('./serve');
(async () => {
  const { server, port } = await startServer(0);
  const configs = {
    shell_d3d11: { args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] },
    new_headless_d3d11: { channel: 'chromium', args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] },
  };
  for (const [name, cfg] of Object.entries(configs)) {
    let browser;
    try {
      browser = await chromium.launch({ headless: true, ...cfg });
      const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 4 / 3 });
      await page.setContent('<canvas id=c width=2560 height=1440 style="width:1920px;height:1080px"></canvas>');
      const info = await page.evaluate(() => {
        const c = document.getElementById('c'); const gl = c.getContext('webgl2', { antialias: true });
        if (!gl) return 'no webgl2';
        const e = gl.getExtension('WEBGL_debug_renderer_info');
        const g = gl.getContext && 0;
        gl.clearColor(0.2, 0.1, 0.4, 1); gl.clear(gl.COLOR_BUFFER_BIT);
        return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'n/a', maxTex: gl.getParameter(gl.MAX_TEXTURE_SIZE),
                 maxSamples: gl.getParameter(gl.MAX_SAMPLES), floatBuf: !!gl.getExtension('EXT_color_buffer_float') };
      });
      console.log(name, JSON.stringify(info));
      for (const type of ['png', 'jpeg']) {
        const t0 = Date.now(); const N = 12;
        for (let i = 0; i < N; i++) await page.screenshot({ type, quality: type === 'jpeg' ? 95 : undefined });
        console.log('  ', type, ((Date.now() - t0) / N).toFixed(0), 'ms/frame');
      }
    } catch (e) { console.log(name, 'FAILED', String(e).split('\n')[0]); }
    if (browser) await browser.close();
  }
  server.close();
})();
