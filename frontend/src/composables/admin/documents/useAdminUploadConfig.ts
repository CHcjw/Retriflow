export function parseUploadRecursiveSeparators(value: string): string[] {
  return value
    .split(/\r?\n/u)
    .map((rawLine) => {
      if (rawLine === " " || rawLine === "[space]") {
        return " ";
      }
      const trimmed = rawLine.trim();
      if (!trimmed) {
        return null;
      }
      if (trimmed === "\\n\\n") {
        return "\n\n";
      }
      if (trimmed === "\\n") {
        return "\n";
      }
      if (trimmed === "\\t" || trimmed === "[tab]") {
        return "\t";
      }
      return rawLine;
    })
    .filter((separator): separator is string => separator !== null);
}

export function serializeUploadRecursiveSeparators(value: unknown): string | null {
  if (!Array.isArray(value)) {
    return null;
  }
  return value
    .map((separator) => String(separator))
    .map((separator) => (separator === " " ? "[space]" : separator.replace(/\n/gu, "\\n").replace(/\t/gu, "\\t")))
    .join("\n");
}

export function buildUploadChunkConfig(options: {
  chunkOverlap: number;
  chunkSize: number;
  chunkStrategy: string;
  recursiveSeparatorsText: string;
  structureMaxChars: number;
  structureMinChars: number;
}) {
  if (options.chunkStrategy === "fixed_size") {
    return {
      chunkSize: options.chunkSize,
      overlapSize: options.chunkOverlap
    };
  }
  if (options.chunkStrategy === "structure_aware") {
    return {
      targetChars: options.chunkSize,
      overlapChars: options.chunkOverlap,
      maxChars: options.structureMaxChars,
      minChars: options.structureMinChars
    };
  }
  if (["recursive", "hybrid_recursive_semantic"].includes(options.chunkStrategy)) {
    return {
      chunk_size: options.chunkSize,
      chunk_overlap: options.chunkOverlap,
      recursive_separators: parseUploadRecursiveSeparators(options.recursiveSeparatorsText)
    };
  }
  return {
    chunk_size: options.chunkSize,
    chunk_overlap: options.chunkOverlap
  };
}
