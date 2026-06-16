from pydantic import BaseModel


class AdminUserItem(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]


class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class AdminUserRoleUpdateRequest(BaseModel):
    role: str


class AdminTraceMessageItem(BaseModel):
    id: int
    role: str
    content_preview: str
    created_at: str
    duration_ms: int = 0


class AdminTraceSessionItem(BaseModel):
    id: str
    title: str
    owner_id: str
    owner_username: str
    message_count: int
    latest_message_at: str
    duration_ms: int = 0
    latest_messages: list[AdminTraceMessageItem]


class AdminTraceListResponse(BaseModel):
    items: list[AdminTraceSessionItem]


class AdminTraceDetailResponse(AdminTraceSessionItem):
    messages: list[AdminTraceMessageItem]


class AdminSettingItem(BaseModel):
    key: str
    value: str
    category: str
    sensitive: bool = False


class AdminSettingListResponse(BaseModel):
    items: list[AdminSettingItem]


class AdminDashboardMetricCard(BaseModel):
    key: str
    label: str
    value: str
    helper: str = ""
    delta: str = ""


class AdminDashboardSeries(BaseModel):
    key: str
    label: str
    color: str
    values: list[float]


class AdminDashboardAiPerformance(BaseModel):
    success_rate: float
    completion_rate: float
    avg_response_ms: int
    p95_response_ms: int
    no_answer_rate: float


class AdminDashboardTrafficOverview(BaseModel):
    labels: list[str]
    series: list[AdminDashboardSeries]
    total_sessions: int
    total_messages: int
    total_active_users: int


class AdminDashboardTrendPanel(BaseModel):
    key: str
    label: str
    unit: str
    summary: str
    series: list[AdminDashboardSeries]


class AdminDashboardOpsInsight(BaseModel):
    level: str
    category: str
    title: str
    message: str
    time_label: str = ""


class AdminDashboardResponse(BaseModel):
    range: str
    range_label: str
    generated_at: str
    core: list[AdminDashboardMetricCard]
    ai_performance: AdminDashboardAiPerformance
    traffic_overview: AdminDashboardTrafficOverview
    trend_panels: list[AdminDashboardTrendPanel]
    quality_snapshot: list[AdminDashboardMetricCard]
    ops_efficiency: list[AdminDashboardMetricCard]
    ops_insights: list[AdminDashboardOpsInsight]


class AdminIntentNodeItem(BaseModel):
    id: str
    name: str
    code: str
    level: str
    node_type: str
    parent_id: str
    knowledge_base_id: str = ""
    collection_name: str = ""
    description: str = ""
    sample_questions: list[str] = []
    rule_snippet: str = ""
    prompt_template: str = ""
    top_k: int | None = None
    sort_order: int = 0
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


class AdminIntentNodeListResponse(BaseModel):
    items: list[AdminIntentNodeItem]


class AdminIntentNodeCreateRequest(BaseModel):
    name: str
    code: str
    level: str = "INTENT"
    node_type: str = "KB"
    parent_id: str = "ROOT"
    knowledge_base_id: str = ""
    collection_name: str = ""
    description: str = ""
    sample_questions: list[str] = []
    rule_snippet: str = ""
    prompt_template: str = ""
    top_k: int | None = None
    sort_order: int = 0
    enabled: bool = True


class AdminIntentNodeUpdateRequest(BaseModel):
    name: str | None = None
    code: str | None = None
    level: str | None = None
    node_type: str | None = None
    parent_id: str | None = None
    knowledge_base_id: str | None = None
    collection_name: str | None = None
    description: str | None = None
    sample_questions: list[str] | None = None
    rule_snippet: str | None = None
    prompt_template: str | None = None
    top_k: int | None = None
    sort_order: int | None = None
    enabled: bool | None = None


class AdminKeywordMappingItem(BaseModel):
    id: str
    raw_keyword: str
    target_keyword: str
    match_type: str = "exact"
    priority: int = 0
    enabled: bool = True
    remark: str = ""
    knowledge_base_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class AdminKeywordMappingListResponse(BaseModel):
    items: list[AdminKeywordMappingItem]


class AdminKeywordMappingCreateRequest(BaseModel):
    raw_keyword: str
    target_keyword: str
    match_type: str = "exact"
    priority: int = 0
    enabled: bool = True
    remark: str = ""
    knowledge_base_id: str = ""


class AdminKeywordMappingUpdateRequest(BaseModel):
    raw_keyword: str | None = None
    target_keyword: str | None = None
    match_type: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    remark: str | None = None
    knowledge_base_id: str | None = None
