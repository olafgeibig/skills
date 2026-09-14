#!/usr/bin/env node
/**
 * clean-srt.js — de-duplicate yt-dlp SRT output from YouTube auto-captions.
 *
 * YouTube auto-captions are a rolling window: each SRT block contains the
 * previous text line plus the new one, so every sentence appears 2-3 times in
 * consecutive blocks. This script keeps only the LAST non-empty text line of
 * each block and drops it if it equals the previously kept line.
 *
 * Usage: node clean-srt.js <input.srt> [output.txt]
 *   output defaults to <input basename>.txt
 *
 * Exit codes: 0 ok, 1 missing/empty input, 2 no SRT blocks found.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';

const [input, output] = process.argv.slice(2);
if (!input) {
  console.error('usage: node clean-srt.js <input.srt> [output.txt]');
  process.exit(1);
}

let text;
try {
  text = readFileSync(input, 'utf8');
} catch {
  console.error(`error: cannot read ${input}`);
  process.exit(1);
}

// Split into blocks on one-or-more blank lines; drop empties.
const blocks = text
  .replace(/\r\n/g, '\n')
  .split(/\n\s*\n/)
  .map((b) => b.trim())
  .filter(Boolean);

const kept = [];
let blocksWithText = 0;

for (const block of blocks) {
  const lines = block.split('\n').map((l) => l.trim()).filter(Boolean);
  // A real SRT block: index line, timestamp line, then >=1 text line.
  if (lines.length < 3 || !/^\d+$/.test(lines[0])) continue;
  const lastLine = lines[lines.length - 1];
  if (!lastLine) continue;
  blocksWithText++;
  if (kept[kept.length - 1] !== lastLine) kept.push(lastLine);
}

if (blocksWithText === 0) {
  console.error('error: no SRT blocks found — is this really an SRT file?');
  process.exit(2);
}

const outPath = output ?? basename(input).replace(/\.srt$/i, '') + '.txt';
writeFileSync(outPath, kept.join('\n') + '\n', 'utf8');

console.log(`blocks=${blocksWithText} lines=${kept.length} -> ${outPath}`);
