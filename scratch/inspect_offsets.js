const puppeteer = require('puppeteer');
const fs = require('fs');

async function inspectPDFPages() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  // Read PDF text using pdfjs or let's inspect the layout of page 7 and 8 in puppeteer print emulation
  const html = fs.readFileSync('output/ARCHITECTURE.html', 'utf8');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Get total height of Section 7 (Cloud Deployment & 8-12 Week Roadmap)
  const h2s = await page.evaluate(() => {
    const list = Array.from(document.querySelectorAll('h2'));
    return list.map(h => ({
      text: h.innerText,
      offsetTop: h.offsetTop
    }));
  });
  console.log('Section offsets:', h2s);

  await browser.close();
}

inspectPDFPages().catch(console.error);
