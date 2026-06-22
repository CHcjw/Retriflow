import json
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse

from api.deps.auth import AdminUser, CurrentUser
from modules.knowledge import RetriFlowKnowledgeService
from schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
    KnowledgeChunkListResponse,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentItem,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentPreviewResponse,
    KnowledgeDocumentReindexRequest,
    KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentStructuredBlockListResponse,
    KnowledgeSampleImportResponse,
    KnowledgeBaseRouteProfileItem,
    KnowledgeBaseRouteProfileUpdateRequest,
    KnowledgeChunkBatchUpdateRequest,
    KnowledgeChunkBatchUpdateResponse,
    KnowledgeChunkItem,
    KnowledgeChunkUpdateRequest,
)


router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge"])


def _service() -> RetriFlowKnowledgeService:
    return RetriFlowKnowledgeService()


def _parse_recursive_separators_text(value: str | None) -> list[str] | None:
    if value is None:
        return None

    separators = [line for line in value.splitlines() if line != ""]
    return separators or None


def _parse_chunk_config_json(value: str | None) -> dict | None:
    if value is None or not value.strip():
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None


@router.get("", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(user: CurrentUser) -> KnowledgeBaseListResponse:
    return _service().list_knowledge_bases()


@router.post("", response_model=KnowledgeBaseItem, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(request: KnowledgeBaseCreateRequest, user: AdminUser) -> KnowledgeBaseItem:
    return _service().create_knowledge_base(request)


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseItem)
def update_knowledge_base(
    knowledge_base_id: str,
    request: KnowledgeBaseUpdateRequest,
    user: AdminUser,
) -> KnowledgeBaseItem:
    return _service().update_knowledge_base(knowledge_base_id, request)


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(knowledge_base_id: str, user: AdminUser) -> None:
    _service().delete_knowledge_base(knowledge_base_id)


@router.get("/{knowledge_base_id}/documents", response_model=KnowledgeDocumentListResponse)
def list_documents(knowledge_base_id: str, user: CurrentUser) -> KnowledgeDocumentListResponse:
    return _service().list_documents(knowledge_base_id)


@router.post(
    "/{knowledge_base_id}/documents",
    response_model=KnowledgeDocumentItem,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    knowledge_base_id: str,
    request: KnowledgeDocumentCreateRequest,
    user: AdminUser,
) -> KnowledgeDocumentItem:
    return _service().create_document(knowledge_base_id, request)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/preview",
    response_model=KnowledgeDocumentPreviewResponse,
)
def preview_document(
    knowledge_base_id: str,
    document_id: int,
    user: CurrentUser,
) -> KnowledgeDocumentPreviewResponse:
    return _service().preview_document(knowledge_base_id, document_id)


@router.get("/{knowledge_base_id}/documents/{document_id}/file")
def download_document_source(
    knowledge_base_id: str,
    document_id: int,
    user: CurrentUser,
) -> StreamingResponse:
    stream, filename, content_type = _service().open_document_source(knowledge_base_id, document_id)
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
    }
    return StreamingResponse(stream, media_type=content_type, headers=headers)


@router.post(
    "/{knowledge_base_id}/documents/{document_id}/reindex",
    response_model=KnowledgeDocumentItem,
)
def reindex_document(
    knowledge_base_id: str,
    document_id: int,
    request: KnowledgeDocumentReindexRequest,
    user: AdminUser,
) -> KnowledgeDocumentItem:
    return _service().reindex_document(knowledge_base_id, document_id, request)


@router.patch(
    "/{knowledge_base_id}/documents/{document_id}",
    response_model=KnowledgeDocumentItem,
)
def update_document(
    knowledge_base_id: str,
    document_id: int,
    request: KnowledgeDocumentUpdateRequest,
    user: AdminUser,
) -> KnowledgeDocumentItem:
    return _service().update_document(knowledge_base_id, document_id, request)


@router.delete(
    "/{knowledge_base_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    knowledge_base_id: str,
    document_id: int,
    user: AdminUser,
) -> None:
    _service().delete_document(knowledge_base_id, document_id)


