const fs = require('fs');

async function testPdfParse() {
  // Let's see if pdf-parse is installed
  try {
    const pdf = require('pdf-parse');
    const dataBuffer = fs.readFileSync('output/ARCHITECTURE.pdf');
    const data = await pdf(dataBuffer);
    console.log('Total pages:', data.numpages);
    console.log('Text preview:\n', data.text.substring(data.text.length - 800));
  } catch (e) {
    console.log('pdf-parse error:', e.message);
  }
}

testPdfParse();
