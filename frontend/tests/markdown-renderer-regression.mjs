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

const boldText = "\u4fdd\u9669\u7cfb\u7edf\u6570\u636e\u5b89\u5168\u4e0d\u662f\u5355\u4e00\u6280\u672f\u5806\u780c\uff0c\u800c\u662f\u901a\u8fc7**\u201c\u6807\u7b7e\u5316\u6570\u636e\u3001\u7b56\u7565\u5316\u6267\u884c\u3001\u8bc1\u636e\u5316\u5ba1\u8ba1\u3001\u6307\u6807\u5316\u8fd0\u8425\u3001\u5de5\u7a0b\u5316\u6062\u590d\u201d**\u7684\u65b9\u6cd5\u8bba [5]\uff0c\u5b9e\u73b0\uff1a";
const boldHtml = renderMessageHtml(boldText);
assert.match(boldHtml, /\u201c<strong>\u6807\u7b7e\u5316\u6570\u636e/u);
assert.doesNotMatch(boldHtml, /\*\*/);

const sectionDash = "\u4e5d\u3001\u5408\u89c4\u5bf9\u9f50\u4e0e\u6a21\u578b\u5b89\u5168- \u5bf9\u9f50\u300a\u7f51\u7edc\u5b89\u5168\u6cd5\u300b\u300a\u6570\u636e\u5b89\u5168\u6cd5\u300b\u300a\u4e2a\u4eba\u4fe1\u606f\u4fdd\u62a4\u6cd5\u300b\uff08PIPL\uff09\u3001\u7b49\u4fdd2.0\uff1b";
const sectionHtml = renderMessageHtml(sectionDash);
assert.match(sectionHtml, /<h3>\u4e5d\u3001\u5408\u89c4\u5bf9\u9f50\u4e0e\u6a21\u578b\u5b89\u5168<\/h3>/u);
assert.match(sectionHtml, /<li>\u5bf9\u9f50\u300a\u7f51\u7edc\u5b89\u5168\u6cd5/u);

const offerDash = "Offer\u53d1\u653e\u4e0e\u5165\u804c\u6279\u6b21\u5b89\u6392- \u5bf9\u901a\u8fc7\u8bc4\u4f30\u7684\u5b66\u751f\u53d1\u653e\u6821\u62dbOffer\uff1b\n\u5165\u804c\u901a\u5e38\u5206\u6279\u6b21\u8fdb\u884c\uff0c\u4f8b\u5982\uff1a\n7\u6708\u7edf\u4e00\u5165\u804c\u4e00\u6279\uff1b\n9\u6708\u518d\u5b89\u6392\u4e00\u6279 [1]\u3002";
const offerHtml = renderMessageHtml(offerDash);
assert.match(offerHtml, /<p>Offer\u53d1\u653e\u4e0e\u5165\u804c\u6279\u6b21\u5b89\u6392<\/p>/u);
assert.match(offerHtml, /<li>\u5bf9\u901a\u8fc7\u8bc4\u4f30\u7684\u5b66\u751f/u);

const boldOrderedList = "**\u65b9\u5f0f C\uff1a \u624b\u52a8\u6dfb\u52a0 IP\u6253\u5370\uff08\u5907\u7528\uff09 **1. \u6253\u5f00\uff1a\u8bbe\u7f6e \u2192 \u6253\u5370\u673a\u548c\u626b\u63cf\u4eea";
const normalizedBoldOrderedList = normalizeMessage(boldOrderedList);
assert.match(normalizedBoldOrderedList, /\*\*\u65b9\u5f0f C\uff1a \u624b\u52a8\u6dfb\u52a0 IP\u6253\u5370\uff08\u5907\u7528\uff09\*\*\n+1\. /u);
const boldOrderedListHtml = renderMessageHtml(boldOrderedList);
assert.match(boldOrderedListHtml, /<strong>\u65b9\u5f0f C\uff1a \u624b\u52a8\u6dfb\u52a0 IP\u6253\u5370/u);
assert.match(boldOrderedListHtml, /<ol>/);

const danglingHeadingMarker = "- \u5c06\u5458\u5de5\u4e2a\u4eba\u6210\u957f\u4e0e\u516c\u53f8\u957f\u671f\u4ef7\u503c\u7ed1\u5b9a [1]\u3002 ###";
const danglingHeadingHtml = renderMessageHtml(danglingHeadingMarker);
assert.doesNotMatch(normalizeMessage(danglingHeadingMarker), /###$/);
assert.doesNotMatch(danglingHeadingHtml, /###/);

const titledSalesTable = "### \u4e09\u3001\u6240\u552e\u4f01\u4e1a\u9500\u552e\u989d Top10| \u4f01\u4e1a\u540d\u79f0 | \u9500\u552e\u989d\uff08\u4e07\u5143\uff09 | \u5360\u6bd4 |\n|---------------|---------------|------|\n|\u91d1\u8776\u8f6f\u4ef611| \u00a5324.43 \u4e07 | 5.5% |";
const titledSalesHtml = renderMessageHtml(titledSalesTable);
assert.match(titledSalesHtml, /<h3>/);
assert.match(titledSalesHtml, /<table>/);
assert.match(titledSalesHtml, /<td>\u91d1\u8776\u8f6f\u4ef611<\/td>/u);
assert.doesNotMatch(titledSalesHtml, /\|---------------\|/);

const compactWeather = "-6\u670830\u65e5\uff08\u5468\u4e00\uff09 - \u767d\u5929\uff1a\u96f7\u9635\u96e8 | \u591c\u95f4\uff1a\u591a\u4e91\n\u6c14\u6e29\uff1a26\u2103 ~ 34\u2103- \u98ce\u5411\uff1a\u5317\u98ce1-3\u7ea7";
const normalizedWeather = normalizeMessage(compactWeather);
assert.doesNotMatch(normalizedWeather, /^-/);
assert.match(normalizedWeather, /\n\u98ce\u5411\uff1a/u);

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
