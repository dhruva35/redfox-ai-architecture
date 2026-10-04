const puppeteer = require('puppeteer');
const path = require('path');

async function testRender() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 1400 });
  await page.goto('file:///' + path.resolve('output/ARCHITECTURE.html').replace(/\\/g, '/'), { waitUntil: 'networkidle0' });

  const imageStats = await page.evaluate(() => {
    const imgs = document.querySelectorAll('img.diagram-img');
    return Array.from(imgs).map(img => ({
      alt: img.alt,
      renderedWidth: img.clientWidth,
      renderedHeight: img.clientHeight,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      complete: img.complete
    }));
  });

  console.log('Image rendering stats in browser:', JSON.stringify(imageStats, null, 2));
  await browser.close();
}

testRender().catch(console.error);
