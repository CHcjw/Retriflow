import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false
});

const defaultLinkOpen =
  markdown.renderer.rules.link_open ||
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options));

markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index];
  const hrefIndex = token.attrIndex("href");
  if (hrefIndex >= 0) {
    const href = token.attrs?.[hrefIndex]?.[1] ?? "";
    if (!isSafeUrl(href)) {
      token.attrSet("href", "#");
    }
  }
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noopener noreferrer");
  return defaultLinkOpen(tokens, index, options, env, self);
};

function isSafeUrl(value: string): boolean {
  return /^(https?:\/\/|\/)/i.test(value.trim());
}

export function normalizeMessage(value: string): string {
  const normalized = value
    .replace(/\r\n/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .trim();

  return normalizeInlineMarkdownTables(normalizeMarkdownOutsideFences(normalizeFenceBoundaries(normalized)));
}

function normalizeFenceBoundaries(value: string): string {
  const withOpeningFenceOnOwnLine = value.replace(/([^\n])\s*(```[A-Za-z0-9_-]*)/g, "$1\n$2");
  const output: string[] = [];
  let inFence = false;

  for (const rawLine of withOpeningFenceOnOwnLine.split("\n")) {
    const line = rawLine.trimStart();
    if (!line.startsWith("```")) {
      output.push(rawLine);
      continue;
    }

    if (!inFence) {
      output.push(rawLine);
      inFence = true;
      continue;
    }

    const indentLength = rawLine.length - line.length;
    const indent = rawLine.slice(0, indentLength);
    const trailing = line.slice(3);
    output.push(`${indent}\`\`\``);
    inFence = false;
    if (trailing.trim()) {
      output.push(trailing.trimStart());
    }
  }

  return output.join("\n");
}

function normalizeMarkdownOutsideFences(value: string): string {
  const lines = value.split("\n");
  const output: string[] = [];
  let inFence = false;

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();
    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      output.push(rawLine);
      continue;
    }
    output.push(inFence ? rawLine : normalizeMarkdownLine(rawLine));
  }

  return output.join("\n").replace(/\n{4,}/g, "\n\n\n").trim();
}

function normalizeMarkdownLine(line: string): string {
  return line
    .replace(/(^|\n)([ \t]*)\\(#{1,6})(?=\s*\S)/g, "$1$2$3")
    .replace(/([^\n])\s+(\\?#{1,6})\s+(?=\S)/g, "$1\n\n$2 ")
    .replace(/(^|\n)([ \t]*\\?#{1,6})\s*(?=\S)/g, (_match, lineStart: string, marker: string) => {
      return `${lineStart}${marker.replace("\\", "")} `;
    })
    .replace(/([\u3002\uff01\uff1f\uff1b:：]\s*)([-*+]\s+)/g, "$1\n\n$2")
    .replace(/([\u3002\uff01\uff1f\uff1b:：]\s*)(\d{1,2}[.)]\s+)/g, "$1\n\n$2")
    .replace(/([^\n])\s+([-*+]\s+)(?=\S)/g, "$1\n$2")
    .replace(/([^\n])\s+(\d{1,2}[.)]\s+)(?=\S)/g, "$1\n$2")
    .replace(/(^|\n)([ \t]*[-*+])(?![-*+])(?=\S)/g, "$1$2 ")
    .replace(/(^|\n)([ \t]*\d{1,2}[.)])(?=\S)/g, "$1$2 ")
    .replace(/([^\n])\s+---[ \t]*(?=\n|$)/g, "$1\n\n---")
    .replace(/(^|\n)[ \t]*---[ \t]*(?=\S)/g, "$1---\n\n");
}

function normalizeInlineMarkdownTables(value: string): string {
  const lines = value.split("\n");
  const output: string[] = [];
  let inFence = false;

  for (const rawLine of lines) {
    if (rawLine.trim().startsWith("```")) {
      inFence = !inFence;
      output.push(rawLine);
      continue;
    }
    output.push(...(inFence ? [rawLine] : splitInlineTableSegments(rawLine)));
  }

  return output.join("\n");
}

function splitInlineTableSegments(rawLine: string): string[] {
  const line = rawLine.trim();
  if (!line.includes("|")) {
    return [rawLine];
  }

  const titledTable = line.match(/^(.+?[\uff1a:])\s*(\|?\s*[^|\n]+\s*\|\s*[^|\n]+.*)$/);
  if (titledTable && !titledTable[1].includes("|")) {
    return [titledTable[1].trim(), ...splitInlineTableSegments(titledTable[2].trim())].filter(Boolean);
  }

  const repeatedRows = splitRepeatedTableRows(line);
  if (repeatedRows.length > 1) {
    return repeatedRows;
  }

  const cells = tableCells(line);
  const separatorIndex = cells.findIndex((cell) => /^:?-{3,}:?$/.test(cell));
  if (separatorIndex > 0) {
    const columnCount = separatorIndex;
    const rows: string[] = [];
    for (let index = 0; index < cells.length; index += columnCount) {
      const rowCells = cells.slice(index, index + columnCount);
      if (rowCells.length === columnCount) {
        rows.push(`| ${rowCells.join(" | ")} |`);
      }
    }
    if (rows.length >= 2 && isTableSeparatorLine(rows[1])) {
      return rows;
    }
  }

  return [rawLine];
}

function splitRepeatedTableRows(line: string): string[] {
  const rows = line.match(/\|[^|\n]+(?:\|[^|\n]+)+\|/g);
  if (!rows || rows.length <= 1 || !rows.some((row) => isTableSeparatorLine(row))) {
    return [];
  }
  return rows.map((row) => normalizeTableRow(row));
}

function normalizeTableRow(row: string): string {
  return `| ${tableCells(row).join(" | ")} |`;
}

function tableCells(line: string): string[] {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim())
    .filter(Boolean);
}

function isTableSeparatorLine(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line.trim());
}

function renderCitations(html: string): string {
  return html.replace(/\[(\d+)\](?!\()/g, '<span class="citation">[$1]</span>');
}

export function renderMessageHtml(value: string): string {
  const normalized = normalizeMessage(value || "\u6b63\u5728\u7b49\u5f85\u6a21\u578b\u8fd4\u56de...");
  return renderCitations(markdown.render(normalized));
}
