<script setup lang="ts">
import { computed } from "vue";

import { useRetriFlowAdmin } from "../composables/useRetriFlowAdmin";

const {
  loading,
  documentLoading,
  chunkLoading,
  taskNodeLoading,
  uploadLoading,
  reindexLoading,
  error,
  infoMessage,
  meta,
  knowledgeBases,
  selectedKnowledgeBase,
  selectedKnowledgeBaseId,
  documents,
  selectedDocument,
  selectedDocumentId,
  chunks,
  ingestionTaskNodes,
  relatedTask,
  isAdmin,
  canManageKnowledge,
  canViewIngestion,
  readonlyNotice,
  documentTitle,
  documentContent,
  documentType,
  chunkStrategy,
  chunkSize,
  chunkOverlap,
  recursiveSeparatorsText,
  uploadFileName,
  uploadDocumentType,
  uploadChunkStrategy,
  uploadChunkSize,
  uploadChunkOverlap,
  uploadRecursiveSeparatorsText,
  documentTypeOptions,
  chunkStrategyOptions,
  manualChunkSummary,
  uploadChunkSummary,
  manualShowChunkSizeControls,
  uploadShowChunkSizeControls,
  manualShowRecursiveSeparatorControls,
  uploadShowRecursiveSeparatorControls,
  manualShowSemanticNotice,
  uploadShowSemanticNotice,
  manualAutoStrategyRecommendation,
  uploadAutoStrategyRecommendation,
  manualRecursiveSeparatorSummary,
  uploadRecursiveSeparatorSummary,
  canCreateDocument,
  canReindexDocument,
  addKnowledgeBase,
  removeKnowledgeBase,
  selectKnowledgeBase,
  selectDocument,
  addDocument,
  uploadDocument,
  reindexDocument
} = useRetriFlowAdmin();

const uploadAccept =
  ".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.html,.htm,text/plain,text/markdown,application/pdf";

const chunkPreviewMap = computed(() => {
  return new Map(
    chunks.value.slice(0, 3).map((chunk) => {
      const metadata = chunk.metadata ?? {};
      const summary = [
        metadata.block_type ? `块类型: ${String(metadata.block_type)}` : null,
        metadata.page_number ? `页码: ${String(metadata.page_number)}` : null,
        chunk.strategy ? `策略: ${chunk.strategy}` : null
      ]
        .filter(Boolean)
        .join(" / ");

      return [chunk.id, summary];
    })
  );
});

const onFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  await uploadDocument(file);
  input.value = "";
};
</script>

