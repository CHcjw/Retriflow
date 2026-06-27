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

const listHtml = renderMessageHtml("\u8bf4\u660e\uff1a- \u7b2c\u4e00\u9879 - \u7b2c\u4e8c\u9879");
assert.match(listHtml, /<ul>/);
assert.match(listHtml, /<li>\u7b2c\u4e00\u9879/u);

const compactTable = "\u5929\u6c14\uff1a| \u65e5\u671f | \u5929\u6c14 | \u6e29\u5ea6 | | --- | --- | --- | | 6\u670824\u65e5 | \u6674 | 30\u2103 |";
const normalizedTable = normalizeMessage(compactTable);
assert.match(normalizedTable, /\| \u65e5\u671f \| \u5929\u6c14 \| \u6e29\u5ea6 \|/u);
assert.match(normalizedTable, /\| --- \| --- \| --- \|/);
assert.match(renderMessageHtml(compactTable), /<table>/);
assert.match(renderMessageHtml(compactTable), /<td>\u6674<\/td>/u);

const compactAnswerTable = "\u7ed3\u8bba\u5982\u4e0b\uff1a| \u6307\u6807 | \u7ed3\u679c || --- | --- || \u6700\u9ad8\u6e29 | 30\u2103 || \u98ce\u529b | 3\u7ea7 |";
assert.match(renderMessageHtml(compactAnswerTable), /<table>/);
assert.match(renderMessageHtml(compactAnswerTable), /<td>30\u2103<\/td>/u);

const inlineFence = '\u793a\u4f8b\uff1a\u5ba1\u8ba1\u65e5\u5fd7\u7ed3\u6784\uff08JSON\uff09 ```json\n{"uid":"u_12876","result":"ALLOW"}\n```\n\u8fd9\u6bb5\u65e5\u5fd7\u8bb0\u5f55\u4e86\u4e00\u6b21\u64cd\u4f5c\u3002';
const normalizedFence = normalizeMessage(inlineFence);
assert.match(normalizedFence, /JSON\uff09\n```json/u);
assert.match(renderMessageHtml(inlineFence), /<pre><code class="language-json">/);
assert.match(renderMessageHtml(inlineFence), /&quot;uid&quot;:&quot;u_12876&quot;/);

const closingFenceWithTrailingText = '```json\n{"uid":"u_12876"}\n```\u8be5\u8bb0\u5f55\u5b8c\u6574\u4f53\u73b0\u4e86\u5ba1\u8ba1\u539f\u5219\u3002';
const trailingHtml = renderMessageHtml(closingFenceWithTrailingText);
assert.match(normalizeMessage(closingFenceWithTrailingText), /```\n\u8be5\u8bb0\u5f55/u);
assert.match(trailingHtml, /<\/code><\/pre>/);
assert.match(trailingHtml, /<p>\u8be5\u8bb0\u5f55/u);

const unsafeLinkHtml = renderMessageHtml("[\u5371\u9669](javascript:alert(1))");
assert.doesNotMatch(unsafeLinkHtml, /href="javascript:/i);

await rm(tempDir, { recursive: true, force: true });
