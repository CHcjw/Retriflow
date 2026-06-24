import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
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
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/(^|\n)([ \t]*)\\(#{1,6})(?=\s*\S)/g, "$1$2$3")
    .replace(/([^\n])\s+(\\?#{1,6})\s*(?=\S)/g, "$1\n\n$2 ")
    .replace(/(^|\n)([ \t]*\\?#{1,6})\s*(?=\S)/g, (_match, lineStart: string, marker: string) => `${lineStart}${marker.replace("\\", "")} `)
    .replace(/(^|\n)([ \t]*\d{1,2}[.)])(?=\S)/g, "$1$2 ")
    .replace(/(^|\n)([ \t]*[-*+])(?![-*+])(?=\S)/g, "$1$2 ")
    .replace(/([^\n])\s+---[ \t]*(?=\n|$)/g, "$1\n\n---")
    .replace(/(^|\n)[ \t]*---[ \t]*(?=\S)/g, "$1---\n\n")
    .replace(/\|\s*\|(?=\s*:?-{3,})/g, "|\n|")
    .replace(/\|\s*(?=\|\s*[^|\n]+?\s*\|)/g, "|\n")
    .replace(/([。！？；，：:]\s*)([-*+]\s+\*\*?)/g, "$1\n\n$2")
    .replace(/([。！？；，：:]\s*)([-*+]\s+)/g, "$1\n\n$2")
    .replace(/([。！？；：:]\s*)(\d+\.\s+)/g, "$1\n\n$2")
    .replace(/(\[[0-9]+\]\s*)([-*+]\s+)/g, "$1\n\n$2")
    .replace(/([^\n])\s+(#{1,6}\s+)/g, "$1\n\n$2")
    .replace(/\n{4,}/g, "\n\n\n")
    .replace(/(^|\n)---(?=#{1,6}\s)/g, "$1---\n")
    .trim();
  return normalizeInlineMarkdownTables(normalized);
}

function isTableSeparatorLine(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line.trim());
}

function normalizeInlineMarkdownTables(value: string): string {
  const lines = value.split("\n");
  const normalizedLines: string[] = [];
  for (const rawLine of lines) {
    normalizedLines.push(...splitInlineTableSegments(rawLine));
  }
  return normalizedLines.join("\n");
}

function splitInlineTableSegments(rawLine: string): string[] {
  const line = rawLine.trim();
  if (!line.includes("|")) {
    return [rawLine];
  }

  const titledHeaderMatch = line.match(/^(.+?[:：])\s*(\|?\s*[^|\n]+\s*\|\s*[^|\n]+.*)$/);
  if (titledHeaderMatch && !titledHeaderMatch[1].includes("|")) {
    return [titledHeaderMatch[1].trim(), ...splitInlineTableSegments(titledHeaderMatch[2].trim())].filter(Boolean);
  }

  const splitByRepeatedRows = splitRepeatedTableRows(line);
  if (splitByRepeatedRows.length > 1) {
    return splitByRepeatedRows;
  }

  const doublePipeIndex = line.indexOf("||");
  if (doublePipeIndex >= 0) {
    const before = line.slice(0, doublePipeIndex).trim();
    const after = line.slice(doublePipeIndex + 1).trim();
    return [before, ...splitInlineTableSegments(after)].filter(Boolean);
  }

  if (!isDenseTableLine(line)) {
    return [rawLine];
  }

  const cells = tableCells(line);
  if (cells.length < 6) {
    return [rawLine];
  }

  const separatorIndex = cells.findIndex((cell) => /^:?-{3,}:?$/.test(cell));
  if (separatorIndex > 0 && cells.length % separatorIndex === 0) {
    const rows: string[] = [];
    for (let index = 0; index < cells.length; index += separatorIndex) {
      rows.push(`| ${cells.slice(index, index + separatorIndex).join(" | ")} |`);
    }
    return rows;
  }

  return [rawLine];
}

function splitRepeatedTableRows(line: string): string[] {
  const rows = line
    .replace(/\s+\|/g, "|")
    .replace(/\|\s+/g, "|")
    .match(/\|[^|\n]+(?:\|[^|\n]+)+\|/g);
  if (!rows || rows.length <= 1) {
    return [];
  }
  const hasSeparator = rows.some((row) => isTableSeparatorLine(row));
  return hasSeparator ? rows.map((row) => normalizeTableRow(row)) : [];
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

function isDenseTableLine(line: string): boolean {
  const pipeCount = (line.match(/\|/g) ?? []).length;
  return pipeCount >= 8 && !isTableSeparatorLine(line);
}

export function renderMessageHtml(value: string): string {
  const normalized = normalizeMessage(value || "正在等待模型返回...");
  return markdown.render(normalized).replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');
}
