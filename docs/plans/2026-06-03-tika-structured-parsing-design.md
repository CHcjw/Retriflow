# RetriFlow Tika Structured Parsing Design

## Context

RetriFlow 当前的知识入库链路只支持 UTF-8 纯文本上传。上传接口直接将字节流解码为字符串，再交给 LangChain 切分与本地检索链路。这满足了演示级文本入库，但还不能支持多格式文档解析、结构化抽取、标准化清洗与字段校验。

用户希望从文档解析层开始升级为：

- 使用 Apache Tika 作为统一解析入口
- 支持多种办公与文档格式
- 在纯文本之外保留结构信息
- 抽取正文段落、标题层级、表格、图片说明、页码
- 表格保留 `row/col/header` 关系，而不是简单拼成一段文本
- 在入库前进行标准化清洗、空值/异常值处理与 Pydantic schema 校验

## Goals

- 为 RetriFlow 新增一个 Python 主导、Tika 驱动的文档解析层
- 在不改变项目主体技术栈的前提下，新增可扩展的结构化抽取模型
- 保持当前知识库 API、入库任务日志、LangChain 切分链路可继续工作
- 为后续向量化、rerank、表格专项增强与更多文件解析器预留扩展位

## Non-Goals

- 这一阶段不引入异步任务队列
- 这一阶段不直接接入真实向量库
- 这一阶段不实现 OCR 专项增强
- 这一阶段不把所有结构化数据永久化到数据库表中

## Recommended Architecture

采用“两层解析架构”：

1. Tika 解析层
   - 由独立的 Tika Server `jar` 提供 HTTP 解析能力
   - RetriFlow 后端通过 `httpx` 调用 `/tika/xml`、`/rmeta` 或 `/tika/json`
   - 解析结果保留 XHTML 与 metadata，避免只拿 plain text

2. Python 结构化处理层
   - 将 Tika 返回的 XHTML/metadata 转换为统一的 Pydantic 数据模型
   - 对段落、标题、表格、图片说明、页码进行结构化抽取
   - 再做标准化清洗与 schema 校验
   - 产出最终可供 LangChain ingestion 使用的标准文本片段与元数据

## Data Flow

1. 用户上传文件到 `POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/upload`
2. `RetriFlowKnowledgeService.upload_document()` 不再直接做 UTF-8 解码
3. 新增 `RetriFlowDocumentParserService`
   - 根据文件名与 MIME 类型构造解析请求
   - 调用 Tika Server
   - 返回原始解析结果：`metadata + xhtml + plain_text`
4. 新增 `RetriFlowStructuredExtractionService`
   - 解析 XHTML
   - 抽取标题、段落、表格、图片说明、页码
   - 输出统一 `StructuredDocument`
5. 新增 `RetriFlowDocumentNormalizationService`
   - 统一编码与空白
   - 标准化单位格式
   - 处理空值与显著异常值
   - 关键字段做 Pydantic 校验
6. 归一化后的正文与结构块进入 `RetriFlowIngestionPipeline`
7. 继续沿用当前 LangChain `Document` + splitter 产出 chunks
8. 知识文档、chunk、ingestion task 正常落库

## Main Components

### 1. Tika Client

新增 `backend/src/domain/tika_client.py`

- 负责 HTTP 调用 Tika Server
- 支持健康检查、超时、错误包装
- 对外返回统一 `RawParsedDocument`

### 2. Structured Extraction

新增 `backend/src/domain/document_structure.py`

- 负责从 XHTML 中抽取结构块
- 结构块至少包含：
  - `heading`
  - `paragraph`
  - `table`
  - `image_caption`
  - `page_break`

### 3. Normalization

新增 `backend/src/domain/document_normalizer.py`

- 对结构块做清洗与归一化
- 输出标准化的 `StructuredDocument`

### 4. Pydantic Schemas

新增 `backend/src/schemas/document_structure.py`

- `RawParsedDocument`
- `StructuredDocument`
- `StructuredBlock`
- `HeadingBlock`
- `ParagraphBlock`
- `TableBlock`
- `TableRow`
- `TableCell`
- `ImageCaptionBlock`

### 5. Knowledge Upload Integration

修改 `backend/src/domain/knowledge.py`

- 上传时先调用 Tika 解析链路
- 将结构化结果展开为可入库文本
- 同时在 ingestion task 节点日志中补充 `parse` 与 `extract` 节点

## Structural Extraction Strategy

### Headings

- 优先从 XHTML 中的 `h1-h6`、显式样式或 Tika 保留的结构标签提取
- 输出：
  - `level`
  - `text`
  - `page_number`
  - `block_index`

### Paragraphs

- 从 `p`、正文容器、非表格文本块提取
- 保留：
  - `text`
  - `page_number`
  - `heading_path`

### Tables

- 从 XHTML 中的 `table/thead/tbody/tr/th/td` 提取
- 输出：
  - `headers`
  - `rows`
  - `row_count`
  - `column_count`
  - `page_number`
- 每个单元格保留：
  - `row_index`
  - `column_index`
  - `is_header`
  - `text`

### Image Captions

- 先支持“邻近文本推断”策略
- 若图片附近出现 `图`、`Figure`、`图片说明` 等说明性文本，则抽为 `image_caption`

### Page Number

- 优先利用 XHTML 中的页容器或 `div.page`
- 若缺少显式页结构，则页码字段允许为空

## Normalization Strategy

- 统一为 UTF-8 语义字符串
- 统一换行和空白
- 表格单元格去掉多余空白但保留空单元格位置
- 常见单位标准化：
  - `％ -> %`
  - 中英文全角半角统一
  - `MB / Mb / M` 等可配置映射
- 空值标准化：
  - `N/A`
  - `null`
  - `--`
  - 空串
- 异常值策略：
  - 过长纯符号串直接丢弃
  - 非法页码置空
  - 空标题不保留为 heading block

## Validation Strategy

- 用 Pydantic 在结构化对象层完成强校验
- 校验重点：
  - `heading.level` 范围
  - `table.row_count / column_count` 与实际数据一致
  - `row_index / column_index` 连续有效
  - 关键文本字段不为 `None`

## Testing Strategy

测试优先级：

1. Tika client 单元测试
   - 模拟 HTTP 返回 XHTML 和 metadata
2. 结构化抽取测试
   - 从最小 XHTML 样本中提取 heading / paragraph / table
3. 标准化与校验测试
   - 单位格式、空值、异常值处理
4. API 集成测试
   - 上传文档后成功生成 document、chunks、ingestion task

## Risks

- Tika XHTML 对不同格式的结构保真度不同
- 图片说明与页码抽取可能存在文件类型差异
- 表格结构复杂时可能需要后续引入格式专项增强

## Recommended First Slice

先做一个低风险可落地版本：

- Tika Server 配置与 Python client
- 纯 Python 结构化模型
- 支持 `text/plain`、`markdown`、`html`、`docx` 的统一解析入口
- 抽取 heading / paragraph / table
- 做基础 normalize + Pydantic 校验
- 与当前 upload ingestion 打通

这样能最快把“多格式 + 结构化 + 可验证”链路建起来，再继续补图片说明、页码和更复杂表格增强。
