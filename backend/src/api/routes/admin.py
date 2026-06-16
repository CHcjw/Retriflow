from fastapi import APIRouter, Query

from api.deps.auth import AdminUser
from modules.admin import RetriFlowAdminService
from schemas.admin import (
    AdminDashboardResponse,
    AdminIntentNodeCreateRequest,
    AdminIntentNodeItem,
    AdminIntentNodeListResponse,
    AdminIntentNodeUpdateRequest,
    AdminKeywordMappingCreateRequest,
    AdminKeywordMappingItem,
    AdminKeywordMappingListResponse,
    AdminKeywordMappingUpdateRequest,
    AdminSettingListResponse,
    AdminTraceDetailResponse,
    AdminTraceListResponse,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserRoleUpdateRequest,
)


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _service() -> RetriFlowAdminService:
    return RetriFlowAdminService()


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_dashboard(
    user: AdminUser,
    range: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
) -> AdminDashboardResponse:
    return _service().get_dashboard(range)


@router.get("/users", response_model=AdminUserListResponse)
def list_users(user: AdminUser) -> AdminUserListResponse:
    return _service().list_users()


@router.post("/users", response_model=AdminUserItem, status_code=201)
def create_user(request: AdminUserCreateRequest, user: AdminUser) -> AdminUserItem:
    return _service().create_user(request)


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
def update_user_role(user_id: str, request: AdminUserRoleUpdateRequest, user: AdminUser) -> AdminUserItem:
    return _service().update_user_role(user_id, request.role)


@router.get("/intent-nodes", response_model=AdminIntentNodeListResponse)
def list_intent_nodes(user: AdminUser) -> AdminIntentNodeListResponse:
    return _service().list_intent_nodes()


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


@router.get("/traces", response_model=AdminTraceListResponse)
def list_traces(user: AdminUser) -> AdminTraceListResponse:
    return _service().list_traces()


@router.get("/traces/{session_id}", response_model=AdminTraceDetailResponse)
def get_trace_detail(session_id: str, user: AdminUser) -> AdminTraceDetailResponse:
    return _service().get_trace_detail(session_id)


@router.get("/settings", response_model=AdminSettingListResponse)
def list_settings(user: AdminUser) -> AdminSettingListResponse:
    return _service().list_settings()
