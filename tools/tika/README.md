# RetriFlow Tika Service

RetriFlow 本身是 Python 项目，Apache Tika 是外部文档解析服务。现在推荐的运行方式不是手动开本地 Java 进程，而是直接放进 Docker Desktop 里作为独立服务启动。

统一命令清单见：

- [docs/local-services.md](D:/code/program/RetriFlow/docs/local-services.md:1)

## 推荐方式：Docker Desktop

项目根目录已经提供：

- `docker-compose.services.yml`

启动命令：

```powershell
docker compose -f .\docker-compose.services.yml up -d
```

这会启动：

- `retriflow-tika`
- `retriflow-ocr`

Tika 默认映射端口：

- `127.0.0.1:9998`

## 本机后端配置

在 `.env` 中启用：

```env
RETRIFLOW_TIKA_ENABLED=true
RETRIFLOW_TIKA_ENDPOINT=http://127.0.0.1:9998
RETRIFLOW_TIKA_REQUEST_TIMEOUT_SECONDS=60
RETRIFLOW_TIKA_OCR_ENABLED=true
RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT=http://127.0.0.1:9889
RETRIFLOW_TIKA_OCR_REQUEST_TIMEOUT_SECONDS=30
```

这样你的本机 FastAPI 后端会：

- 通过 `http://127.0.0.1:9998` 调 Tika
- 通过 `http://127.0.0.1:9889` 调 OCR 服务

## 健康检查

Tika：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9998/tika
```

OCR：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9889/healthz
```

## 旧方式：本地 Java 手动启动

如果你暂时不用 Docker，也还可以继续用本地脚本启动 Tika：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\tika\start_tika.ps1
```

默认 jar：

- `tools/tika/tika-server-standard-3.2.3.jar`

## 当前 RetriFlow 的使用方式

- `PUT /tika/xml`
  - 获取 XHTML，用于结构化提取标题、正文段落、表格、图片说明、页码
- `PUT /rmeta/text`
  - 获取 metadata 与文本内容

## 注意事项

- 当前 Docker 方案只容器化依赖服务，不容器化 `backend` 和 `frontend`
- 你的本机后端和前端仍然照常本地运行
- `docx/pdf/xlsx/pptx` 的主解析依赖 Tika
- 图片说明增强依赖 OCR 服务，但 OCR 当前只作为增强层，不替代 Tika 主流程
