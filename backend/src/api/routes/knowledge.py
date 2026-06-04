from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status

from domain.knowledge import RetriFlowKnowledgeService
from schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeChunkListResponse,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentItem,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentStructuredBlockListResponse,
    KnowledgeSampleImportResponse,
)


router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge"])
service = RetriFlowKnowledgeService()


def _parse_recursive_separators_text(value: str | None) -> list[str] | None:
    if value is None:
        return None

    separators = [line for line in value.splitlines() if line != ""]
    return separators or None


@router.get("", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases() -> KnowledgeBaseListResponse:
    return service.list_knowledge_bases()


@router.post("", response_model=KnowledgeBaseItem, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(request: KnowledgeBaseCreateRequest) -> KnowledgeBaseItem:
    return service.create_knowledge_base(request)


@router.get("/{knowledge_base_id}/documents", response_model=KnowledgeDocumentListResponse)
def list_documents(knowledge_base_id: str) -> KnowledgeDocumentListResponse:
    return service.list_documents(knowledge_base_id)


@router.post(
    "/{knowledge_base_id}/documents",
    response_model=KnowledgeDocumentItem,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    knowledge_base_id: str,
    request: KnowledgeDocumentCreateRequest,
) -> KnowledgeDocumentItem:
    return service.create_document(knowledge_base_id, request)


@router.post(
    "/{knowledge_base_id}/documents/upload",
    response_model=KnowledgeDocumentItem,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: str,
    file: UploadFile = File(...),
    document_type: Annotated[str, Form()] = "knowledge_base",
    chunk_strategy: Annotated[str, Form()] = "auto",
    chunk_size: Annotated[int, Form()] = 600,
    chunk_overlap: Annotated[int, Form()] = 120,
    recursive_separators_text: Annotated[str | None, Form()] = None,
) -> KnowledgeDocumentItem:
    content = await file.read()
    return service.upload_document(
        knowledge_base_id,
        file.filename or "uploaded-document.txt",
        content,
        file.content_type,
        document_type,
        chunk_strategy,
        chunk_size,
        chunk_overlap,
        _parse_recursive_separators_text(recursive_separators_text),
    )


@router.post(
    "/{knowledge_base_id}/documents/import-samples",
    response_model=KnowledgeSampleImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_sample_documents(knowledge_base_id: str) -> KnowledgeSampleImportResponse:
    imported_count = service.import_sample_directory(knowledge_base_id)
    return KnowledgeSampleImportResponse(imported_count=imported_count)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/chunks",
    response_model=KnowledgeChunkListResponse,
)
def list_document_chunks(knowledge_base_id: str, document_id: int) -> KnowledgeChunkListResponse:
    return service.list_document_chunks(knowledge_base_id, document_id)


@router.get(
    "/{knowledge_base_id}/documents/{document_id}/structured-blocks",
    response_model=KnowledgeDocumentStructuredBlockListResponse,
)
def list_document_structured_blocks(
    knowledge_base_id: str,
    document_id: int,
) -> KnowledgeDocumentStructuredBlockListResponse:
    return service.list_document_structured_blocks(knowledge_base_id, document_id)
