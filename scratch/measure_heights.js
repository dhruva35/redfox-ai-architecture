const puppeteer = require('puppeteer');
const fs = require('fs');

async function measureSectionHeights() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 800, height: 1200 });
  const html = fs.readFileSync('output/ARCHITECTURE.html', 'utf8');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Let's measure each section's height
  const sectionHeights = await page.evaluate(() => {
    // get elements between page breaks
    const breaks = Array.from(document.querySelectorAll('div[style*="page-break-after"]'));
    const results = [];
    let startY = 0;
    
    breaks.forEach((b, i) => {
      const rect = b.getBoundingClientRect();
      const height = rect.top - startY;
      results.push({ section: i + 1, height: Math.round(height) });
      startY = rect.bottom;
    });
    // last section
    results.push({ section: breaks.length + 1, height: Math.round(document.body.scrollHeight - startY) });
    return results;
  });

  console.log('Section Heights (pixels, standard A4 printable is ~950px):', sectionHeights);
  await browser.close();
}

measureSectionHeights().catch(console.error);
