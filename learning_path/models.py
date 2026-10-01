"""数据模型：技能目录、活动、学员快照、岗位画像与学习计划。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prerequisite:
    """一条前置关系：学习 skill 前，requires_skill 必须达到 requires_level。"""

    skill: str
    requires_skill: str
    requires_level: int


@dataclass(frozen=True)
class SkillCatalog:
    """技能目录：技能集合与前置关系（有向无环图）。"""

    skills: frozenset[str] = frozenset()
    prerequisites: tuple[Prerequisite, ...] = ()


@dataclass(frozen=True)
class Activity:
    """候选学习活动：正整数分钟时长 + 声明的技能目标等级。"""

    activity_id: str
    duration_minutes: int
    targets: tuple[tuple[str, int], ...]  # (skill, declared_level)


@dataclass(frozen=True)
class LearnerSnapshot:
    """学员快照：当前熟练度（0-5）与已完成活动。调用方传入，不会被修改。"""

    levels: dict[str, int] = field(default_factory=dict)
    completed_activity_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoleTarget:
    """岗位对某技能的要求：目标等级与业务权重（1-10）。"""

    skill: str
    target_level: int
    weight: int


@dataclass(frozen=True)
class RoleProfile:
    """岗位画像。"""

    targets: tuple[RoleTarget, ...] = ()


@dataclass(frozen=True)
class LearningPlan:
    """学习计划：按顺序执行的活动、总时长与总收益。"""

    activity_ids: tuple[str, ...] = ()
    total_minutes: int = 0
    total_gain: int = 0
