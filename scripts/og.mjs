// Renders the 1200x630 share images: public/img/og/YYYY.jpg and home.jpg.
// Usage: node scripts/og.mjs years.json public      (run via `python3 build.py --images`)
// Needs Playwright with Chromium (resolved from the global/local node_modules).
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [yearsFile, publicDir] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(yearsFile, 'utf8'));
const years = data.years.slice().sort((a, b) => a.year - b.year);
const first = years[0].year, last = years[years.length - 1].year;
const outDir = path.join(publicDir, 'img', 'og');
fs.mkdirSync(outDir, { recursive: true });

const dataUri = (f) => 'data:' + (f.endsWith('.png') ? 'image/png' : 'image/jpeg') + ';base64,' +
  fs.readFileSync(path.join(publicDir, f)).toString('base64');
const logo = dataUri('img/izo-logo.png');
const card = (y) => dataUri(`img/cards/${y}.jpg`);

const label = (t) => `<div style="position:absolute;left:32px;bottom:28px;display:flex;align-items:center;gap:14px;background:#fff;border-radius:999px;padding:10px 22px 10px 16px;box-shadow:0 4px 18px rgba(0,0,0,.25);font:700 30px/1 Arial,sans-serif;color:#111"><img src="${logo}" style="height:30px">${t}</div>`;
const play = `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center"><div style="width:120px;height:120px;border-radius:50%;background:rgba(255,255,255,.9);display:flex;align-items:center;justify-content:center"><div style="margin-left:10px;width:0;height:0;border-left:44px solid #111;border-top:28px solid transparent;border-bottom:28px solid transparent"></div></div></div>`;

function art(e) {
  const y = e.year;
  if (e.video && !e.thumb) {
    return `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:700 260px/1 Arial,sans-serif;color:rgba(255,255,255,.08)">${y}</div>${play}`;
  }
  if (e.video) {
    return `<img src="${card(y)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">${play}`;
  }
  return `<img src="${card(y)}" style="position:absolute;inset:24px 24px 24px 24px;width:calc(100% - 48px);height:calc(100% - 48px);object-fit:contain">`;
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
const shot = async (html, name) => {
  await page.setContent(html);
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(outDir, name), type: 'jpeg', quality: 84 });
  console.log('og', name);
};

for (const e of years) {
  await shot(`<body style="margin:0"><div style="position:relative;width:1200px;height:630px;overflow:hidden;background:${e.card_bg}">${art(e)}${label(String(e.year))}</div></body>`, `${e.year}.jpg`);
}

// home collage: years that set "collage": "cover" | "contain", newest first
const tiles = years.filter((e) => e.collage).reverse().map((e) =>
  `<div style="background:${e.card_bg};border-radius:8px;overflow:hidden"><img src="${card(e.year)}" style="width:100%;height:100%;object-fit:${e.collage}"></div>`).join('');
await shot(`<body style="margin:0"><div style="position:relative;width:1200px;height:630px;background:#e6e7e8;overflow:hidden">
<div style="position:absolute;inset:-40px -60px;display:grid;grid-template-columns:repeat(4,1fr);gap:16px;transform:rotate(-6deg) scale(1.05);opacity:.95">${tiles}</div>
<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;border-radius:16px;padding:36px 48px;box-shadow:0 12px 40px rgba(0,0,0,.3);text-align:center">
<img src="${logo}" style="height:56px;display:block;margin:0 auto 18px"><div style="font:700 64px/1 Arial,sans-serif;color:#8C2108;letter-spacing:.02em">XMAS ARCHIVE</div><div style="font:400 30px/1 Arial,sans-serif;color:#3B403E;margin-top:14px">${first} – ${last}</div></div></div></body>`, 'home.jpg');

await browser.close();
