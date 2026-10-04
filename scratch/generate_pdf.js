const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

const srcMd = 'output/ARCHITECTURE.md';
const tempMd = 'output/ARCHITECTURE_PDF.md';

let content = fs.readFileSync(srcMd, 'utf8');

// Replace mermaid blocks with image links
// We need to map the diagrams appropriately. Since we don't have explicit filenames in the mermaid blocks,
// we will have to use some heuristic or replace them in order if we know it.
// The blocks in ARCHITECTURE.md are:
// 1. system_architecture (Section 4.1)
// 2. agent_loop (Section 5.1)
// 3. engagement_state_erd (Section 5.2)
// 4. trust_boundaries (Section 8.2 -> Wait, it's 8.2? Actually it's Trust Boundaries in 8.1 / 8.2)
// 5. gcp_deployment (Section 9.1)
// Wait, I should just use regex to replace each block with the corresponding image.

const diagrams = [
  'diagrams/system_architecture.png',
  'diagrams/agent_loop.png',
  'diagrams/engagement_state_erd.png',
  'diagrams/trust_boundaries.png',
  'diagrams/gcp_deployment.png',
  'diagrams/skill_pack_loading.png'
];

let index = 0;
content = content.replace(/```mermaid[\s\S]*?```/g, (match) => {
  if (index < diagrams.length) {
    const imgPath = diagrams[index];
    index++;
    return `![Diagram](${imgPath})`;
  }
  return match;
});

fs.writeFileSync(tempMd, content, 'utf8');
console.log('Created temporary Markdown file for PDF conversion.');

try {
  console.log('Generating PDF using md-to-pdf...');
  execSync('npx -y md-to-pdf output/ARCHITECTURE_PDF.md', { stdio: 'inherit' });
  
  if (fs.existsSync('output/ARCHITECTURE_PDF.pdf')) {
    fs.renameSync('output/ARCHITECTURE_PDF.pdf', 'output/ARCHITECTURE.pdf');
    console.log('Successfully generated output/ARCHITECTURE.pdf');
    fs.unlinkSync(tempMd); // Clean up
  } else {
    console.error('Failed to find generated PDF.');
  }
} catch (error) {
  console.error('Error during PDF generation:', error.message);
}
