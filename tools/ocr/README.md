# RetriFlow OCR Service

这个目录提供给 RetriFlow 使用的本地 OCR 服务，设计目标是放进 Docker Desktop 中独立启动，然后由本机运行的后端通过 HTTP 调用。

统一命令清单见：

- [docs/local-services.md](D:/code/program/RetriFlow/docs/local-services.md:1)

## 服务信息

- 容器名：`retriflow-ocr`
- 默认端口：`9889`
- 健康检查：`GET /healthz`
- 图片说明提取接口：`POST /ocr/captions`

## 启动方式

在项目根目录执行：

```powershell
docker compose -f .\docker-compose.services.yml up -d
```

这样会同时启动：

- `retriflow-tika`
- `retriflow-ocr`

## 本机后端配置

在 `.env` 中启用：

```env
RETRIFLOW_TIKA_ENABLED=true
RETRIFLOW_TIKA_ENDPOINT=http://127.0.0.1:9998
RETRIFLOW_TIKA_OCR_ENABLED=true
RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT=http://127.0.0.1:9889
RETRIFLOW_TIKA_OCR_REQUEST_TIMEOUT_SECONDS=30
```

## 当前能力

- OCR 服务负责对图片执行 `Tesseract` 识别，并返回 caption 候选
- RetriFlow 后端会优先尝试通过 `Tika /unpack` 提取文档中的嵌入图片
- 当前已经覆盖：
  - `DOCX + Tika /unpack + OCR`
  - `PDF + Tika /unpack + OCR`
- 如果 `DOCX` 的 `Tika /unpack` 没拿到图片，后端会回退到本地 `word/media/*` 解包

## 当前边界

- OCR 目前主要用于图片说明增强，不替代 Tika 的主文档解析
- `PDF` 是否能抽到图片，取决于 Tika `/unpack` 对具体 PDF 的嵌入资源提取结果
- 目前还没有做：
  - PDF 页面整页转图片后逐页 OCR
  - 更强的图片预处理
  - 多模态模型 caption 回退
