import re
from datetime import datetime

from schemas.chat import ChatSourceItem


class RetriFlowAnswerPostprocessor:
    DEFAULT_NO_ANSWER = "根据现有资料，暂时无法回答该问题。建议您联系人工客服获取更多帮助。"

    def finalize(self, answer: str, sources: list[ChatSourceItem]) -> str:
        normalized = self._normalize(answer)
        safe_answer = self._apply_safety_filter(normalized)

        if not safe_answer.strip():
            safe_answer = self.DEFAULT_NO_ANSWER

        if sources and not self._contains_any_citation(safe_answer):
            safe_answer = safe_answer.rstrip("。 \n") + "。[1]"

        sections = [safe_answer]

        conflict_notice = self._build_conflict_notice(sources)
        if conflict_notice:
            sections.append(conflict_notice)

        if sources:
            sections.append(f"## 参考来源\n{self._build_reference_section(sources)}")

        return "\n\n".join(section for section in sections if section.strip())

    @staticmethod
    def _normalize(answer: str) -> str:
        return answer.replace("\r\n", "\n").strip()

    def _apply_safety_filter(self, answer: str) -> str:
        blocked_patterns = [
            r"(?i)制作炸弹",
            r"(?i)绕过支付",
            r"(?i)窃取密码",
        ]
        for pattern in blocked_patterns:
            if re.search(pattern, answer):
                return self.DEFAULT_NO_ANSWER
        return answer

    @staticmethod
    def _contains_any_citation(answer: str) -> bool:
        return bool(re.search(r"\[\d+\]", answer))

    def _build_conflict_notice(self, sources: list[ChatSourceItem]) -> str:
        conflict_pairs = self._detect_conflicts(sources)
        if not conflict_pairs:
            return ""

        latest_index = self._find_latest_source_index(sources)
        latest_hint = ""
        if latest_index is not None:
            latest_hint = f"\n优先参考较新的资料 [{latest_index + 1}]。"

        lines = ["## 冲突提示"]
        for left_index, right_index in conflict_pairs:
            lines.append(
                f"资料 [{left_index + 1}]《{sources[left_index].document_title}》"
                f" 与资料 [{right_index + 1}]《{sources[right_index].document_title}》存在信息冲突。"
            )
        if latest_hint:
            lines.append(latest_hint.strip())
        return "\n".join(lines)

    def _detect_conflicts(self, sources: list[ChatSourceItem]) -> list[tuple[int, int]]:
        conflict_pairs: list[tuple[int, int]] = []
        normalized_contents = [self._normalize_conflict_text(source.content) for source in sources]
        for left_index in range(len(sources)):
            for right_index in range(left_index + 1, len(sources)):
                left_text = normalized_contents[left_index]
                right_text = normalized_contents[right_index]
                if not left_text or not right_text:
                    continue
                if "支持" in left_text and "不支持" in right_text:
                    conflict_pairs.append((left_index, right_index))
                    continue
                if "不支持" in left_text and "支持" in right_text:
                    conflict_pairs.append((left_index, right_index))
                    continue
                if "可申请" in left_text and "不支持" in right_text:
                    conflict_pairs.append((left_index, right_index))
                    continue
                if "不支持" in left_text and "可申请" in right_text:
                    conflict_pairs.append((left_index, right_index))
        return conflict_pairs

    @staticmethod
    def _normalize_conflict_text(text: str) -> str:
        return re.sub(r"\s+", "", text.lower())

    @staticmethod
    def _find_latest_source_index(sources: list[ChatSourceItem]) -> int | None:
        parsed_dates: list[tuple[int, datetime]] = []
        for index, source in enumerate(sources):
            parsed = RetriFlowAnswerPostprocessor._parse_datetime(source.source_updated_at)
            if parsed is not None:
                parsed_dates.append((index, parsed))
        if not parsed_dates:
            return None
        parsed_dates.sort(key=lambda item: item[1], reverse=True)
        return parsed_dates[0][0]

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _build_reference_section(sources: list[ChatSourceItem]) -> str:
        lines: list[str] = []
        for index, source in enumerate(sources, start=1):
            lines.append(f"[{index}] {source.document_title}")
            if source.source_updated_at:
                lines.append(f"更新时间：{source.source_updated_at}")
            if source.source_link:
                lines.append(f"链接：{source.source_link}")
        return "\n".join(lines)
