export function useAdminFormatters() {
  function formatDate(value: string) {
    if (!value || value === "None") {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function formatDuration(value: number | string | null | undefined) {
    const ms = typeof value === "number" ? value : Number(value || 0);
    if (!Number.isFinite(ms) || ms <= 0) {
      return "0ms";
    }
    if (ms >= 1000) {
      return `${(ms / 1000).toFixed(1)}s`;
    }
    return `${Math.round(ms)}ms`;
  }

  function statusLabel(status: string) {
    if (status === "indexing") {
      return "切块中";
    }
    if (status === "indexed") {
      return "切块成功";
    }
    if (status === "failed") {
      return "切块失败";
    }
    if (status === "pending") {
      return "待切块";
    }
    return status || "未知";
  }

  function statusClass(status: string) {
    return {
      success: status === "indexed",
      danger: status === "failed",
      warning: status === "pending" || status === "indexing"
    };
  }

  function sourceLabel(sourceType: string) {
    return sourceType || "local";
  }

  function processingModeLabel(mode: string) {
    const labels: Record<string, string> = {
      auto: "自动处理",
      chunk_strategy: "按切块策略处理",
      data_channel: "按数据通道处理",
      structure_aware: "结构感知分块",
      fixed: "固定分块",
      fixed_size: "固定大小分块",
      overlap: "重叠分块",
      recursive: "递归分块",
      semantic_embedding: "Embedding 语义分块",
      semantic_llm: "LLM 语义分块",
      hybrid_recursive_semantic: "递归 + 语义",
      hybrid_by_document_type: "按类型策略",
      hybrid_postprocess: "分块后处理"
    };
    return labels[mode] ?? mode ?? "自动处理";
  }

  function documentTypeLabel(type: string) {
    const labels: Record<string, string> = {
      manual: "普通文本",
      knowledge_base: "知识库文档",
      faq: "FAQ",
      contract: "合同",
      log: "日志",
      table: "表格",
      ocr: "OCR 文档",
      mixed_knowledge: "混合知识"
    };
    return labels[type] ?? type ?? "知识库文档";
  }

  function chunkMetadataSummary(metadata: Record<string, unknown>) {
    const parts = [
      metadata.block_type ? `块类型：${String(metadata.block_type)}` : "",
      metadata.page_number ? `页码：${String(metadata.page_number)}` : "",
      metadata.heading_path ? `标题：${Array.isArray(metadata.heading_path) ? metadata.heading_path.join(" / ") : String(metadata.heading_path)}` : ""
    ].filter(Boolean);
    return parts.join(" · ") || "正文分块";
  }

  return {
    chunkMetadataSummary,
    documentTypeLabel,
    formatDate,
    formatDuration,
    processingModeLabel,
    sourceLabel,
    statusClass,
    statusLabel
  };
}
