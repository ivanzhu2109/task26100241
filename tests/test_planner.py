"""每周学习路径规划库的自动化测试。"""

import pytest

from learning_planner import (
    Activity,
    LearnerSnapshot,
    Prerequisite,
    RoleProfile,
    RoleTarget,
    Skill,
    SkillCatalog,
    plan_week,
)


def make_chain_fixture():
    """场景一：基础技能A解锁目标技能B，C为无前置的备选。"""
    catalog = SkillCatalog(
        {
            "A": Skill("A"),
            "B": Skill("B", (Prerequisite("A", 2),)),
            "C": Skill("C"),
        }
    )
    activities = [
        Activity("a1", 30, {"A": 1}),
        Activity("a2", 30, {"A": 2}),
        Activity("b1", 30, {"B": 1}),
        Activity("c1", 60, {"C": 1}),
    ]
    role = RoleProfile((RoleTarget("B", 1, 10), RoleTarget("C", 1, 7)))
    return catalog, activities, role


def plan_ids(plan):
    return [p.activity.activity_id for p in plan.activities]


class TestPrerequisiteChain:
    def test_foundation_unlocks_high_value_target(self):
        catalog, activities, role = make_chain_fixture()
        snapshot = LearnerSnapshot({"A": 0, "B": 0, "C": 0})
        plan = plan_week(catalog, activities, snapshot, role, budget_minutes=90)
        assert plan_ids(plan) == ["a1", "a2", "b1"]
        assert plan.total_minutes == 90
        assert plan.benefit == 10

    def test_tight_budget_falls_back_to_unlocked_option(self):
        catalog, activities, role = make_chain_fixture()
        snapshot = LearnerSnapshot({"A": 0, "B": 0, "C": 0})
        plan = plan_week(catalog, activities, snapshot, role, budget_minutes=60)
        assert plan_ids(plan) == ["c1"]
        assert plan.benefit == 7

    def test_levels_take_effect_after_each_activity(self):
        catalog, activities, role = make_chain_fixture()
        snapshot = LearnerSnapshot({"A": 0, "B": 0, "C": 0})
        plan = plan_week(catalog, activities, snapshot, role, budget_minutes=90)
        assert plan.activities[0].resulting_levels["A"] == 1
        assert plan.activities[1].resulting_levels["A"] == 2
        assert plan.activities[2].resulting_levels["B"] == 1

    def test_snapshot_is_not_mutated(self):
        catalog, activities, role = make_chain_fixture()
        levels = {"A": 0, "B": 0, "C": 0}
        snapshot = LearnerSnapshot(levels)
        plan_week(catalog, activities, snapshot, role, budget_minutes=90)
        assert dict(snapshot.levels) == {"A": 0, "B": 0, "C": 0}
        assert levels == {"A": 0, "B": 0, "C": 0}


class TestSharedFoundation:
    def build(self):
        catalog = SkillCatalog(
            {
                "F": Skill("F"),
                "D": Skill("D", (Prerequisite("F", 1),)),
                "E": Skill("E", (Prerequisite("F", 1),)),
            }
        )
        activities = [
            Activity("f1", 30, {"F": 1}),
            Activity("d1", 30, {"D": 1}),
            Activity("e1", 30, {"E": 1}),
        ]
        role = RoleProfile((RoleTarget("D", 1, 10), RoleTarget("E", 1, 8)))
        return catalog, activities, role

    def test_shared_foundation_scheduled_once(self):
        catalog, activities, role = self.build()
        snapshot = LearnerSnapshot({})
        plan = plan_week(catalog, activities, snapshot, role, budget_minutes=90)
        assert plan_ids(plan) == ["f1", "d1", "e1"]
        assert plan.total_minutes == 90
        assert plan.benefit == 18

    def test_self_unlocking_activity_is_rejected(self):
        """多技能活动不能用自身内部提升满足自己的前置条件。"""
        catalog, activities, role = self.build()
        cheat = Activity("cheat", 40, {"F": 1, "D": 1})
        snapshot = LearnerSnapshot({})
        plan = plan_week(
            catalog, [*activities, cheat], snapshot, role, budget_minutes=40
        )
        assert "cheat" not in plan_ids(plan)

    def test_self_unlocking_activity_only_option_gives_empty_plan(self):
        catalog, _, role = self.build()
        cheat = Activity("cheat", 40, {"F": 1, "D": 1})
        snapshot = LearnerSnapshot({})
        plan = plan_week(catalog, [cheat], snapshot, role, budget_minutes=180)
        assert plan.activities == ()
        assert plan.benefit == 0

    def test_self_unlocking_allowed_once_prereq_met(self):
        """前置已满足时，多技能活动可以合法地同时提升多项技能。"""
        catalog, _, role = self.build()
        combo = Activity("combo", 40, {"F": 1, "D": 1})
        snapshot = LearnerSnapshot({"F": 1})
        plan = plan_week(catalog, [combo], snapshot, role, budget_minutes=180)
        assert plan_ids(plan) == ["combo"]
        assert plan.benefit == 10


