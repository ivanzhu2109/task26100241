"""每周学习路径规划：在全部合法活动序列中搜索收益最大的计划。"""

from __future__ import annotations

from typing import Mapping, Sequence

from .models import (
    Activity,
    LearnerSnapshot,
    LearningPlan,
    PlannedActivity,
    RoleProfile,
    SkillCatalog,
)

DEFAULT_WEEKLY_BUDGET_MINUTES = 180


class _Search:
    """以 (等级向量, 已用活动集合) 为状态的记忆化搜索。

    状态唯一确定已耗时（已用活动时长之和固定），因此可以作为缓存键。
    收益用岗位得分表示：sum(weight * min(当前等级, 目标等级))，
    最终收益 = 末态得分 - 初态得分，与缺口减少量等价。
    """

    def __init__(
        self,
        catalog: SkillCatalog,
        activities: Sequence[Activity],
        snapshot: LearnerSnapshot,
        role: RoleProfile,
        budget_minutes: int,
    ) -> None:
        skill_names = set(catalog.skills) | set(snapshot.levels)
        for activity in activities:
            skill_names.update(activity.target_levels)
        targets: dict[str, tuple[int, int]] = {}
        for target in role.targets:
            if target.skill in targets:
                raise ValueError(f"岗位技能 {target.skill!r} 的目标重复定义")
            targets[target.skill] = (target.target_level, target.weight)
        skill_names.update(targets)

        self.skills = tuple(sorted(skill_names))
        self.index = {name: pos for pos, name in enumerate(self.skills)}
        self.initial = tuple(snapshot.levels.get(name, 0) for name in self.skills)
        self.target_level = tuple(
            targets.get(name, (0, 0))[0] for name in self.skills
        )
        self.weight = tuple(targets.get(name, (0, 0))[1] for name in self.skills)
        self.prereqs = tuple(
            tuple(
                (self.index[p.skill], p.required_level)
                for p in catalog.skills[name].prerequisites
            )
            if name in catalog.skills
            else ()
            for name in self.skills
        )

        self.activities = tuple(activities)
        self.duration = tuple(a.duration_minutes for a in activities)
        self.budget = budget_minutes
        self.memo: dict[
            tuple[tuple[int, ...], int], tuple[int, int, tuple[int, ...]]
        ] = {}

    def score(self, levels: tuple[int, ...]) -> int:
        return sum(
            weight * min(level, target)
            for level, target, weight in zip(
                levels, self.target_level, self.weight
            )
        )

    def spent(self, mask: int) -> int:
        total = 0
        bit = 0
        while mask:
            if mask & 1:
                total += self.duration[bit]
            mask >>= 1
            bit += 1
        return total

    def feasible(
        self, activity: Activity, levels: tuple[int, ...]
    ) -> tuple[int, ...] | None:
        """检查活动能否在当前等级下开始，可行则返回完成后的等级向量。"""
        new_levels = list(levels)
        improves = False
        for skill, declared in activity.target_levels.items():
            pos = self.index[skill]
            current = levels[pos]
            if declared > current + 1:
                return None
            if declared > current:
                improves = True
                new_levels[pos] = declared
        if not improves:
            return None
        # 前置阈值必须在活动开始前满足；同活动内的提升不能互相解锁，
        # 因此一律用开始前的 levels 检查。
        for skill, declared in activity.target_levels.items():
            pos = self.index[skill]
            if declared > levels[pos]:
                for prereq_pos, required in self.prereqs[pos]:
                    if levels[prereq_pos] < required:
                        return None
        return tuple(new_levels)

    def best_from(
        self, levels: tuple[int, ...], mask: int
    ) -> tuple[int, int, tuple[int, ...]]:
        """返回从该状态出发的最优 (得分, 总时长, 活动序号序列)。"""
        key = (levels, mask)
        if key in self.memo:
            return self.memo[key]
        remaining = self.budget - self.spent(mask)
        best = (self.score(levels), 0, ())
        for pos, activity in enumerate(self.activities):
            if mask >> pos & 1 or self.duration[pos] > remaining:
                continue
            new_levels = self.feasible(activity, levels)
            if new_levels is None:
                continue
            score, minutes, seq = self.best_from(new_levels, mask | (1 << pos))
            candidate = (score, minutes + self.duration[pos], (pos, *seq))
            if (candidate[0], -candidate[1]) > (best[0], -best[1]):
                best = candidate
        self.memo[key] = best
        return best


def plan_week(
    catalog: SkillCatalog,
    activities: Sequence[Activity],
    snapshot: LearnerSnapshot,
    role: RoleProfile,
    budget_minutes: int = DEFAULT_WEEKLY_BUDGET_MINUTES,
) -> LearningPlan:
    """返回本周内可顺序完成、岗位缺口改善最大的学习计划。

    只读取传入的 snapshot，不会修改它；计算数据仅存内存。
    收益相同取总时长最短；没有任何有收益的合法计划时返回空计划。
    """
    if budget_minutes <= 0:
        raise ValueError("周预算必须是正整数分钟")
    candidates = tuple(
        activity
        for activity in activities
        if activity.activity_id not in snapshot.completed_activity_ids
    )
    search = _Search(catalog, candidates, snapshot, role, budget_minutes)
    final_score, _, sequence = search.best_from(search.initial, 0)
    benefit = final_score - search.score(search.initial)
    if benefit <= 0 or not sequence:
        return LearningPlan()

    planned: list[PlannedActivity] = []
    levels = search.initial
    total = 0
    for pos in sequence:
        activity = search.activities[pos]
        new_levels = search.feasible(activity, levels)
        assert new_levels is not None
        levels = new_levels
        total += activity.duration_minutes
        levels_after: Mapping[str, int] = dict(zip(search.skills, levels))
        planned.append(
            PlannedActivity(activity=activity, resulting_levels=levels_after)
        )
    return LearningPlan(
        activities=tuple(planned), total_minutes=total, benefit=benefit
    )
