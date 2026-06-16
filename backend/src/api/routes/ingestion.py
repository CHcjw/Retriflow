from fastapi import APIRouter

from api.deps.auth import AdminUser
from modules.ingestion import RetriFlowIngestionService
from schemas.knowledge import (
    IngestionPipelineCreateRequest,
    IngestionPipelineItem,
    IngestionPipelineListResponse,
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


@router.get("/tasks", response_model=IngestionTaskListResponse)
def list_tasks(user: AdminUser) -> IngestionTaskListResponse:
    return _service().list_tasks()


@router.get("/tasks/{task_id}/nodes", response_model=IngestionTaskNodeListResponse)
def list_task_nodes(task_id: int, user: AdminUser) -> IngestionTaskNodeListResponse:
    return _service().list_task_nodes(task_id)
