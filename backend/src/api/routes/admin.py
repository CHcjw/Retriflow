from typing import Annotated

from fastapi import APIRouter, Query

from api.deps.auth import AdminUser
from modules.admin import RetriFlowAdminService
from schemas.admin import (
    AdminDashboardResponse,
    AdminIntentNodeCreateRequest,
    AdminIntentNodeItem,
    AdminIntentNodeListResponse,
    AdminIntentTreeCacheStatusResponse,
    AdminIntentNodeUpdateRequest,
    AdminKeywordMappingCreateRequest,
    AdminKeywordMappingItem,
    AdminKeywordMappingListResponse,
    AdminKeywordMappingUpdateRequest,
    AdminMessageFeedbackListResponse,
    AdminModelHealthListResponse,
    AdminModelHealthProbeRequest,
    AdminModelHealthItem,
    AdminSampleQuestionCreateRequest,
    AdminSampleQuestionItem,
    AdminSampleQuestionListResponse,
    AdminSampleQuestionUpdateRequest,
    AdminSettingListResponse,
    AdminTraceDetailResponse,
    AdminTraceListResponse,
    AdminTraceMemoryDiagnosticsResponse,
    AdminTraceNodeListResponse,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserPasswordChangeRequest,
    AdminUserRoleUpdateRequest,
    AdminUserUpdateRequest,
)


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

TraceIdQuery = Annotated[str, Query(pattern=r"^$|^\d{20}$")]


def _service() -> RetriFlowAdminService:
    return RetriFlowAdminService()


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_dashboard(
    user: AdminUser,
    range: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
) -> AdminDashboardResponse:
    return _service().get_dashboard(range)


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    user: AdminUser,
    q: str = Query(default="", max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AdminUserListResponse:
    return _service().list_users(query=q, page=page, page_size=page_size)


@router.post("/users", response_model=AdminUserItem, status_code=201)
def create_user(request: AdminUserCreateRequest, user: AdminUser) -> AdminUserItem:
    return _service().create_user(request)


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
def update_user_role(user_id: str, request: AdminUserRoleUpdateRequest, user: AdminUser) -> AdminUserItem:
    return _service().update_user_role(user_id, request.role)


@router.patch("/users/me/password", status_code=204)
def change_current_user_password(request: AdminUserPasswordChangeRequest, user: AdminUser) -> None:
    _service().change_user_password(user.id, request)


@router.patch("/users/{user_id}", response_model=AdminUserItem)
def update_user(user_id: str, request: AdminUserUpdateRequest, user: AdminUser) -> AdminUserItem:
    return _service().update_user(user_id, request)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, user: AdminUser) -> None:
    _service().delete_user(user_id, current_user_id=user.id)


@router.get("/intent-nodes", response_model=AdminIntentNodeListResponse)
def list_intent_nodes(user: AdminUser) -> AdminIntentNodeListResponse:
    return _service().list_intent_nodes()


@router.get("/intent-tree-cache", response_model=AdminIntentTreeCacheStatusResponse)
def get_intent_tree_cache_status(user: AdminUser) -> AdminIntentTreeCacheStatusResponse:
    return _service().get_intent_tree_cache_status()


@router.delete("/intent-tree-cache", response_model=AdminIntentTreeCacheStatusResponse)
def clear_intent_tree_cache(user: AdminUser) -> AdminIntentTreeCacheStatusResponse:
    return _service().clear_intent_tree_cache()


@router.post("/intent-nodes", response_model=AdminIntentNodeItem, status_code=201)
def create_intent_node(request: AdminIntentNodeCreateRequest, user: AdminUser) -> AdminIntentNodeItem:
    return _service().create_intent_node(request)


@router.patch("/intent-nodes/{node_id}", response_model=AdminIntentNodeItem)
def update_intent_node(
    node_id: str,
    request: AdminIntentNodeUpdateRequest,
    user: AdminUser,
) -> AdminIntentNodeItem:
    return _service().update_intent_node(node_id, request)


@router.delete("/intent-nodes/{node_id}", status_code=204)
def delete_intent_node(node_id: str, user: AdminUser) -> None:
    _service().delete_intent_node(node_id)


@router.get("/keyword-mappings", response_model=AdminKeywordMappingListResponse)
def list_keyword_mappings(user: AdminUser) -> AdminKeywordMappingListResponse:
    return _service().list_keyword_mappings()


