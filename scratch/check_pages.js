const puppeteer = require('puppeteer');
const fs = require('fs');

async function testSections() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const html = fs.readFileSync('output/ARCHITECTURE.html', 'utf8');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Get bounding rect of h2 elements
  const h2s = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('h2')).map(el => {
      const rect = el.getBoundingClientRect();
      return { text: el.innerText, top: rect.top, height: rect.height };
    });
  });
  console.log('H2 positions:', JSON.stringify(h2s, null, 2));

  // Let's also check images and tables
  const elements = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('h2, table, img, pre')).map(el => {
      return { tag: el.tagName, text: el.innerText ? el.innerText.substring(0, 30) : (el.src ? el.src.split('/').pop() : ''), height: Math.round(el.getBoundingClientRect().height) };
    });
  });
  console.log('Key element heights:', JSON.stringify(elements, null, 2));

  await browser.close();
}

testSections().catch(console.error);
