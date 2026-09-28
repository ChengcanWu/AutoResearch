# -*- coding: utf-8 -*-
"""核心数据契约（对应 docs/ARCHITECTURE.md §接口冻结）。

W0 demo 说明：
- Fact / NBA / MicroTask / Submission / Feedback 五个 schema 与正式契约一致；
- LLM 环节（onboarding 抽取、planner 决策、任务反馈）按 NEXT_PRE §3 白名单 mock，
  但数据结构与闭环逻辑是真实的。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid4().hex


FactCategory = Literal["background", "interest", "capability", "preference", "experience"]
FactSource = Literal["declared", "inferred", "behavior"]
FactStatus = Literal["draft", "confirmed", "active", "dismissed", "deleted"]


class UserFact:
    """用户模型的最小单元：一条有证据、可解释的事实。"""

    def __init__(
        self,
        *,
        id: str | None = None,
        user_id: str = "",
        category: FactCategory = "interest",
        key: str = "",
        value: str = "",
        confidence: float = 0.6,
        source: FactSource = "declared",
        evidence: list[dict[str, Any]] | None = None,
        status: FactStatus = "draft",
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        self.id = id or new_id()
        self.user_id = user_id
        self.category = category
        self.key = key
        self.value = value
        self.confidence = round(float(confidence), 2)
        self.source = source
        self.evidence = evidence or []
        self.status = status
        self.created_at = created_at or now_iso()
        self.updated_at = updated_at or self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "evidence": self.evidence,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserFact":
        return cls(
            id=d.get("id"),
            user_id=d.get("user_id", ""),
            category=d.get("category", "interest"),
            key=d.get("key", ""),
            value=d.get("value", ""),
            confidence=d.get("confidence", 0.6),
            source=d.get("source", "declared"),
            evidence=d.get("evidence") or [],
            status=d.get("status", "draft"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


class NBA:
    """Next Best Action：一次行动建议，rationale 必须引用事实。"""

    def __init__(
        self,
        *,
        action: str,
        title: str,
        rationale: str,
        rationale_facts: list[str] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.action = action  # explore_direction | micro_task | review_progress
        self.title = title
        self.rationale = rationale
        self.rationale_facts = rationale_facts or []  # 引用的 fact id
        self.alternatives = alternatives or []
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "title": self.title,
            "rationale": self.rationale,
            "rationale_facts": self.rationale_facts,
            "alternatives": self.alternatives,
            "payload": self.payload,
        }


class MicroTask:
    """微任务：10–30 分钟、带步骤与评分标准的真实小任务。"""

    def __init__(
        self,
        *,
        id: str | None = None,
        user_id: str = "",
        direction: str = "",
        title: str = "",
        brief: str = "",
        steps: list[str] | None = None,
        rubric: list[dict[str, str]] | None = None,
        time_budget_min: int = 20,
        difficulty: int = 1,
        status: str = "open",  # open | submitted | done
        created_at: str | None = None,
    ) -> None:
        self.id = id or new_id()
        self.user_id = user_id
        self.direction = direction
        self.title = title
        self.brief = brief
        self.steps = steps or []
        self.rubric = rubric or []
        self.time_budget_min = time_budget_min
        self.difficulty = difficulty
        self.status = status
        self.created_at = created_at or now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "direction": self.direction,
            "title": self.title,
            "brief": self.brief,
            "steps": self.steps,
            "rubric": self.rubric,
            "time_budget_min": self.time_budget_min,
            "difficulty": self.difficulty,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MicroTask":
        return cls(
            id=d.get("id"),
            user_id=d.get("user_id", ""),
            direction=d.get("direction", ""),
            title=d.get("title", ""),
            brief=d.get("brief", ""),
            steps=d.get("steps") or [],
            rubric=d.get("rubric") or [],
            time_budget_min=d.get("time_budget_min", 20),
            difficulty=d.get("difficulty", 1),
            status=d.get("status", "open"),
            created_at=d.get("created_at"),
        )


class Feedback:
    """任务反馈：rubric 逐条判定 + 下一步提示，不评价人格。"""

    def __init__(
        self,
        *,
        score: int,
        rubric: list[dict[str, Any]],
        next_hint: str,
        encouragement: str,
        learned_facts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.score = score  # 0-100
        self.rubric = rubric  # [{criterion, pass, comment}]
        self.next_hint = next_hint
        self.encouragement = encouragement
        self.learned_facts = learned_facts or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "rubric": self.rubric,
            "next_hint": self.next_hint,
            "encouragement": self.encouragement,
            "learned_facts": self.learned_facts,
        }
