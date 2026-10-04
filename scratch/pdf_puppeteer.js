const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

async function generatePDF() {
  console.log('Reading output/ARCHITECTURE_PDF.md...');
  let mdContent = fs.readFileSync('output/ARCHITECTURE_PDF.md', 'utf8');

  // Replace diagram/image markdown syntax with base64 embedded <img> tags directly
  mdContent = mdContent.replace(/!\[(.*?)\]\(diagrams\/([^)]+)\)/g, (match, alt, filename) => {
    const filePath = path.resolve('output/diagrams', filename);
    if (fs.existsSync(filePath)) {
      const b64 = fs.readFileSync(filePath).toString('base64');
      console.log(`Embedded base64 for ${filename} (${b64.length} chars)`);
      return `<div class="diagram-wrapper"><img src="data:image/png;base64,${b64}" alt="${alt || filename}" class="diagram-img"/></div>`;
    } else {
      console.warn(`File not found: ${filePath}`);
      return match;
    }
  });

  // Convert markdown to HTML
  const htmlBody = marked(mdContent);

  const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  
  * { box-sizing: border-box; }
  body { 
    font-family: 'Inter', Arial, -apple-system, sans-serif; 
    font-size: 12px; 
    line-height: 1.55; 
    color: #1e293b; 
    max-width: 860px; 
    margin: 0 auto; 
    padding: 0 10px; 
  }
  
  h1 { 
    font-size: 23px; 
    color: #0f172a; 
    border-bottom: 3px solid #e11d48; 
    padding-bottom: 6px; 
    margin-top: 14px;
    margin-bottom: 10px;
  }
  
  h2 { 
    font-size: 17px; 
    color: #0f172a; 
    border-bottom: 1.5px solid #e2e8f0; 
    padding-bottom: 5px; 
    margin-top: 20px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }
  
  h3 { 
    font-size: 14px; 
    color: #334155; 
    margin-top: 14px; 
    margin-bottom: 6px;
    page-break-after: avoid;
  }
  
  p, li { 
    color: #334155; 
  }

  ul, ol {
    margin-top: 4px;
    margin-bottom: 10px;
    padding-left: 20px;
  }

  li {
    margin-bottom: 3px;
  }
  
  code { 
    background: #f1f5f9; 
    border: 1px solid #e2e8f0;
    border-radius: 4px; 
    padding: 2px 5px; 
    font-size: 11px; 
    font-family: 'Courier New', Courier, monospace; 
    color: #0f172a;
  }
  
  pre { 
    background: #0f172a; 
    color: #f8fafc; 
    padding: 12px; 
    border-radius: 6px; 
    overflow-x: auto; 
    font-size: 10.5px; 
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 12px 0;
  }
  
  pre code { 
    background: transparent; 
    border: none;
    color: inherit; 
    padding: 0; 
  }
  
  table { 
    width: 100%; 
    border-collapse: collapse; 
    margin: 14px 0; 
    font-size: 11px; 
    page-break-inside: avoid;
  }
  
  th { 
    background: #0f172a; 
    color: #ffffff; 
    padding: 7px 9px; 
    text-align: left; 
    font-weight: 600;
  }
  
  td { 
    border: 1px solid #e2e8f0; 
    padding: 7px 9px; 
    vertical-align: top; 
  }
  
  tr:nth-child(even) td { 
    background: #f8fafc; 
  }
  
  .diagram-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 10px 0;
    page-break-inside: avoid;
  }

  .diagram-img { 
    max-width: 94%; 
    max-height: 250px;
    object-fit: contain;
    display: block; 
    margin: 0 auto;
    border: 1px solid #cbd5e1; 
    border-radius: 6px; 
    background: #ffffff;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    page-break-inside: avoid;
  }
  
  blockquote { 
    border-left: 4px solid #e11d48; 
    margin: 10px 0; 
    padding: 8px 14px; 
    background: #fff1f2; 
    color: #475569; 
    border-radius: 0 4px 4px 0;
  }
  
  hr { 
    border: none; 
    border-top: 1px solid #e2e8f0; 
    margin: 18px 0; 
  }
  
  a { 
    color: #e11d48; 
    text-decoration: none; 
    font-weight: 500;
  }
  
  strong { 
    color: #0f172a; 
  }

  @media print {
    body {
      margin: 0;
      padding: 0;
    }
    .page-break {
      page-break-after: always;
    }
  }
</style>
</head>
<body>
${htmlBody}
</body>
</html>`;

  fs.writeFileSync('output/ARCHITECTURE.html', html, 'utf8');
  console.log('Saved output/ARCHITECTURE.html');

  const browser = await puppeteer.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.pdf({
    path: 'output/ARCHITECTURE.pdf',
    format: 'A4',
    margin: { top: '22mm', bottom: '20mm', left: '16mm', right: '16mm' },
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: `
      <div style="font-size: 8px; font-family: Arial, sans-serif; color: #64748b; width: 100%; padding: 0 16mm; display: flex; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
        <span><strong>Redfox Cyber Security</strong> | AI Penetration Testing Platform Architecture</span>
        <span>Candidate: Gangari Dhruvaveer</span>
      </div>
    `,
    footerTemplate: `
      <div style="font-size: 8px; font-family: Arial, sans-serif; color: #64748b; width: 100%; padding: 0 16mm; display: flex; justify-content: space-between; border-top: 1px solid #e2e8f0; padding-top: 4px;">
        <span>Confidential - For Candidate Evaluation Only</span>
        <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
      </div>
    `
  });
  await browser.close();
  console.log('Successfully generated output/ARCHITECTURE.pdf with embedded images!');
}

generatePDF().catch(console.error);