@router.post(
    "/{knowledge_base_id}/documents/upload",
    response_model=KnowledgeDocumentItem,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: str,
    user: AdminUser,
    file: UploadFile = File(...),
    document_type: Annotated[str, Form()] = "knowledge_base",
    process_mode: Annotated[str, Form()] = "chunk_strategy",
    pipeline_id: Annotated[int | None, Form()] = None,
    chunk_strategy: Annotated[str, Form()] = "auto",
    chunk_size: Annotated[int, Form()] = 600,
    chunk_overlap: Annotated[int, Form()] = 120,
    recursive_separators_text: Annotated[str | None, Form()] = None,
    chunk_config_json: Annotated[str | None, Form()] = None,
) -> KnowledgeDocumentItem:
    content = await file.read()
    return _service().upload_document(
        knowledge_base_id,
        file.filename or "uploaded-document.txt",
        content,
        file.content_type,
        document_type,
        chunk_strategy,
        chunk_size,
        chunk_overlap,
        _parse_recursive_separators_text(recursive_separators_text),
        _parse_chunk_config_json(chunk_config_json),
        process_mode,
        pipeline_id,
    )


@router.post(
    "/{knowledge_base_id}/documents/import-samples",
    response_model=KnowledgeSampleImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_sample_documents(knowledge_base_id: str, user: AdminUser) -> KnowledgeSampleImportResponse:
    imported_count = _service().import_sample_directory(knowledge_base_id)
    return KnowledgeSampleImportResponse(imported_count=imported_count)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/chunks",
    response_model=KnowledgeChunkListResponse,
)
def list_document_chunks(
    knowledge_base_id: str,
    document_id: int,
    user: CurrentUser,
) -> KnowledgeChunkListResponse:
    return _service().list_document_chunks(knowledge_base_id, document_id)


@router.patch(
    "/{knowledge_base_id}/documents/{document_id}/chunks/{chunk_id}",
    response_model=KnowledgeChunkItem,
)
def update_document_chunk(
    knowledge_base_id: str,
    document_id: int,
    chunk_id: int,
    request: KnowledgeChunkUpdateRequest,
    user: AdminUser,
) -> KnowledgeChunkItem:
    return _service().update_document_chunk(
        knowledge_base_id,
        document_id,
        chunk_id,
        enabled=request.enabled,
        content=request.content,
    )


@router.patch(
    "/{knowledge_base_id}/documents/{document_id}/chunks",
    response_model=KnowledgeChunkBatchUpdateResponse,
)
def update_document_chunks(
    knowledge_base_id: str,
    document_id: int,
    request: KnowledgeChunkBatchUpdateRequest,
    user: AdminUser,
) -> KnowledgeChunkBatchUpdateResponse:
    updated_count = _service().update_document_chunks_enabled(
        knowledge_base_id,
        document_id,
        request.chunk_ids,
        request.enabled,
    )
    return KnowledgeChunkBatchUpdateResponse(updated_count=updated_count)


@router.delete(
    "/{knowledge_base_id}/documents/{document_id}/chunks/{chunk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document_chunk(
    knowledge_base_id: str,
    document_id: int,
    chunk_id: int,
    user: AdminUser,
) -> None:
    _service().delete_document_chunk(knowledge_base_id, document_id, chunk_id)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/structured-blocks",
    response_model=KnowledgeDocumentStructuredBlockListResponse,
)
def list_document_structured_blocks(
    knowledge_base_id: str,
    document_id: int,
    user: CurrentUser,
) -> KnowledgeDocumentStructuredBlockListResponse:
    return _service().list_document_structured_blocks(knowledge_base_id, document_id)


@router.get(
    "/{knowledge_base_id}/route-profile",
    response_model=KnowledgeBaseRouteProfileItem,
)
def get_route_profile(
    knowledge_base_id: str,
    user: CurrentUser,
) -> KnowledgeBaseRouteProfileItem:
    return _service().get_route_profile(knowledge_base_id)


@router.put(
    "/{knowledge_base_id}/route-profile",
    response_model=KnowledgeBaseRouteProfileItem,
)
def update_route_profile(
    knowledge_base_id: str,
    request: KnowledgeBaseRouteProfileUpdateRequest,
    user: AdminUser,
) -> KnowledgeBaseRouteProfileItem:
    return _service().update_route_profile(knowledge_base_id, request)