@router.post("/keyword-mappings", response_model=AdminKeywordMappingItem, status_code=201)
def create_keyword_mapping(
    request: AdminKeywordMappingCreateRequest,
    user: AdminUser,
) -> AdminKeywordMappingItem:
    return _service().create_keyword_mapping(request)


@router.patch("/keyword-mappings/{mapping_id}", response_model=AdminKeywordMappingItem)
def update_keyword_mapping(
    mapping_id: str,
    request: AdminKeywordMappingUpdateRequest,
    user: AdminUser,
) -> AdminKeywordMappingItem:
    return _service().update_keyword_mapping(mapping_id, request)


@router.delete("/keyword-mappings/{mapping_id}", status_code=204)
def delete_keyword_mapping(mapping_id: str, user: AdminUser) -> None:
    _service().delete_keyword_mapping(mapping_id)


@router.get("/sample-questions", response_model=AdminSampleQuestionListResponse)
def list_sample_questions(
    user: AdminUser,
    enabled_only: bool = Query(default=False),
) -> AdminSampleQuestionListResponse:
    return _service().list_sample_questions(enabled_only=enabled_only)


@router.post("/sample-questions", response_model=AdminSampleQuestionItem, status_code=201)
def create_sample_question(
    request: AdminSampleQuestionCreateRequest,
    user: AdminUser,
) -> AdminSampleQuestionItem:
    return _service().create_sample_question(request)


@router.patch("/sample-questions/{sample_id}", response_model=AdminSampleQuestionItem)
def update_sample_question(
    sample_id: str,
    request: AdminSampleQuestionUpdateRequest,
    user: AdminUser,
) -> AdminSampleQuestionItem:
    return _service().update_sample_question(sample_id, request)


@router.delete("/sample-questions/{sample_id}", status_code=204)
def delete_sample_question(sample_id: str, user: AdminUser) -> None:
    _service().delete_sample_question(sample_id)


@router.get("/message-feedback", response_model=AdminMessageFeedbackListResponse)
def list_message_feedback(user: AdminUser) -> AdminMessageFeedbackListResponse:
    return _service().list_message_feedback()


@router.get("/traces", response_model=AdminTraceListResponse)
def list_traces(
    user: AdminUser,
    q: str = Query(default="", max_length=120),
    trace_id: TraceIdQuery = "",
    task_id: str = Query(default="", max_length=120),
    user_query: str = Query(default="", max_length=120),
    status: str = Query(default="", max_length=40),
    started_from: str = Query(default="", max_length=80),
    started_to: str = Query(default="", max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AdminTraceListResponse:
    return _service().list_traces(
        query=q,
        trace_id=trace_id,
        task_id=task_id,
        user_query=user_query,
        status_filter=status,
        started_from=started_from,
        started_to=started_to,
        page=page,
        page_size=page_size,
    )


@router.get("/traces/{session_id}", response_model=AdminTraceDetailResponse)
def get_trace_detail(session_id: str, user: AdminUser) -> AdminTraceDetailResponse:
    return _service().get_trace_detail(session_id)


@router.get("/traces/{session_id}/memory", response_model=AdminTraceMemoryDiagnosticsResponse)
def get_trace_memory_diagnostics(session_id: str, user: AdminUser) -> AdminTraceMemoryDiagnosticsResponse:
    return _service().get_trace_memory_diagnostics(session_id)


@router.get("/traces/{session_id}/nodes", response_model=AdminTraceNodeListResponse)
def get_trace_nodes(session_id: str, user: AdminUser) -> AdminTraceNodeListResponse:
    return _service().get_trace_nodes(session_id)


@router.get("/model-health", response_model=AdminModelHealthListResponse)
def list_model_health(user: AdminUser) -> AdminModelHealthListResponse:
    return _service().list_model_health()


@router.post("/model-health/probe", response_model=AdminModelHealthItem)
def probe_model_health(request: AdminModelHealthProbeRequest, user: AdminUser) -> AdminModelHealthItem:
    return _service().probe_model_health(request)


@router.get("/settings", response_model=AdminSettingListResponse)
def list_settings(user: AdminUser) -> AdminSettingListResponse:
    return _service().list_settings()
