from fastapi import APIRouter, Query

from api.deps.auth import AdminUser
from modules.ingestion import RetriFlowIngestionService
from schemas.knowledge import (
    IngestionPipelineCreateRequest,
    IngestionPipelineItem,
    IngestionPipelineListResponse,
    IngestionPipelineUpdateRequest,
    IngestionTaskListResponse,
    IngestionTaskNodeListResponse,
)


router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


def _service() -> RetriFlowIngestionService:
    return RetriFlowIngestionService()


@router.get("/pipelines", response_model=IngestionPipelineListResponse)
def list_pipelines(user: AdminUser) -> IngestionPipelineListResponse:
    return _service().list_pipelines()


@router.post("/pipelines", response_model=IngestionPipelineItem, status_code=201)
def create_pipeline(request: IngestionPipelineCreateRequest, user: AdminUser) -> IngestionPipelineItem:
    return _service().create_pipeline(request)


@router.patch("/pipelines/{pipeline_id}", response_model=IngestionPipelineItem)
def update_pipeline(
    pipeline_id: int,
    request: IngestionPipelineUpdateRequest,
    user: AdminUser,
) -> IngestionPipelineItem:
    return _service().update_pipeline(pipeline_id, request)


@router.delete("/pipelines/{pipeline_id}", status_code=204)
def delete_pipeline(pipeline_id: int, user: AdminUser) -> None:
    _service().delete_pipeline(pipeline_id)


@router.get("/tasks", response_model=IngestionTaskListResponse)
def list_tasks(user: AdminUser, document_id: int | None = Query(default=None)) -> IngestionTaskListResponse:
    return _service().list_tasks(document_id=document_id)


@router.get("/tasks/{task_id}/nodes", response_model=IngestionTaskNodeListResponse)
def list_task_nodes(task_id: int, user: AdminUser) -> IngestionTaskNodeListResponse:
    return _service().list_task_nodes(task_id)
