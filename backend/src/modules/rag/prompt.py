from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from threading import RLock
from typing import Mapping

from schemas.chat import ChatSourceItem


_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_SECTION_HEADER = re.compile(r"^---\s*section:\s*(\S+)\s*---$", re.MULTILINE)


class PromptTemplateUtils:
    @staticmethod
    def cleanup_prompt(prompt: str | None) -> str:
        if prompt is None:
            return ""
        return _MULTI_BLANK_LINES.sub("\n\n", prompt).strip()

    @staticmethod
    def fill_slots(template: str | None, slots: Mapping[str, object] | None = None) -> str:
        if template is None:
            return ""
        result = template
        for key, value in (slots or {}).items():
            result = result.replace("{" + key + "}", "" if value is None else str(value))
        return result

    @staticmethod
    def parse_sections(content: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        last_name: str | None = None
        last_start = -1
        for match in _SECTION_HEADER.finditer(content):
            if last_name is not None:
                sections[last_name] = content[last_start:match.start()].lstrip("\n").rstrip()
            last_name = match.group(1)
            last_start = match.end()
        if last_name is not None:
            sections[last_name] = content[last_start:].lstrip("\n").rstrip()
        return sections


class PromptTemplateLoader:
    def __init__(self, template_root: Path | None = None) -> None:
        self.template_root = template_root or Path(__file__).resolve().parent / "prompts"
        self._cache: dict[str, str] = {}
        self._section_cache: dict[str, dict[str, str]] = {}
        self._lock = RLock()

    def load(self, path: str) -> str:
        normalized = self._normalize_path(path)
        with self._lock:
            if normalized not in self._cache:
                self._cache[normalized] = (self.template_root / normalized).read_text(encoding="utf-8")
            return self._cache[normalized]

    def render(self, path: str, slots: Mapping[str, object] | None = None) -> str:
        template = self.load(path)
        return PromptTemplateUtils.cleanup_prompt(PromptTemplateUtils.fill_slots(template, slots))

    def load_section(self, path: str, section: str) -> str:
        normalized = self._normalize_path(path)
        with self._lock:
            if normalized not in self._section_cache:
                self._section_cache[normalized] = PromptTemplateUtils.parse_sections(self.load(normalized))
            template = self._section_cache[normalized].get(section)
        if template is None:
            raise KeyError(f"prompt section not found: {normalized} -> {section}")
        return template

    def render_section(self, path: str, section: str, slots: Mapping[str, object] | None = None) -> str:
        template = self.load_section(path, section)
        return PromptTemplateUtils.cleanup_prompt(PromptTemplateUtils.fill_slots(template, slots))

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = path.strip().removeprefix("classpath:").lstrip("/\\")
        if not normalized or ".." in Path(normalized).parts:
            raise ValueError("invalid prompt template path")
        return normalized.replace("\\", "/")


class PromptScene(str, Enum):
    KB_ONLY = "kb_only"
    MCP_ONLY = "mcp_only"
    MIXED = "mixed"
    EMPTY = "empty"


@dataclass(frozen=True)
class PromptBuildPlan:
    scene: PromptScene
    base_template: str
    mcp_context: str
    kb_context: str
    question: str


class RAGPromptService:
    NO_ANSWER_REPLY = "无法从知识库中找到答案"

    def __init__(self, loader: PromptTemplateLoader | None = None, no_answer_reply: str | None = None) -> None:
        self.loader = loader or get_prompt_template_loader()
        self.no_answer_reply = no_answer_reply or self.NO_ANSWER_REPLY

    def plan(
        self,
        *,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
    ) -> PromptBuildPlan:
        kb_context = self.build_retrieved_context(sources)
        mcp_context = extra_context.strip()
        has_sources = bool(sources)
        has_mcp_context = bool(mcp_context)
        if has_sources and has_mcp_context:
            scene = PromptScene.MIXED
        elif has_sources:
            scene = PromptScene.KB_ONLY
        elif has_mcp_context:
            scene = PromptScene.MCP_ONLY
        else:
            scene = PromptScene.EMPTY
        return PromptBuildPlan(
            scene=scene,
            base_template=self.build_system_prompt(),
            mcp_context=mcp_context,
            kb_context=kb_context,
            question=question,
        )

    def build_messages(
        self,
        *,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": self.build_user_prompt(question, sources, extra_context)},
        ]

    def build_system_prompt(self) -> str:
        return self.loader.render(
            "answer.md",
            {"no_answer_reply": self.no_answer_reply},
        )

    def build_user_prompt(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str = "",
    ) -> str:
        sections = [
            self.loader.render_section(
                "context.md",
                "retrieved-context",
                {"body": self.build_retrieved_context(sources)},
            )
        ]
        if extra_context.strip():
            sections.append(
                self.loader.render_section(
                    "context.md",
                    "tool-context",
                    {"body": extra_context.strip()},
                )
            )
        sections.append(
            self.loader.render_section(
                "context.md",
                "user-question",
                {"question": question},
            )
        )
        return "\n\n".join(section for section in sections if section.strip()).strip()

    def build_retrieved_context(self, sources: list[ChatSourceItem]) -> str:
        if not sources:
            return self.loader.render_section("context.md", "no-sources")

        blocks: list[str] = []
        for index, source in enumerate(sources[:5], start=1):
            updated_line = f"更新时间：{source.source_updated_at}" if source.source_updated_at else ""
            blocks.append(
                self.loader.render_section(
                    "context.md",
                    "single-source",
                    {
                        "index": index,
                        "document_title": source.document_title,
                        "updated_line": updated_line,
                        "knowledge_base_id": source.knowledge_base_id,
                        "content": source.content,
                    },
                )
            )
        return "\n\n".join(blocks)


_DEFAULT_LOADER = PromptTemplateLoader()


def get_prompt_template_loader() -> PromptTemplateLoader:
    return _DEFAULT_LOADER
