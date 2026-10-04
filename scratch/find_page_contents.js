const puppeteer = require('puppeteer');
const fs = require('fs');

async function findPageContents() {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const html = fs.readFileSync('output/ARCHITECTURE.html', 'utf8');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Let's print out the exact client heights of each section divided by the page breaks
  const sections = await page.evaluate(() => {
    // split by <div style="page-break-after: always;"></div>
    const parts = document.body.innerHTML.split(/<div style="page-break-after:\s*always;\s*"><\/div>/i);
    return parts.map((part, index) => {
      const temp = document.createElement('div');
      temp.innerHTML = part;
      return {
        sectionIndex: index + 1,
        title: temp.querySelector('h1, h2') ? temp.querySelector('h1, h2').innerText : 'No Title',
        textLength: temp.innerText.length
      };
    });
  });

  console.log('Document parts:', JSON.stringify(sections, null, 2));
  console.log('Total sections separated by page breaks:', sections.length);

  await browser.close();
}

findPageContents().catch(console.error);
