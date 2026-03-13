#!/usr/bin/env node
/**
 * Capture screenshots of all app tabs.
 * Prerequisites: npm install playwright (in project root or frontend)
 * Run with app at http://localhost:3000: node scripts/capture_screenshots.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');

const TABS = [
  { name: 'warm-contacts', selector: 'button:has-text("Warm Contacts")' },
  { name: 'todo', selector: 'button:has-text("TODO")' },
  { name: 'summaries', selector: 'button:has-text("Summaries")' },
  { name: 'input-prompt', selector: 'button:has-text("Input Prompt")' },
];

async function main() {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
  try {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    for (const tab of TABS) {
      await page.click(tab.selector);
      await page.waitForTimeout(500);
      const filepath = path.join(SCREENSHOTS_DIR, `${tab.name}.png`);
      await page.screenshot({ path: filepath, fullPage: true });
      console.log('Saved', filepath);
    }
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