<template>
  <section class="page-panel">
    <div class="panel-header">
      <p class="eyebrow">Admin Console</p>
      <h2>RetriFlow 知识库工作台</h2>
    </div>

    <div class="toolbar-row">
      <p v-if="meta" class="hero-copy">
        当前后台已接入 {{ meta.name }} 的知识库、文档、分块结构，以及管理员可见的 ingestion 任务与节点日志。
      </p>
      <button v-if="canManageKnowledge" type="button" class="secondary-button" @click="addKnowledgeBase">
        新增知识库
      </button>
    </div>

    <div v-if="meta" class="feature-grid">
      <article class="feature-card">
        <h3>配置后端</h3>
        <p>{{ meta.database_backend }}</p>
      </article>
      <article class="feature-card">
        <h3>实际后端</h3>
        <p>{{ meta.runtime_database_backend }}</p>
      </article>
      <article class="feature-card">
        <h3>Schema</h3>
        <p>{{ meta.database_schema }}</p>
      </article>
      <article class="feature-card">
        <h3>知识库数量</h3>
        <p>{{ knowledgeBases.length }}</p>
      </article>
    </div>

    <div v-if="readonlyNotice" class="info-card">
      <strong>{{ isAdmin ? "管理员模式" : "只读模式" }}</strong>
      <p>{{ readonlyNotice }}</p>
    </div>

    <p v-if="infoMessage" class="status-copy">{{ infoMessage }}</p>
    <p v-if="loading" class="status-copy">正在加载后台数据...</p>
    <p v-else-if="error" class="status-copy error-copy">{{ error }}</p>

    <div class="admin-grid">
      <article
        v-for="knowledgeBase in knowledgeBases"
        :key="knowledgeBase.id"
        class="admin-card"
        :class="{ active: knowledgeBase.id === selectedKnowledgeBaseId }"
      >
        <div class="pane-title-row">
          <span class="card-title">{{ knowledgeBase.name }}</span>
          <button
            v-if="canManageKnowledge"
            type="button"
            class="secondary-button compact-button danger-button"
            @click.stop="removeKnowledgeBase(knowledgeBase.id)"
          >
            删除
          </button>
        </div>
        <button
          type="button"
          class="admin-card-button"
          :class="{ active: knowledgeBase.id === selectedKnowledgeBaseId }"
          @click="selectKnowledgeBase(knowledgeBase.id)"
        >
          <span>产品：{{ knowledgeBase.product }}</span>
          <span>文档数：{{ knowledgeBase.document_count }}</span>
        </button>
      </article>
    </div>

    <section v-if="selectedKnowledgeBase" class="document-panel">
      <div class="pane-title-row">
        <div>
          <p class="eyebrow">Documents</p>
          <h3>{{ selectedKnowledgeBase.name }} 的文档</h3>
        </div>
        <p class="status-copy">当前 {{ documents.length }} 篇</p>
      </div>

      <form v-if="canManageKnowledge" class="document-form" @submit.prevent="addDocument">
        <input v-model="documentTitle" type="text" placeholder="文档标题" aria-label="文档标题" />

        <div class="form-grid">
          <label class="field-stack">
            <span>文档类型</span>
            <select v-model="documentType">
              <option v-for="option in documentTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="field-stack">
            <span>分块策略</span>
            <select v-model="chunkStrategy">
              <option v-for="option in chunkStrategyOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </div>

        <div v-if="manualAutoStrategyRecommendation" class="info-card">
          <strong>自动策略推荐</strong>
          <p>{{ manualAutoStrategyRecommendation }}</p>
        </div>

        <div v-if="manualShowChunkSizeControls" class="form-grid">
          <label class="field-stack">
            <span>Chunk Size</span>
            <input
              v-model.number="chunkSize"
              type="number"
              min="200"
              max="1000"
              step="10"
              aria-label="chunk size"
            />
          </label>

          <label class="field-stack">
            <span>Overlap</span>
            <input
              v-model.number="chunkOverlap"
              type="number"
              min="0"
              :max="Math.max(chunkSize - 1, 0)"
              step="5"
              aria-label="chunk overlap"
            />
          </label>
        </div>

        <p v-if="manualShowChunkSizeControls" class="field-hint">
          {{ manualChunkSummary }} 默认值为 `600 / 120`，适合大多数 `200 - 1000` 字符范围的分块。
        </p>

        <div v-if="manualShowRecursiveSeparatorControls" class="field-stack">
          <span>递归分隔符列表</span>
          <textarea
            v-model="recursiveSeparatorsText"
            class="compact-textarea"
            aria-label="递归分隔符列表"
            placeholder="每行一个分隔符，例如：\n\n\n\n\n[space]"
          ></textarea>
          <p class="field-hint">
            当前使用：{{ manualRecursiveSeparatorSummary }}。支持输入 `\n\n`、`\n`、`[space]`、`[tab]` 或任意自定义分隔符。
          </p>
        </div>

        <div v-if="manualShowSemanticNotice" class="info-card">
          <strong>语义分块说明</strong>
          <p>当前已启用 Embedding 语义分块，LLM 语义分块暂未开放，后续会接入模型级语义切分。</p>
        </div>

        <textarea
          v-model="documentContent"
          placeholder="粘贴文档内容，保存后会自动经过 normalize、segment、chunk、index 四个阶段"
          aria-label="文档内容"
        ></textarea>

        <div class="inline-actions">
          <button type="submit" :disabled="!canCreateDocument">加入知识库</button>
          <button
            type="button"
            class="secondary-button"
            :disabled="!canReindexDocument"
            @click="reindexDocument"
          >
            {{ reindexLoading ? "重建中..." : "对当前文档重建索引" }}
          </button>
        </div>
      </form>

      <div v-if="canManageKnowledge" class="upload-panel">
        <div class="pane-title-row">
          <div>
            <p class="eyebrow">Upload</p>
            <h4>上传文档入库</h4>
          </div>
        </div>

        <div class="form-grid">
          <label class="field-stack">
            <span>上传文档类型</span>
            <select v-model="uploadDocumentType">
              <option v-for="option in documentTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="field-stack">
            <span>上传分块策略</span>
            <select v-model="uploadChunkStrategy">
              <option v-for="option in chunkStrategyOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </div>

        <div v-if="uploadAutoStrategyRecommendation" class="info-card">
          <strong>自动策略推荐</strong>
          <p>{{ uploadAutoStrategyRecommendation }}</p>
        </div>

        <div v-if="uploadShowChunkSizeControls" class="form-grid">
          <label class="field-stack">
            <span>上传 Chunk Size</span>
            <input
              v-model.number="uploadChunkSize"
              type="number"
              min="200"
              max="1000"
              step="10"
              aria-label="upload chunk size"
            />
          </label>

          <label class="field-stack">
            <span>上传 Overlap</span>
            <input
              v-model.number="uploadChunkOverlap"
              type="number"
              min="0"
              :max="Math.max(uploadChunkSize - 1, 0)"
              step="5"
              aria-label="upload chunk overlap"
            />
          </label>
        </div>

        <p v-if="uploadShowChunkSizeControls" class="field-hint">
          {{ uploadChunkSummary }} 上传文档将沿用你当前选择的文档类型和分块策略。
        </p>

        <div v-if="uploadShowRecursiveSeparatorControls" class="field-stack">
          <span>上传递归分隔符列表</span>
          <textarea
            v-model="uploadRecursiveSeparatorsText"
            class="compact-textarea"
            aria-label="上传递归分隔符列表"
            placeholder="每行一个分隔符，例如：\n\n\n\n\n[space]"
          ></textarea>
          <p class="field-hint">
            当前使用：{{ uploadRecursiveSeparatorSummary }}。这组配置会连同上传任务一起发送给后端。
          </p>
        </div>

        <div v-if="uploadShowSemanticNotice" class="info-card">
          <strong>语义分块说明</strong>
          <p>上传场景同样只启用 Embedding 语义分块，适合合同、规范和长段落语义聚合。</p>
        </div>

        <div class="upload-row">
          <label class="upload-button">
            <input :accept="uploadAccept" type="file" @change="onFileChange" />
            <span>{{ uploadLoading ? "上传中..." : "上传文档文件" }}</span>
          </label>
          <span class="status-copy">
            {{
              uploadFileName
                ? `最近上传：${uploadFileName}`
                : "支持 txt、md、pdf、doc、docx、xls、xlsx、html 等常见文档格式"
            }}
          </span>
        </div>
      </div>

      <p v-if="documentLoading" class="status-copy">正在加载文档...</p>
      <div v-else class="document-list">
        <button
          v-for="document in documents"
          :key="document.id"
          type="button"
          class="message-card admin-card-button"
          :class="{ active: document.id === selectedDocumentId }"
          @click="selectDocument(document.id)"
        >
          <div class="pane-title-row">
            <h4>{{ document.title }}</h4>
            <span class="status-badge">{{ document.status }}</span>
          </div>
          <p>来源：{{ document.source_type }}</p>
          <p>向量索引：{{ document.vector_index_status }} / {{ document.vector_chunk_count }} chunks</p>
          <p>索引时间：{{ document.vector_indexed_at || "未建立" }}</p>
          <p>创建时间：{{ document.created_at }}</p>
        </button>
      </div>

      <section v-if="selectedDocument" class="document-panel">
        <div class="pane-title-row">
          <div>
            <p class="eyebrow">Chunks</p>
            <h3>{{ selectedDocument.title }} 的分块结果</h3>
          </div>
          <span v-if="relatedTask && canViewIngestion" class="status-copy">
            task #{{ relatedTask.id }} / {{ relatedTask.status }} / {{ relatedTask.chunk_count }} chunks
          </span>
        </div>

        <p v-if="chunkLoading" class="status-copy">正在加载 chunks...</p>
        <div v-else class="document-list">
          <article v-for="chunk in chunks" :key="chunk.id" class="message-card">
            <div class="pane-title-row">
              <strong>Chunk {{ chunk.chunk_index }}</strong>
              <div class="inline-actions">
                <span class="status-badge">{{ chunk.strategy }}</span>
                <span class="status-badge">{{ chunk.char_count }} chars</span>
              </div>
            </div>
            <p class="chunk-meta">
              文档类型：{{ chunk.document_type }}
              <span v-if="chunkPreviewMap.get(chunk.id)"> / {{ chunkPreviewMap.get(chunk.id) }} </span>
            </p>
            <p>{{ chunk.content }}</p>
          </article>
        </div>

        <section class="document-panel">
          <div class="pane-title-row">
            <div>
              <p class="eyebrow">Pipeline</p>
              <h3>Ingestion 节点日志</h3>
            </div>
          </div>

          <div v-if="!canViewIngestion" class="info-card">
            <strong>管理员可见</strong>
            <p>ingestion 任务和节点日志仅对 admin 开放，普通用户可查看文档与分块结果。</p>
          </div>

          <template v-else>
            <p v-if="taskNodeLoading" class="status-copy">正在加载节点日志...</p>
            <div v-else class="document-list">
              <article v-for="node in ingestionTaskNodes" :key="node.id" class="message-card">
                <div class="pane-title-row">
                  <strong>{{ node.node_order }}. {{ node.node_type }}</strong>
                  <span class="status-badge">{{ node.success ? "success" : "failed" }}</span>
                </div>
                <p>{{ node.message }}</p>
                <p>{{ node.duration_ms }} ms</p>
              </article>
            </div>
          </template>
        </section>
      </section>
    </section>
  </section>
</template>
