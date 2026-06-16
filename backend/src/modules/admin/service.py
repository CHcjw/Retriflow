import json
import uuid
from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import HTTPException, status

from core.config import get_settings
from core.state import get_connection
from modules.auth import RetriFlowAuthService
from modules.rag.postprocess import RetriFlowAnswerPostprocessor
from schemas.admin import (
    AdminDashboardAiPerformance,
    AdminDashboardMetricCard,
    AdminDashboardOpsInsight,
    AdminDashboardResponse,
    AdminDashboardSeries,
    AdminDashboardTrafficOverview,
    AdminDashboardTrendPanel,
    AdminIntentNodeCreateRequest,
    AdminIntentNodeItem,
    AdminIntentNodeListResponse,
    AdminIntentNodeUpdateRequest,
    AdminKeywordMappingCreateRequest,
    AdminKeywordMappingItem,
    AdminKeywordMappingListResponse,
    AdminKeywordMappingUpdateRequest,
    AdminSettingItem,
    AdminSettingListResponse,
    AdminTraceDetailResponse,
    AdminTraceListResponse,
    AdminTraceMessageItem,
    AdminTraceSessionItem,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
)
from schemas.auth import AuthRegisterRequest


class RetriFlowAdminService:
    def get_dashboard(self, range_key: str = "24h") -> AdminDashboardResponse:
        normalized_range, range_hours, range_label, bucket_count = self._resolve_dashboard_range(range_key)
        now = datetime.now(timezone.utc)
        start_at = now - timedelta(hours=range_hours)

        with get_connection() as connection:
            user_count = self._count(connection, "users")
            session_count = self._count(connection, "sessions")
            knowledge_count = self._count(connection, "knowledge_bases")
            document_count = self._count(connection, "knowledge_documents")
            chunk_count = self._count(connection, "knowledge_chunks")
            task_count = self._count(connection, "ingestion_tasks")
            indexed_documents = connection.execute(
                "select count(*) from knowledge_documents where vector_index_status = ?",
                ("indexed",),
            ).fetchone()[0]
            message_rows = connection.execute(
                """
                select
                    cm.session_id,
                    cm.role,
                    cm.content,
                    cm.created_at,
                    coalesce(cm.duration_ms, 0) as duration_ms,
                    coalesce(s.owner_id, '') as owner_id,
                    coalesce(u.username, s.owner_id, 'anonymous') as owner_label
                from conversation_messages cm
                left join sessions s on s.id = cm.session_id
                left join users u on u.id = s.owner_id
                order by cm.session_id, cm.id asc
                """
            ).fetchall()
            ingestion_rows = connection.execute(
                """
                select status, created_at
                from ingestion_tasks
                order by created_at asc
                """
            ).fetchall()

        window_message_rows = self._filter_rows_by_time(message_rows, start_at)
        window_ingestion_rows = self._filter_rows_by_time(ingestion_rows, start_at)
        response_durations = self._estimate_response_durations(window_message_rows)
        active_session_ids = {str(row["session_id"]) for row in window_message_rows}
        active_user_labels = {
            str(row.get("owner_label", "")).strip()
            for row in window_message_rows
            if str(row.get("owner_label", "")).strip()
        }

        active_session_count = len(active_session_ids)
        active_user_count = len(active_user_labels)
        window_message_count = len(window_message_rows)
        user_message_count = len([row for row in window_message_rows if str(row["role"]) == "user"])
        assistant_message_count = len([row for row in window_message_rows if str(row["role"]) == "assistant"])
        no_answer_count = len(
            [
                row
                for row in window_message_rows
                if str(row["role"]) == "assistant"
                and RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER in str(row.get("content", ""))
            ]
        )
        avg_response_ms = int(mean(response_durations)) if response_durations else 0
        p95_response_ms = self._percentile(response_durations, 0.95)
        success_rate = round((assistant_message_count / max(user_message_count, 1)) * 100, 1) if user_message_count else 0.0
        completion_rate = round((min(user_message_count, assistant_message_count) / max(user_message_count, 1)) * 100, 1) if user_message_count else 0.0
        avg_depth = round(window_message_count / max(active_session_count, 1), 2) if active_session_count else 0.0
        indexed_rate = round((int(indexed_documents or 0) / max(document_count, 1)) * 100, 1) if document_count else 0.0
        completed_tasks = len([row for row in window_ingestion_rows if str(row["status"]).lower() in {"completed", "success", "indexed"}])
        failed_tasks = len([row for row in window_ingestion_rows if str(row["status"]).lower() in {"failed", "error"}])
        no_answer_rate = round((no_answer_count / max(assistant_message_count, 1)) * 100, 1) if assistant_message_count else 0.0
        slow_response_count = len([duration for duration in response_durations if duration > 20_000])
        slow_response_rate = round((slow_response_count / max(len(response_durations), 1)) * 100, 1) if response_durations else 0.0
        error_rate = round((failed_tasks / max(len(window_ingestion_rows), 1)) * 100, 1) if window_ingestion_rows else 0.0
        avg_sessions_per_user = round(active_session_count / max(active_user_count, 1), 2) if active_user_count else 0.0
        avg_messages_per_session = round(window_message_count / max(active_session_count, 1), 2) if active_session_count else 0.0
        avg_messages_per_user = round(window_message_count / max(active_user_count, 1), 2) if active_user_count else 0.0

        buckets = self._build_time_buckets(start_at, now, bucket_count)
        traffic_overview, trend_panels = self._build_dashboard_series(
            message_rows=window_message_rows,
            ingestion_rows=window_ingestion_rows,
            buckets=buckets,
        )

        return AdminDashboardResponse(
            range=normalized_range,
            range_label=range_label,
            generated_at=self._serialize_timestamp(now),
            core=[
                AdminDashboardMetricCard(
                    key="active_users",
                    label="活跃用户",
                    value=str(active_user_count),
                    helper=f"{range_label}内有消息行为的用户",
                    delta=f"注册用户 {user_count}",
                ),
                AdminDashboardMetricCard(
                    key="sessions",
                    label="会话数",
                    value=str(active_session_count),
                    helper=f"{range_label}内活跃会话",
                    delta=f"全量 {session_count}",
                ),
                AdminDashboardMetricCard(
                    key="messages",
                    label="消息数",
                    value=str(window_message_count),
                    helper=f"用户 {user_message_count} / 助手 {assistant_message_count}",
                    delta=f"入库任务总数 {task_count}",
                ),
                AdminDashboardMetricCard(
                    key="depth",
                    label="会话深度",
                    value=f"{avg_depth}",
                    helper="消息数 / 活跃会话",
                    delta=f"知识资产 {knowledge_count}/{document_count}/{chunk_count}",
                ),
            ],
            ai_performance=AdminDashboardAiPerformance(
                success_rate=success_rate,
                completion_rate=completion_rate,
                avg_response_ms=avg_response_ms,
                p95_response_ms=p95_response_ms,
                no_answer_rate=no_answer_rate,
            ),
            traffic_overview=traffic_overview,
            trend_panels=trend_panels,
            quality_snapshot=[
                AdminDashboardMetricCard(
                    key="indexed_rate",
                    label="索引完成率",
                    value=f"{indexed_rate}%",
                    helper="已建索引文档 / 全部文档",
                    delta=f"已索引 {indexed_documents}",
                ),
                AdminDashboardMetricCard(
                    key="no_answer_rate",
                    label="未命中率",
                    value=f"{no_answer_rate}%",
                    helper="兜底回复占助手回复比例",
                    delta=f"{no_answer_count} 次",
                ),
                AdminDashboardMetricCard(
                    key="slow_response_rate",
                    label="慢响应率",
                    value=f"{slow_response_rate}%",
                    helper="大于 20s 的回复比例",
                    delta=f"{slow_response_count} 次",
                ),
                AdminDashboardMetricCard(
                    key="error_rate",
                    label="任务失败率",
                    value=f"{error_rate}%",
                    helper="当前时间窗入库任务失败比例",
                    delta=f"失败 {failed_tasks} / 完成 {completed_tasks}",
                ),
            ],
            ops_efficiency=[
                AdminDashboardMetricCard(
                    key="sessions_per_user",
                    label="人均会话",
                    value=f"{avg_sessions_per_user}",
                    helper="活跃会话 / 活跃用户",
                ),
                AdminDashboardMetricCard(
                    key="messages_per_session",
                    label="单会话消息",
                    value=f"{avg_messages_per_session}",
                    helper="消息数 / 活跃会话",
                ),
                AdminDashboardMetricCard(
                    key="messages_per_user",
                    label="人均消息",
                    value=f"{avg_messages_per_user}",
                    helper="消息数 / 活跃用户",
                ),
            ],
            ops_insights=self._build_ops_insights(
                range_label=range_label,
                generated_at=now,
                active_user_count=active_user_count,
                active_session_count=active_session_count,
                window_message_count=window_message_count,
                avg_response_ms=avg_response_ms,
                p95_response_ms=p95_response_ms,
                indexed_rate=indexed_rate,
                no_answer_rate=no_answer_rate,
                slow_response_rate=slow_response_rate,
                failed_tasks=failed_tasks,
            ),
        )

    def create_user(self, request: AdminUserCreateRequest) -> AdminUserItem:
        normalized_role = request.role.strip().lower() or "user"
        if normalized_role not in {"admin", "user"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be admin or user")
        created = RetriFlowAuthService().register(
            AuthRegisterRequest(username=request.username, password=request.password, role=normalized_role)
        )
        with get_connection() as connection:
            row = connection.execute(
                "select id, username, role, created_at from users where id = ?",
                (created.id,),
            ).fetchone()
        return self._to_user(row)

    def list_users(self) -> AdminUserListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, username, role, created_at
                from users
                order by created_at desc, username
                """
            ).fetchall()
        return AdminUserListResponse(items=[self._to_user(row) for row in rows])

    def update_user_role(self, user_id: str, role: str) -> AdminUserItem:
        normalized_role = role.strip().lower()
        if normalized_role not in {"admin", "user"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be admin or user")
        with get_connection() as connection:
            if connection.execute("select id from users where id = ?", (user_id,)).fetchone() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
            connection.execute("update users set role = ? where id = ?", (normalized_role, user_id))
            connection.commit()
            updated = connection.execute(
                "select id, username, role, created_at from users where id = ?",
                (user_id,),
            ).fetchone()
        return self._to_user(updated)

    def list_intent_nodes(self) -> AdminIntentNodeListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select *
                from admin_intent_nodes
                order by parent_id, sort_order, created_at, name
                """
            ).fetchall()
        return AdminIntentNodeListResponse(items=[self._to_intent_node(row) for row in rows])

    def create_intent_node(self, request: AdminIntentNodeCreateRequest) -> AdminIntentNodeItem:
        node_id = f"intent-{uuid.uuid4().hex[:12]}"
        code = self._normalize_required(request.code, "code")
        name = self._normalize_required(request.name, "name")
        with get_connection() as connection:
            try:
                connection.execute(
                    """
                    insert into admin_intent_nodes (
                        id, name, code, level, node_type, parent_id, knowledge_base_id,
                        collection_name, description, sample_questions_json, rule_snippet,
                        prompt_template, top_k, sort_order, enabled
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        name,
                        code,
                        request.level.strip() or "INTENT",
                        request.node_type.strip() or "KB",
                        request.parent_id.strip() or "ROOT",
                        request.knowledge_base_id.strip(),
                        request.collection_name.strip(),
                        request.description.strip(),
                        json.dumps(request.sample_questions, ensure_ascii=False),
                        request.rule_snippet.strip(),
                        request.prompt_template.strip(),
                        request.top_k,
                        request.sort_order,
                        1 if request.enabled else 0,
                    ),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                if "unique" in str(exc).lower():
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="intent code already exists") from exc
                raise
            row = self._get_intent_node_row(connection, node_id)
        return self._to_intent_node(row)

    def update_intent_node(self, node_id: str, request: AdminIntentNodeUpdateRequest) -> AdminIntentNodeItem:
        mapping = request.model_dump(exclude_unset=True)
        if "name" in mapping:
            mapping["name"] = self._normalize_required(str(mapping["name"]), "name")
        if "code" in mapping:
            mapping["code"] = self._normalize_required(str(mapping["code"]), "code")
        if "sample_questions" in mapping:
            mapping["sample_questions_json"] = json.dumps(mapping.pop("sample_questions") or [], ensure_ascii=False)
        if "enabled" in mapping:
            mapping["enabled"] = 1 if mapping["enabled"] else 0
        fields = [f"{key} = ?" for key in mapping]
        values = list(mapping.values())
        if fields:
            fields.append("updated_at = current_timestamp")
        with get_connection() as connection:
            if self._get_intent_node_row(connection, node_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="intent node not found")
            if fields:
                try:
                    connection.execute(
                        f"update admin_intent_nodes set {', '.join(fields)} where id = ?",
                        [*values, node_id],
                    )
                    connection.commit()
                except Exception as exc:
                    connection.rollback()
                    if "unique" in str(exc).lower():
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="intent code already exists") from exc
                    raise
            row = self._get_intent_node_row(connection, node_id)
        return self._to_intent_node(row)

    def delete_intent_node(self, node_id: str) -> None:
        with get_connection() as connection:
            if self._get_intent_node_row(connection, node_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="intent node not found")
            connection.execute("delete from admin_intent_nodes where id = ?", (node_id,))
            connection.execute("update admin_intent_nodes set parent_id = ? where parent_id = ?", ("ROOT", node_id))
            connection.commit()

    def list_keyword_mappings(self) -> AdminKeywordMappingListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select *
                from admin_keyword_mappings
                order by priority desc, raw_keyword, created_at desc
                """
            ).fetchall()
        return AdminKeywordMappingListResponse(items=[self._to_keyword_mapping(row) for row in rows])

    def create_keyword_mapping(self, request: AdminKeywordMappingCreateRequest) -> AdminKeywordMappingItem:
        mapping_id = f"keyword-{uuid.uuid4().hex[:12]}"
        raw_keyword = self._normalize_required(request.raw_keyword, "raw_keyword")
        target_keyword = self._normalize_required(request.target_keyword, "target_keyword")
        with get_connection() as connection:
            connection.execute(
                """
                insert into admin_keyword_mappings (
                    id, raw_keyword, target_keyword, match_type, priority, enabled, remark, knowledge_base_id
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_id,
                    raw_keyword,
                    target_keyword,
                    request.match_type.strip() or "exact",
                    request.priority,
                    1 if request.enabled else 0,
                    request.remark.strip(),
                    request.knowledge_base_id.strip(),
                ),
            )
            connection.commit()
            row = self._get_keyword_mapping_row(connection, mapping_id)
        return self._to_keyword_mapping(row)

    def update_keyword_mapping(self, mapping_id: str, request: AdminKeywordMappingUpdateRequest) -> AdminKeywordMappingItem:
        mapping = request.model_dump(exclude_unset=True)
        if "raw_keyword" in mapping:
            mapping["raw_keyword"] = self._normalize_required(str(mapping["raw_keyword"]), "raw_keyword")
        if "target_keyword" in mapping:
            mapping["target_keyword"] = self._normalize_required(str(mapping["target_keyword"]), "target_keyword")
        if "enabled" in mapping:
            mapping["enabled"] = 1 if mapping["enabled"] else 0
        fields = [f"{key} = ?" for key in mapping]
        values = list(mapping.values())
        if fields:
            fields.append("updated_at = current_timestamp")
        with get_connection() as connection:
            if self._get_keyword_mapping_row(connection, mapping_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="keyword mapping not found")
            if fields:
                connection.execute(
                    f"update admin_keyword_mappings set {', '.join(fields)} where id = ?",
                    [*values, mapping_id],
                )
                connection.commit()
            row = self._get_keyword_mapping_row(connection, mapping_id)
        return self._to_keyword_mapping(row)

    def delete_keyword_mapping(self, mapping_id: str) -> None:
        with get_connection() as connection:
            if self._get_keyword_mapping_row(connection, mapping_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="keyword mapping not found")
            connection.execute("delete from admin_keyword_mappings where id = ?", (mapping_id,))
            connection.commit()

    def list_traces(self) -> AdminTraceListResponse:
        with get_connection() as connection:
            session_rows = connection.execute(
                """
                select
                    s.id,
                    s.title,
                    s.owner_id,
                    coalesce(u.username, '') as owner_username,
                    s.message_count,
                    max(cm.created_at) as latest_message_at
                from sessions s
                left join users u on u.id = s.owner_id
                left join conversation_messages cm on cm.session_id = s.id
                group by s.id, s.title, s.owner_id, u.username, s.message_count
                order by max(cm.created_at) desc nulls last, s.id desc
                """
            ).fetchall()
            items: list[AdminTraceSessionItem] = []
            for session_row in session_rows:
                message_rows = connection.execute(
                    """
                    select id, role, content, created_at, duration_ms
                    from conversation_messages
                    where session_id = ?
                    order by id desc
                    limit 4
                    """,
                    (session_row["id"],),
                ).fetchall()
                items.append(
                    AdminTraceSessionItem(
                        id=session_row["id"],
                        title=session_row["title"],
                        owner_id=str(session_row.get("owner_id", "") or ""),
                        owner_username=str(session_row.get("owner_username", "") or ""),
                        message_count=int(session_row["message_count"] or 0),
                        latest_message_at=self._serialize_timestamp(session_row.get("latest_message_at")),
                        duration_ms=self._session_duration_ms(connection, session_row["id"]),
                        latest_messages=[self._to_trace_message(row) for row in reversed(message_rows)],
                    )
                )
        return AdminTraceListResponse(items=items)

    def get_trace_detail(self, session_id: str) -> AdminTraceDetailResponse:
        with get_connection() as connection:
            session_row = connection.execute(
                """
                select
                    s.id,
                    s.title,
                    s.owner_id,
                    coalesce(u.username, '') as owner_username,
                    s.message_count,
                    max(cm.created_at) as latest_message_at
                from sessions s
                left join users u on u.id = s.owner_id
                left join conversation_messages cm on cm.session_id = s.id
                where s.id = ?
                group by s.id, s.title, s.owner_id, u.username, s.message_count
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
            message_rows = connection.execute(
                """
                select id, role, content, created_at, duration_ms
                from conversation_messages
                where session_id = ?
                order by id asc
                """,
                (session_id,),
            ).fetchall()
            session_duration_ms = self._session_duration_ms(connection, session_id)
        messages = [self._to_trace_message(row, preview_limit=600) for row in message_rows]
        return AdminTraceDetailResponse(
            id=session_row["id"],
            title=session_row["title"],
            owner_id=str(session_row.get("owner_id", "") or ""),
            owner_username=str(session_row.get("owner_username", "") or ""),
            message_count=int(session_row["message_count"] or 0),
            latest_message_at=self._serialize_timestamp(session_row.get("latest_message_at")),
            duration_ms=session_duration_ms,
            latest_messages=messages[-4:],
            messages=messages,
        )

    def list_settings(self) -> AdminSettingListResponse:
        settings = get_settings()
        raw_items = [
            ("app_name", settings.app_name, "应用"),
            ("app_version", settings.app_version, "应用"),
            ("api_prefix", settings.api_prefix, "应用"),
            ("database_backend", settings.database_backend, "数据库"),
            ("database_schema", settings.database_schema, "数据库"),
            ("vector_store_type", settings.vector_store_type, "向量库"),
            ("pgvector_table", settings.pgvector_table, "向量库"),
            ("default_chat_model", settings.default_chat_model, "模型"),
            ("deep_thinking_model", settings.deep_thinking_model, "模型"),
            ("default_embedding_model", settings.default_embedding_model, "模型"),
            ("default_rerank_model", settings.default_rerank_model, "模型"),
            ("chat_provider", settings.chat_provider, "模型供应商"),
            ("rewrite_provider", settings.rewrite_provider, "模型供应商"),
            ("route_provider", settings.route_provider, "模型供应商"),
            ("intent_provider", settings.intent_provider, "模型供应商"),
            ("embedding_provider", settings.embedding_provider, "模型供应商"),
            ("rerank_provider", settings.rerank_provider, "模型供应商"),
            ("retrieval_bm25_top_k", settings.retrieval_bm25_top_k, "检索"),
            ("retrieval_vector_top_k", settings.retrieval_vector_top_k, "检索"),
            ("retrieval_rrf_top_k", settings.retrieval_rrf_top_k, "检索"),
            ("retrieval_rerank_top_k", settings.retrieval_rerank_top_k, "检索"),
            ("retrieval_final_top_k", settings.retrieval_final_top_k, "检索"),
            ("tika_enabled", settings.tika_enabled, "本地服务"),
            ("tika_endpoint", settings.tika_endpoint, "本地服务"),
            ("tika_ocr_enabled", settings.tika_ocr_enabled, "本地服务"),
            ("tika_ocr_service_endpoint", settings.tika_ocr_service_endpoint, "本地服务"),
            ("langsmith_tracing", settings.langsmith_tracing, "观测"),
            ("langsmith_project", settings.langsmith_project, "观测"),
            ("auth_enabled", settings.auth_enabled, "认证"),
            ("auth_access_token_ttl_hours", settings.auth_access_token_ttl_hours, "认证"),
        ]
        return AdminSettingListResponse(
            items=[AdminSettingItem(key=key, value=str(value), category=category) for key, value, category in raw_items]
        )

    @staticmethod
    def _to_user(row) -> AdminUserItem:
        return AdminUserItem(
            id=str(row["id"]),
            username=str(row["username"]),
            role=str(row["role"]),
            created_at=RetriFlowAdminService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _to_trace_message(row, preview_limit: int = 160) -> AdminTraceMessageItem:
        content = str(row["content"])
        preview = content if len(content) <= preview_limit else f"{content[:preview_limit]}..."
        return AdminTraceMessageItem(
            id=int(row["id"]),
            role=str(row["role"]),
            content_preview=preview,
            created_at=RetriFlowAdminService._serialize_timestamp(row["created_at"]),
            duration_ms=int(row.get("duration_ms", 0) or 0),
        )

    @staticmethod
    def _to_intent_node(row) -> AdminIntentNodeItem:
        return AdminIntentNodeItem(
            id=str(row["id"]),
            name=str(row["name"]),
            code=str(row["code"]),
            level=str(row["level"]),
            node_type=str(row["node_type"]),
            parent_id=str(row["parent_id"]),
            knowledge_base_id=str(row["knowledge_base_id"] or ""),
            collection_name=str(row["collection_name"] or ""),
            description=str(row["description"] or ""),
            sample_questions=RetriFlowAdminService._loads_json_list(row["sample_questions_json"]),
            rule_snippet=str(row["rule_snippet"] or ""),
            prompt_template=str(row["prompt_template"] or ""),
            top_k=row["top_k"],
            sort_order=int(row["sort_order"] or 0),
            enabled=bool(row["enabled"]),
            created_at=RetriFlowAdminService._serialize_timestamp(row["created_at"]),
            updated_at=RetriFlowAdminService._serialize_timestamp(row["updated_at"]),
        )

    @staticmethod
    def _to_keyword_mapping(row) -> AdminKeywordMappingItem:
        return AdminKeywordMappingItem(
            id=str(row["id"]),
            raw_keyword=str(row["raw_keyword"]),
            target_keyword=str(row["target_keyword"]),
            match_type=str(row["match_type"] or "exact"),
            priority=int(row["priority"] or 0),
            enabled=bool(row["enabled"]),
            remark=str(row["remark"] or ""),
            knowledge_base_id=str(row["knowledge_base_id"] or ""),
            created_at=RetriFlowAdminService._serialize_timestamp(row["created_at"]),
            updated_at=RetriFlowAdminService._serialize_timestamp(row["updated_at"]),
        )

    @staticmethod
    def _resolve_dashboard_range(range_key: str) -> tuple[str, int, str, int]:
        ranges = {
            "24h": ("24h", 24, "近 24 小时", 12),
            "7d": ("7d", 24 * 7, "近 7 天", 7),
            "30d": ("30d", 24 * 30, "近 30 天", 30),
        }
        return ranges.get(range_key, ranges["24h"])

    def _build_dashboard_series(
        self,
        message_rows,
        ingestion_rows,
        buckets: list[datetime],
    ) -> tuple[AdminDashboardTrafficOverview, list[AdminDashboardTrendPanel]]:
        if len(buckets) < 2:
            buckets = [datetime.now(timezone.utc) - timedelta(hours=1), datetime.now(timezone.utc)]

        bucket_models = [
            {
                "start": buckets[index],
                "end": buckets[index + 1],
                "label": self._format_bucket_label(buckets[index], len(buckets) - 1),
                "sessions": set(),
                "users": set(),
                "messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "response_durations": [],
                "no_answers": 0,
                "slow_responses": 0,
                "tasks": 0,
                "failed_tasks": 0,
            }
            for index in range(len(buckets) - 1)
        ]

        pending_user_at: dict[str, datetime] = {}
        pending_user_bucket: dict[str, int] = {}

        for row in message_rows:
            timestamp = self._parse_timestamp(row["created_at"])
            if timestamp is None:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            bucket_index = self._locate_bucket(bucket_models, timestamp)
            if bucket_index is None:
                continue

            session_id = str(row["session_id"])
            role = str(row["role"])
            owner_label = str(row.get("owner_label", "")).strip()
            bucket = bucket_models[bucket_index]
            bucket["sessions"].add(session_id)
            if owner_label:
                bucket["users"].add(owner_label)
            bucket["messages"] += 1
            if role == "user":
                bucket["user_messages"] += 1
                pending_user_at[session_id] = timestamp
                pending_user_bucket[session_id] = bucket_index
            if role == "assistant":
                bucket["assistant_messages"] += 1
                if RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER in str(row.get("content", "")):
                    bucket["no_answers"] += 1
                duration_ms = int(row.get("duration_ms", 0) or 0)
                if duration_ms <= 0 and session_id in pending_user_at:
                    duration_ms = max(
                        0,
                        int((timestamp - pending_user_at[session_id]).total_seconds() * 1000),
                    )
                if duration_ms > 0 or session_id in pending_user_at:
                    response_bucket_index = pending_user_bucket.get(session_id, bucket_index)
                    response_bucket = bucket_models[response_bucket_index]
                    response_bucket["response_durations"].append(duration_ms)
                    if duration_ms > 20_000:
                        response_bucket["slow_responses"] += 1

        for row in ingestion_rows:
            timestamp = self._parse_timestamp(row["created_at"])
            if timestamp is None:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            bucket_index = self._locate_bucket(bucket_models, timestamp)
            if bucket_index is None:
                continue
            bucket = bucket_models[bucket_index]
            bucket["tasks"] += 1
            if str(row["status"]).lower() in {"failed", "error"}:
                bucket["failed_tasks"] += 1

        labels = [bucket["label"] for bucket in bucket_models]
        sessions_values = [float(len(bucket["sessions"])) for bucket in bucket_models]
        active_users_values = [float(len(bucket["users"])) for bucket in bucket_models]
        messages_values = [float(bucket["messages"]) for bucket in bucket_models]
        avg_response_values = [
            float(int(mean(bucket["response_durations"])) if bucket["response_durations"] else 0)
            for bucket in bucket_models
        ]
        error_rate_values = [
            round((bucket["failed_tasks"] / max(bucket["tasks"], 1)) * 100, 1) if bucket["tasks"] else 0.0
            for bucket in bucket_models
        ]
        no_answer_rate_values = [
            round((bucket["no_answers"] / max(bucket["assistant_messages"], 1)) * 100, 1)
            if bucket["assistant_messages"]
            else 0.0
            for bucket in bucket_models
        ]
        slow_response_rate_values = [
            round((bucket["slow_responses"] / max(len(bucket["response_durations"]), 1)) * 100, 1)
            if bucket["response_durations"]
            else 0.0
            for bucket in bucket_models
        ]

        traffic_overview = AdminDashboardTrafficOverview(
            labels=labels,
            series=[
                AdminDashboardSeries(key="messages", label="消息量", color="#315efb", values=messages_values),
                AdminDashboardSeries(key="sessions", label="会话量", color="#00a87e", values=sessions_values),
                AdminDashboardSeries(key="active_users", label="活跃用户", color="#f59e0b", values=active_users_values),
            ],
            total_sessions=int(sum(sessions_values)),
            total_messages=int(sum(messages_values)),
            total_active_users=len({user for bucket in bucket_models for user in bucket["users"]}),
        )

        trend_panels = [
            AdminDashboardTrendPanel(
                key="sessions",
                label="会话趋势",
                unit="个",
                summary=f"峰值 {int(max(sessions_values or [0]))} 个会话",
                series=[AdminDashboardSeries(key="sessions", label="会话数", color="#00a87e", values=sessions_values)],
            ),
            AdminDashboardTrendPanel(
                key="active_users",
                label="活跃用户趋势",
                unit="人",
                summary=f"峰值 {int(max(active_users_values or [0]))} 位活跃用户",
                series=[AdminDashboardSeries(key="active_users", label="活跃用户", color="#315efb", values=active_users_values)],
            ),
            AdminDashboardTrendPanel(
                key="response_time",
                label="响应时间趋势",
                unit="ms",
                summary=f"P95 重点关注高峰时段",
                series=[AdminDashboardSeries(key="avg_response_ms", label="平均响应", color="#f59e0b", values=avg_response_values)],
            ),
            AdminDashboardTrendPanel(
                key="quality",
                label="质量趋势",
                unit="%",
                summary="同时观察失败率、未命中率、慢响应率",
                series=[
                    AdminDashboardSeries(key="error_rate", label="失败率", color="#ef4444", values=error_rate_values),
                    AdminDashboardSeries(key="no_answer_rate", label="未命中率", color="#8b5cf6", values=no_answer_rate_values),
                    AdminDashboardSeries(key="slow_response_rate", label="慢响应率", color="#f97316", values=slow_response_rate_values),
                ],
            ),
        ]
        return traffic_overview, trend_panels

    @staticmethod
    def _build_time_buckets(start_at: datetime, now: datetime, bucket_count: int) -> list[datetime]:
        total_seconds = max(1, int((now - start_at).total_seconds()))
        step_seconds = max(1, total_seconds // max(bucket_count, 1))
        buckets = [start_at + timedelta(seconds=step_seconds * index) for index in range(bucket_count)]
        buckets.append(now)
        return buckets

    @staticmethod
    def _locate_bucket(bucket_models: list[dict], timestamp: datetime) -> int | None:
        for index, bucket in enumerate(bucket_models):
            if bucket["start"] <= timestamp <= bucket["end"]:
                return index
        return None

    @staticmethod
    def _format_bucket_label(value: datetime, bucket_count: int) -> str:
        if bucket_count <= 7:
            return value.astimezone().strftime("%m-%d")
        if bucket_count <= 12:
            return value.astimezone().strftime("%H:%M")
        return value.astimezone().strftime("%m-%d")

    @staticmethod
    def _build_ops_insights(
        range_label: str,
        generated_at: datetime,
        active_user_count: int,
        active_session_count: int,
        window_message_count: int,
        avg_response_ms: int,
        p95_response_ms: int,
        indexed_rate: float,
        no_answer_rate: float,
        slow_response_rate: float,
        failed_tasks: int,
    ) -> list[AdminDashboardOpsInsight]:
        time_label = generated_at.astimezone().strftime("%m-%d %H:%M")
        insights: list[AdminDashboardOpsInsight] = []

        if window_message_count == 0:
            insights.append(
                AdminDashboardOpsInsight(
                    level="info",
                    category="流量",
                    title="当前时间窗暂无新增会话",
                    message=f"{range_label}内没有新的消息流入，建议结合首页示例问题或知识库调试入口做一次链路验证。",
                    time_label=time_label,
                )
            )
        else:
            insights.append(
                AdminDashboardOpsInsight(
                    level="success",
                    category="流量",
                    title="流量已形成稳定会话池",
                    message=f"{range_label}内累计 {window_message_count} 条消息，覆盖 {active_session_count} 个活跃会话和 {active_user_count} 位活跃用户。",
                    time_label=time_label,
                )
            )

        if p95_response_ms > 15_000 or slow_response_rate >= 20:
            insights.append(
                AdminDashboardOpsInsight(
                    level="warning",
                    category="性能",
                    title="高峰时段响应偏慢",
                    message=f"P95 响应约 {RetriFlowAdminService._format_duration(p95_response_ms)}，慢响应率 {slow_response_rate}%。建议优先检查重排模型、向量检索 TopK 和外部模型服务。",
                    time_label=time_label,
                )
            )
        elif avg_response_ms > 0:
            insights.append(
                AdminDashboardOpsInsight(
                    level="success",
                    category="性能",
                    title="响应时间处于可接受区间",
                    message=f"平均响应约 {RetriFlowAdminService._format_duration(avg_response_ms)}，当前链路延迟整体稳定。",
                    time_label=time_label,
                )
            )

        if no_answer_rate >= 15:
            insights.append(
                AdminDashboardOpsInsight(
                    level="warning",
                    category="质量",
                    title="知识命中率需要关注",
                    message=f"当前未命中率 {no_answer_rate}%。建议检查知识库覆盖、意图路由和查询改写质量，补齐高频问法样本。",
                    time_label=time_label,
                )
            )
        elif indexed_rate >= 85:
            insights.append(
                AdminDashboardOpsInsight(
                    level="success",
                    category="质量",
                    title="知识索引基础健康",
                    message=f"索引完成率 {indexed_rate}%，知识库检索基础状态良好，可继续优化召回与重排。",
                    time_label=time_label,
                )
            )

        if failed_tasks > 0:
            insights.append(
                AdminDashboardOpsInsight(
                    level="danger",
                    category="运维",
                    title="存在失败的入库任务",
                    message=f"{range_label}内检测到 {failed_tasks} 个失败任务，建议进入流水线任务和链路追踪查看具体节点日志。",
                    time_label=time_label,
                )
            )

        return insights

    def _filter_rows_by_time(self, rows, start_at: datetime):
        filtered = []
        for row in rows:
            timestamp = self._parse_timestamp(row["created_at"])
            if timestamp is None:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp >= start_at:
                filtered.append(row)
        return filtered

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _count(connection, table_name: str) -> int:
        return int(connection.execute(f"select count(*) from {table_name}").fetchone()[0] or 0)

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is required")
        return normalized

    @staticmethod
    def _loads_json_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []

    @staticmethod
    def _parse_timestamp(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            try:
                return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

    def _get_intent_node_row(self, connection, node_id: str):
        return connection.execute("select * from admin_intent_nodes where id = ?", (node_id,)).fetchone()

    def _get_keyword_mapping_row(self, connection, mapping_id: str):
        return connection.execute("select * from admin_keyword_mappings where id = ?", (mapping_id,)).fetchone()

    def _session_duration_ms(self, connection, session_id: str) -> int:
        duration_row = connection.execute(
            """
            select coalesce(sum(duration_ms), 0) as duration_ms
            from conversation_messages
            where session_id = ?
            """,
            (session_id,),
        ).fetchone()
        duration_ms = int(duration_row["duration_ms"] or 0) if duration_row is not None else 0
        if duration_ms > 0:
            return duration_ms

        rows = connection.execute(
            "select created_at from conversation_messages where session_id = ? order by id asc",
            (session_id,),
        ).fetchall()
        return self._duration_between_rows(rows)

    def _duration_between_rows(self, rows) -> int:
        timestamps = [self._parse_timestamp(row["created_at"]) for row in rows]
        timestamps = [item for item in timestamps if item is not None]
        if len(timestamps) < 2:
            return 0
        return max(0, int((max(timestamps) - min(timestamps)).total_seconds() * 1000))

    def _estimate_response_durations(self, rows) -> list[int]:
        durations: list[int] = []
        last_user_at_by_session: dict[str, datetime] = {}
        for row in rows:
            session_id = str(row["session_id"])
            timestamp = self._parse_timestamp(row["created_at"])
            if timestamp is None:
                continue
            if str(row["role"]) == "user":
                last_user_at_by_session[session_id] = timestamp
                continue
            if str(row["role"]) == "assistant" and session_id in last_user_at_by_session:
                duration_ms = int(row.get("duration_ms", 0) or 0)
                if duration_ms <= 0:
                    duration_ms = max(0, int((timestamp - last_user_at_by_session[session_id]).total_seconds() * 1000))
                durations.append(duration_ms)
        return durations

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int:
        if not values:
            return 0
        sorted_values = sorted(values)
        index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * percentile))))
        return sorted_values[index]

    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        if duration_ms >= 1000:
            return f"{duration_ms / 1000:.1f}s"
        return f"{duration_ms}ms"
