from pydantic import BaseModel, Field


class AdminUserItem(BaseModel):
    id: str
    username: str
    role: str
    avatar_url: str = ""
    created_at: str


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int = 0
    page: int = 1
    page_size: int = 20


class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    avatar_url: str = ""


class AdminUserRoleUpdateRequest(BaseModel):
    role: str


class AdminUserUpdateRequest(BaseModel):
    username: str | None = None
    role: str | None = None
    avatar_url: str | None = None


class AdminUserPasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class AdminTraceMessageItem(BaseModel):
    id: int
    role: str
    content_preview: str
    created_at: str
    duration_ms: int = 0


class AdminTraceSessionItem(BaseModel):
    id: str
    trace_id: str = ""
    task_id: str = ""
    status: str = ""
    title: str
    owner_id: str
    owner_username: str
    message_count: int
    started_at: str = ""
    latest_message_at: str
    duration_ms: int = 0
    latest_messages: list[AdminTraceMessageItem]


class AdminTraceListResponse(BaseModel):
    items: list[AdminTraceSessionItem]
    total: int = 0
    page: int = 1
    page_size: int = 20


class AdminTraceDetailResponse(AdminTraceSessionItem):
    messages: list[AdminTraceMessageItem]


class AdminTraceMemoryDiagnosticsResponse(BaseModel):
    session_id: str
    has_summary: bool
    summary_preview: str = ""
    recent_message_count: int = 0
    mid_term_count: int = 0
    long_term_count: int = 0
    prompt_message_count: int = 0


class AdminTraceNodeItem(BaseModel):
    id: str
    session_id: str
    task_id: str = ""
    parent_id: str = ""
    name: str
    node_type: str
    status: str
    input_summary: str = ""
    output_summary: str = ""
    error_message: str = ""
    metadata: dict[str, object] = {}
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0


class AdminTraceNodeListResponse(BaseModel):
    items: list[AdminTraceNodeItem]


class AdminMessageFeedbackItem(BaseModel):
    id: int
    message_id: int
    session_id: str
    user_id: str
    username: str = ""
    vote: int
    reason: str = ""
    comment: str = ""
    message_preview: str = ""
    created_at: str = ""
    updated_at: str = ""


class AdminMessageFeedbackListResponse(BaseModel):
    items: list[AdminMessageFeedbackItem]


class AdminModelHealthItem(BaseModel):
    capability: str
    provider_name: str
    model: str
    state: str
    failure_count: int = 0
    success_count: int = 0
    opened_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str = ""
    last_success_duration_ms: int | None = None
    last_first_packet_ms: int | None = None
    half_open_in_flight: bool = False


class AdminModelHealthListResponse(BaseModel):
    items: list[AdminModelHealthItem]


class AdminModelHealthProbeRequest(BaseModel):
    capability: str = "chat"
    provider_name: str = ""
    model: str = ""


class AdminMcpParameterItem(BaseModel):
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""
    default: object | None = None
    enum: list[object] = Field(default_factory=list)


class AdminMcpToolItem(BaseModel):
    tool_id: str
    description: str = ""
    server_name: str = "builtin"
    transport: str = "builtin"
    schema_version: str = "json_schema"
    parameter_count: int = 0
    keywords: list[str] = Field(default_factory=list)
    parameters: list[AdminMcpParameterItem] = Field(default_factory=list)


class AdminMcpRemoteServerItem(BaseModel):
    name: str
    url: str
    healthy: bool
    tool_count: int = 0
    error: str = ""


class AdminMcpStatusResponse(BaseModel):
    tools: list[AdminMcpToolItem]
    remote_servers: list[AdminMcpRemoteServerItem]
    total_tools: int = 0
    remote_enabled: bool = False


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
    mcp_tool_id: str = ""
    collection_name: str = ""
    description: str = ""
    sample_questions: list[str] = []
    rule_snippet: str = ""
    prompt_template: str = ""
    param_prompt_template: str = ""
    top_k: int | None = None
    min_score: float | None = None
    sort_order: int = 0
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


class AdminIntentNodeListResponse(BaseModel):
    items: list[AdminIntentNodeItem]


class AdminIntentTreeCacheStatusResponse(BaseModel):
    enabled: bool
    available: bool
    exists: bool
    key: str
    ttl_seconds: int | None = None
    ttl_days: int = 7
    backend: str = "redis"
    error: str = ""


class AdminIntentNodeCreateRequest(BaseModel):
    name: str
    code: str
    level: str = "INTENT"
    node_type: str = "KB"
    parent_id: str = "ROOT"
    knowledge_base_id: str = ""
    mcp_tool_id: str = ""
    collection_name: str = ""
    description: str = ""
    sample_questions: list[str] = []
    rule_snippet: str = ""
    prompt_template: str = ""
    param_prompt_template: str = ""
    top_k: int | None = None
    min_score: float | None = None
    sort_order: int = 0
    enabled: bool = True


class AdminIntentNodeUpdateRequest(BaseModel):
    name: str | None = None
    code: str | None = None
    level: str | None = None
    node_type: str | None = None
    parent_id: str | None = None
    knowledge_base_id: str | None = None
    mcp_tool_id: str | None = None
    collection_name: str | None = None
    description: str | None = None
    sample_questions: list[str] | None = None
    rule_snippet: str | None = None
    prompt_template: str | None = None
    param_prompt_template: str | None = None
    top_k: int | None = None
    min_score: float | None = None
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


class AdminSampleQuestionItem(BaseModel):
    id: str
    title: str
    description: str = ""
    question: str
    sort_order: int = 0
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


class AdminSampleQuestionListResponse(BaseModel):
    items: list[AdminSampleQuestionItem]


class AdminSampleQuestionCreateRequest(BaseModel):
    title: str
    description: str = ""
    question: str
    sort_order: int = 0
    enabled: bool = True


class AdminSampleQuestionUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    question: str | None = None
    sort_order: int | None = None
    enabled: bool | None = None
