"""数据类型定义：技能目录、岗位、活动、学员快照与学习计划。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

MIN_LEVEL = 0
MAX_LEVEL = 5


def _check_level(value: int, what: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{what} 必须是整数，得到 {value!r}")
    if not MIN_LEVEL <= value <= MAX_LEVEL:
        raise ValueError(f"{what} 必须在 {MIN_LEVEL}..{MAX_LEVEL} 之间，得到 {value}")


@dataclass(frozen=True)
class Prerequisite:
    """一条前置关系：学习某技能前，前置技能必须达到的等级。"""

    skill: str
    required_level: int

    def __post_init__(self) -> None:
        _check_level(self.required_level, f"前置等级({self.skill})")
        if self.required_level == MIN_LEVEL:
            raise ValueError(f"前置等级({self.skill})必须大于 0")


@dataclass(frozen=True)
class Skill:
    """技能目录中的一个技能及其直接前置条件。"""

    name: str
    prerequisites: tuple[Prerequisite, ...] = ()


@dataclass(frozen=True)
class SkillCatalog:
    """技能目录：技能名 -> 技能定义。前置关系整体必须构成有向无环图。"""

    skills: Mapping[str, Skill] = field(default_factory=dict)

    def __post_init__(self) -> None:
        skills = dict(self.skills)
        for name, skill in skills.items():
            if skill.name != name:
                raise ValueError(f"目录键 {name!r} 与技能名 {skill.name!r} 不一致")
            for prereq in skill.prerequisites:
                if prereq.skill not in skills:
                    raise ValueError(
                        f"技能 {name!r} 的前置 {prereq.skill!r} 不在目录中"
                    )
        _check_acyclic(skills)
        object.__setattr__(self, "skills", MappingProxyType(skills))


def _check_acyclic(skills: Mapping[str, Skill]) -> None:
    """用三色标记做 DFS，发现环则抛 ValueError。"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in skills}

    def visit(name: str, path: tuple[str, ...]) -> None:
        color[name] = GRAY
        for prereq in skills[name].prerequisites:
            if color[prereq.skill] == GRAY:
                cycle = " -> ".join((*path, name, prereq.skill))
                raise ValueError(f"前置关系存在环: {cycle}")
            if color[prereq.skill] == WHITE:
                visit(prereq.skill, (*path, name))
        color[name] = BLACK

    for name in skills:
        if color[name] == WHITE:
            visit(name, ())


@dataclass(frozen=True)
class RoleTarget:
    """岗位对某技能的要求：目标等级与业务权重。"""

    skill: str
    target_level: int
    weight: int

    def __post_init__(self) -> None:
        _check_level(self.target_level, f"岗位目标等级({self.skill})")
        if not 1 <= self.weight <= 10:
            raise ValueError(
                f"业务权重({self.skill})必须在 1..10 之间，得到 {self.weight}"
            )


@dataclass(frozen=True)
class RoleProfile:
    """岗位画像：只覆盖部分技能，未列入的技能不直接得分。"""

    targets: tuple[RoleTarget, ...] = ()


@dataclass(frozen=True)
class Activity:
    """候选学习活动：正整数分钟时长 + 一个或多个技能的目标等级。"""

    activity_id: str
    duration_minutes: int
    target_levels: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.duration_minutes, int) or isinstance(
            self.duration_minutes, bool
        ):
            raise TypeError("活动时长必须是整数分钟")
        if self.duration_minutes <= 0:
            raise ValueError("活动时长必须是正整数分钟")
        if not self.target_levels:
            raise ValueError(f"活动 {self.activity_id!r} 至少声明一个技能目标等级")
        for skill, level in self.target_levels.items():
            _check_level(level, f"活动 {self.activity_id!r} 的目标等级({skill})")
        object.__setattr__(
            self, "target_levels", MappingProxyType(dict(self.target_levels))
        )


@dataclass(frozen=True)
class LearnerSnapshot:
    """学员快照：当前各技能等级与已完成的活动。视为可信，不追溯来源。"""

    levels: Mapping[str, int] = field(default_factory=dict)
    completed_activity_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for skill, level in self.levels.items():
            _check_level(level, f"学员等级({skill})")
        object.__setattr__(self, "levels", MappingProxyType(dict(self.levels)))
        object.__setattr__(
            self, "completed_activity_ids", frozenset(self.completed_activity_ids)
        )


@dataclass(frozen=True)
class PlannedActivity:
    """计划中的一个活动及其完成后的技能等级快照。"""

    activity: Activity
    resulting_levels: Mapping[str, int]


@dataclass(frozen=True)
class LearningPlan:
    """学习计划：按顺序执行的活动列表、总时长与岗位缺口改善收益。"""

    activities: tuple[PlannedActivity, ...] = ()
    total_minutes: int = 0
    benefit: int = 0
