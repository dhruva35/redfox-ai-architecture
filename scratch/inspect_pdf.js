const fs = require('fs');

async function extractPages() {
  // Let's inspect the text using pdfjs-dist if available or regex markers
  const data = fs.readFileSync('output/ARCHITECTURE.pdf', 'utf8');
  console.log('PDF total length:', data.length);
}

extractPages().catch(console.error);
