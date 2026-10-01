"""周学习路径规划：在预算内选出岗位缺口改善最大的合法活动序列。"""
from __future__ import annotations

from functools import lru_cache

from .models import (
    Activity,
    LearnerSnapshot,
    LearningPlan,
    RoleProfile,
    SkillCatalog,
)

DEFAULT_WEEKLY_BUDGET_MINUTES = 180


def plan_week(
    catalog: SkillCatalog,
    activities: list[Activity],
    snapshot: LearnerSnapshot,
    role: RoleProfile,
    budget_minutes: int = DEFAULT_WEEKLY_BUDGET_MINUTES,
) -> LearningPlan:
    """返回收益最大的合法学习计划；收益相同取总时长最短；无收益则返回空计划。"""
    prereq_map: dict[str, list[tuple[str, int]]] = {}
    for prereq in catalog.prerequisites:
        prereq_map.setdefault(prereq.skill, []).append(
            (prereq.requires_skill, prereq.requires_level)
        )

    # 只读快照，内部状态均为副本，绝不修改传入对象。
    base_levels = {skill: int(level) for skill, level in snapshot.levels.items()}
    candidates = [
        activity
        for activity in activities
        if activity.activity_id not in snapshot.completed_activity_ids
    ]
    role_targets = tuple(
        (target.skill, target.target_level, target.weight) for target in role.targets
    )

    def is_executable(levels: dict[str, int], activity: Activity) -> bool:
        improves_any = False
        for skill, declared in activity.targets:
            current = levels.get(skill, 0)
            if declared > current + 1:
                return False
            if declared > current:
                improves_any = True
        if not improves_any:
            return False
        # 前置阈值按活动开始前的等级判断，活动内部提升不能互相解锁。
        for skill, declared in activity.targets:
            if declared > levels.get(skill, 0):
                for requires_skill, requires_level in prereq_map.get(skill, ()):
                    if levels.get(requires_skill, 0) < requires_level:
                        return False
        return True

    def gap_reduction(before: dict[str, int], after: dict[str, int]) -> int:
        total = 0
        for skill, target_level, weight in role_targets:
            gap_before = max(0, target_level - before.get(skill, 0))
            gap_after = max(0, target_level - after.get(skill, 0))
            total += weight * (gap_before - gap_after)
        return total

    count = len(candidates)

    @lru_cache(maxsize=None)
    def best_from(mask: int) -> tuple[int, int, tuple[str, ...]]:
        """从已选集合 mask 出发的最优（收益, 时长, 活动序列）。等级与耗时由 mask 唯一确定。"""
        levels = dict(base_levels)
        used_minutes = 0
        for index in range(count):
            if mask >> index & 1:
                chosen = candidates[index]
                used_minutes += chosen.duration_minutes
                for skill, declared in chosen.targets:
                    if declared > levels.get(skill, 0):
                        levels[skill] = declared

        best_gain, best_minutes, best_sequence = 0, 0, ()
        for index in range(count):
            if mask >> index & 1:
                continue
            activity = candidates[index]
            if used_minutes + activity.duration_minutes > budget_minutes:
                continue
            if not is_executable(levels, activity):
                continue
            after = dict(levels)
            for skill, declared in activity.targets:
                if declared > after.get(skill, 0):
                    after[skill] = declared
            sub_gain, sub_minutes, sub_sequence = best_from(mask | (1 << index))
            total_gain = gap_reduction(levels, after) + sub_gain
            total_minutes = activity.duration_minutes + sub_minutes
            if (total_gain, -total_minutes) > (best_gain, -best_minutes):
                best_gain = total_gain
                best_minutes = total_minutes
                best_sequence = (activity.activity_id,) + sub_sequence
        return best_gain, best_minutes, best_sequence

    gain, minutes, sequence = best_from(0)
    if gain <= 0:
        return LearningPlan()
    return LearningPlan(activity_ids=sequence, total_minutes=minutes, total_gain=gain)
