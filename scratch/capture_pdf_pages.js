const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

async function capture() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 900, height: 1200 });

  const html = fs.readFileSync('output/ARCHITECTURE.html', 'utf8');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Take a full page screenshot or test image elements
  const imgs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('img')).map(img => ({
      src: img.src.substring(0, 30) + '...',
      alt: img.alt,
      width: img.width,
      height: img.height,
      visible: img.offsetWidth > 0 && img.offsetHeight > 0
    }));
  });

  console.log('Images in document:', JSON.stringify(imgs, null, 2));

  // Let's capture screenshots of the sections containing diagrams
  const wrappers = await page.$$('.diagram-wrapper');
  for (let i = 0; i < wrappers.length; i++) {
    const shotPath = `scratch/diagram_shot_${i + 1}.png`;
    await wrappers[i].screenshot({ path: shotPath });
    console.log(`Saved screenshot ${shotPath}`);
  }

  await browser.close();
}

capture().catch(console.error);
