import assert from "node:assert/strict";
import { mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { build } from "esbuild";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const tempDir = resolve(projectRoot, ".tmp-tests");
const outputFile = resolve(tempDir, "markdownRenderer.mjs");

await mkdir(tempDir, { recursive: true });

await build({
  entryPoints: [resolve(projectRoot, "src/utils/markdownRenderer.ts")],
  outfile: outputFile,
  bundle: true,
  format: "esm",
  platform: "node",
  sourcemap: false,
  logLevel: "silent"
});

const { normalizeMessage, renderMessageHtml } = await import(pathToFileURL(outputFile).href);

const listHtml = renderMessageHtml("说明：- 第一项 - 第二项");
assert.match(listHtml, /<ul>/);
assert.match(listHtml, /<li>第一项/);

const compactTable = "天气：| 日期 | 天气 | 温度 | | --- | --- | --- | | 6月24日 | 晴 | 30℃ |";
const normalizedTable = normalizeMessage(compactTable);
assert.match(normalizedTable, /\| 日期 \| 天气 \| 温度 \|/);
assert.match(normalizedTable, /\| --- \| --- \| --- \|/);
assert.match(renderMessageHtml(compactTable), /<table>/);
assert.match(renderMessageHtml(compactTable), /<td>晴<\/td>/);

const unsafeLinkHtml = renderMessageHtml("[危险](javascript:alert(1))");
assert.doesNotMatch(unsafeLinkHtml, /href="javascript:/i);

await rm(tempDir, { recursive: true, force: true });