class TestActivityRules:
    def test_skip_level_activity_rejected(self):
        catalog = SkillCatalog({"A": Skill("A")})
        jump = Activity("jump", 30, {"A": 2})
        role = RoleProfile((RoleTarget("A", 2, 5),))
        plan = plan_week(catalog, [jump], LearnerSnapshot({}), role)
        assert plan.activities == ()

    def test_no_improvement_activity_rejected(self):
        catalog = SkillCatalog({"A": Skill("A")})
        flat = Activity("flat", 30, {"A": 1})
        role = RoleProfile((RoleTarget("A", 1, 5),))
        plan = plan_week(catalog, [flat], LearnerSnapshot({"A": 1}), role)
        assert plan.activities == ()

    def test_completed_activity_not_repeated(self):
        catalog = SkillCatalog({"A": Skill("A")})
        done = Activity("a1", 30, {"A": 1})
        role = RoleProfile((RoleTarget("A", 1, 5),))
        snapshot = LearnerSnapshot({"A": 0}, completed_activity_ids={"a1"})
        plan = plan_week(catalog, [done], snapshot, role)
        assert plan.activities == ()

    def test_default_budget_is_180(self):
        catalog = SkillCatalog({s: Skill(s) for s in "WXYZ"})
        activities = [
            Activity("w", 60, {"W": 1}),
            Activity("x", 60, {"X": 1}),
            Activity("y", 60, {"Y": 1}),
            Activity("z", 60, {"Z": 1}),
        ]
        role = RoleProfile(
            tuple(RoleTarget(s, 1, 5) for s in "WXYZ")
        )
        plan = plan_week(catalog, activities, LearnerSnapshot({}), role)
        assert plan.total_minutes == 180
        assert len(plan.activities) == 3

    def test_tie_break_prefers_shorter_plan(self):
        catalog = SkillCatalog({"A": Skill("A")})
        activities = [
            Activity("slow", 90, {"A": 1}),
            Activity("fast", 30, {"A": 1}),
        ]
        role = RoleProfile((RoleTarget("A", 1, 5),))
        plan = plan_week(catalog, activities, LearnerSnapshot({}), role)
        assert plan_ids(plan) == ["fast"]
        assert plan.total_minutes == 30

    def test_over_target_gain_adds_no_benefit(self):
        catalog = SkillCatalog({"A": Skill("A")})
        activities = [
            Activity("a1", 30, {"A": 1}),
            Activity("a2", 30, {"A": 2}),
        ]
        role = RoleProfile((RoleTarget("A", 1, 5),))
        plan = plan_week(catalog, activities, LearnerSnapshot({}), role)
        assert plan_ids(plan) == ["a1"]
        assert plan.benefit == 5

    def test_empty_plan_when_nothing_helps(self):
        catalog = SkillCatalog({"A": Skill("A")})
        activities = [Activity("a1", 30, {"A": 1})]
        role = RoleProfile((RoleTarget("B", 1, 5),))
        plan = plan_week(catalog, activities, LearnerSnapshot({}), role)
        assert plan.activities == ()
        assert plan.total_minutes == 0
        assert plan.benefit == 0


class TestValidation:
    def test_cycle_in_catalog_rejected(self):
        with pytest.raises(ValueError, match="环"):
            SkillCatalog(
                {
                    "A": Skill("A", (Prerequisite("B", 1),)),
                    "B": Skill("B", (Prerequisite("A", 1),)),
                }
            )

    def test_level_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            LearnerSnapshot({"A": 6})

    def test_non_positive_duration_rejected(self):
        with pytest.raises(ValueError):
            Activity("bad", 0, {"A": 1})

    def test_duplicate_role_target_rejected(self):
        catalog = SkillCatalog({"A": Skill("A")})
        role = RoleProfile((RoleTarget("A", 1, 5), RoleTarget("A", 2, 3)))
        with pytest.raises(ValueError, match="重复"):
            plan_week(catalog, [], LearnerSnapshot({}), role)
