from fastapi import APIRouter

from domain.ingestion import RetriFlowIngestionService
from schemas.knowledge import IngestionTaskListResponse, IngestionTaskNodeListResponse


router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])
service = RetriFlowIngestionService()


@router.get("/tasks", response_model=IngestionTaskListResponse)
def list_tasks() -> IngestionTaskListResponse:
    return service.list_tasks()


@router.get("/tasks/{task_id}/nodes", response_model=IngestionTaskNodeListResponse)
def list_task_nodes(task_id: int) -> IngestionTaskNodeListResponse:
    return service.list_task_nodes(task_id)
