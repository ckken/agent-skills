#!/usr/bin/env node

import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import process from 'node:process';

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const options = { timeoutMs: 180_000 };
  for (let i = 0; i < argv.length; i += 1) {
    const value = argv[i];
    if (value === '--url') options.url = argv[++i];
    else if (value === '--output') options.output = argv[++i];
    else if (value === '--timeout-ms') options.timeoutMs = Number(argv[++i]);
    else if (value === '--force') options.force = true;
    else if (value === '--allow-console-errors') options.allowConsoleErrors = true;
    else if (value === '--help' || value === '-h') options.help = true;
    else throw new Error(`Unknown argument: ${value}`);
  }
  return options;
}

function usage() {
  return [
    'Usage:',
    '  node export_editable_pptx.mjs --url <slide-url> --output <file.pptx>',
    '',
    'Options:',
    '  --timeout-ms <ms>  Export timeout (default: 180000)',
    '  --force            Replace an existing output file',
    '  --allow-console-errors  Keep the export when the page logs console errors',
  ].join('\n');
}

async function loadPlaywright() {
  try {
    return require('playwright');
  } catch (requireError) {
    try {
      return await import('playwright');
    } catch (importError) {
      throw new Error(
        `Playwright is required. Install it in the active runtime or set NODE_PATH to a runtime that provides it.\n${requireError}\n${importError}`,
      );
    }
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(`${usage()}\n`);
    return;
  }
  if (!options.url || !options.output) throw new Error(`--url and --output are required.\n${usage()}`);
  if (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0) {
    throw new Error('--timeout-ms must be a positive number');
  }

  const output = path.resolve(options.output);
  if (path.extname(output).toLowerCase() !== '.pptx') {
    throw new Error('--output must end with .pptx');
  }
  if (!options.force) {
    try {
      await fs.access(output);
      throw new Error(`Output already exists: ${output}. Use --force to replace it.`);
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  await fs.mkdir(path.dirname(output), { recursive: true });

  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(options.timeoutMs);

  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  try {
    await page.goto(options.url, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: /Download|下载/i }).click();
    const exportItem = page.getByRole('menuitem', { name: /Export as PPTX|导出.*PPTX/i });
    try {
      await exportItem.waitFor({ state: 'visible', timeout: Math.min(options.timeoutMs, 5_000) });
    } catch {
      throw new Error(
        'The Download menu does not expose "Export as PPTX". Start the editable-PPTX exporter branch and retry.',
      );
    }
    const downloadPromise = page.waitForEvent('download');
    await exportItem.click();
    const download = await downloadPromise;
    const failure = await download.failure();
    if (failure) throw new Error(`Download failed: ${failure}`);
    if (consoleErrors.length > 0 && !options.allowConsoleErrors) {
      throw new Error(`Browser console errors blocked the export:\n${consoleErrors.join('\n')}`);
    }
    await download.saveAs(output);

    const stat = await fs.stat(output);
    if (stat.size === 0) throw new Error('Downloaded PPTX is empty');

    process.stdout.write(
      `${JSON.stringify(
        {
          ok: true,
          output,
          bytes: stat.size,
          suggestedFilename: download.suggestedFilename(),
          consoleErrors,
        },
        null,
        2,
      )}\n`,
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
