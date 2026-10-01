"""周学习路径规划库的自动化测试。"""
from learning_path import (
    Activity,
    LearnerSnapshot,
    Prerequisite,
    RoleProfile,
    RoleTarget,
    SkillCatalog,
    plan_week,
)


def test_foundation_unlocks_high_value_skill():
    """场景一：基础技能A不在岗位中，但能解锁高价值的B。

    预算90分钟时应选择 A->A->B（收益10），而不是直接学C（收益7）。
    """
    catalog = SkillCatalog(
        skills=frozenset({"A", "B", "C"}),
        prerequisites=(Prerequisite(skill="B", requires_skill="A", requires_level=2),),
    )
    activities = [
        Activity("a1", 30, (("A", 1),)),
        Activity("a2", 30, (("A", 2),)),
        Activity("b1", 30, (("B", 1),)),
        Activity("c1", 60, (("C", 1),)),
    ]
    snapshot = LearnerSnapshot(levels={"A": 0, "B": 0, "C": 0})
    role = RoleProfile(
        targets=(
            RoleTarget("B", 1, 10),
            RoleTarget("C", 1, 7),
        )
    )

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=90)

    assert plan.activity_ids == ("a1", "a2", "b1")
    assert plan.total_minutes == 90
    assert plan.total_gain == 10


def test_shared_foundation_and_no_internal_unlock():
    """场景二：多个目标共享基础技能；活动内部提升不能解锁自身前置。

    - 基础技能 X 是岗位技能 Y、Z 的共同前置，只需学习一次。
    - 活动 "cheat" 同时声明 X:1 与 Y:1，试图用内部提升的 X 满足 Y 的前置，
      在活动开始前 X 仍为 0，因此该活动不可执行。
      （若错误地允许内部解锁，cheat(10分钟)+z1 只需50分钟即可拿到全部收益，
      会比诚实路径更短；正确实现必须走 x1+y1+z1。）
    """
    catalog = SkillCatalog(
        skills=frozenset({"X", "Y", "Z"}),
        prerequisites=(
            Prerequisite(skill="Y", requires_skill="X", requires_level=1),
            Prerequisite(skill="Z", requires_skill="X", requires_level=1),
        ),
    )
    activities = [
        Activity("cheat", 10, (("X", 1), ("Y", 1))),  # 非法：内部提升不能自我解锁
        Activity("x1", 40, (("X", 1),)),
        Activity("y1", 5, (("Y", 1),)),
        Activity("z1", 40, (("Z", 1),)),
    ]
    snapshot = LearnerSnapshot(levels={"X": 0, "Y": 0, "Z": 0})
    role = RoleProfile(
        targets=(
            RoleTarget("Y", 1, 5),
            RoleTarget("Z", 1, 5),
        )
    )

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=120)

    assert "cheat" not in plan.activity_ids
    # 共享基础课只占一次时间：X 学一次即可同时解锁 Y 和 Z。
    assert sorted(plan.activity_ids) == ["x1", "y1", "z1"]
    assert plan.activity_ids[0] == "x1"  # 前置课必须先完成
    assert plan.total_minutes == 85
    assert plan.total_gain == 10


def test_internal_unlock_rejected_even_when_alone_affordable():
    """仅有 cheat 类活动可用时，无合法收益计划，返回空计划。"""
    catalog = SkillCatalog(
        skills=frozenset({"X", "Y"}),
        prerequisites=(Prerequisite(skill="Y", requires_skill="X", requires_level=1),),
    )
    activities = [Activity("cheat", 10, (("X", 1), ("Y", 1)))]
    snapshot = LearnerSnapshot(levels={"X": 0, "Y": 0})
    role = RoleProfile(targets=(RoleTarget("Y", 1, 9),))

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ()
    assert plan.total_minutes == 0
    assert plan.total_gain == 0


def test_snapshot_is_not_mutated():
    """调用不得改变传入的学员快照。"""
    catalog = SkillCatalog(skills=frozenset({"A"}))
    activities = [Activity("a1", 30, (("A", 1),))]
    levels = {"A": 0}
    completed = frozenset({"old"})
    snapshot = LearnerSnapshot(levels=levels, completed_activity_ids=completed)
    role = RoleProfile(targets=(RoleTarget("A", 1, 5),))

    plan_week(catalog, activities, snapshot, role, budget_minutes=60)

    assert levels == {"A": 0}
    assert snapshot.levels == {"A": 0}
    assert snapshot.completed_activity_ids == frozenset({"old"})


def test_completed_activities_are_excluded():
    """已完成的活动不能再选。"""
    catalog = SkillCatalog(skills=frozenset({"A"}))
    activities = [
        Activity("a1", 30, (("A", 1),)),
        Activity("a2", 30, (("A", 2),)),
    ]
    snapshot = LearnerSnapshot(
        levels={"A": 1}, completed_activity_ids=frozenset({"a1"})
    )
    role = RoleProfile(targets=(RoleTarget("A", 2, 5),))

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ("a2",)
    assert plan.total_gain == 5


def test_level_can_only_increase_by_one_per_activity():
    """声明等级不得超过当前等级加一。"""
    catalog = SkillCatalog(skills=frozenset({"A"}))
    activities = [Activity("jump", 30, (("A", 2),))]
    snapshot = LearnerSnapshot(levels={"A": 0})
    role = RoleProfile(targets=(RoleTarget("A", 2, 5),))

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ()


def test_tie_break_prefers_shorter_total_duration():
    """收益相同取总时长最短。"""
    catalog = SkillCatalog(skills=frozenset({"A"}))
    activities = [
        Activity("slow", 90, (("A", 1),)),
        Activity("fast", 30, (("A", 1),)),
    ]
    snapshot = LearnerSnapshot(levels={"A": 0})
    role = RoleProfile(targets=(RoleTarget("A", 1, 5),))

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ("fast",)
    assert plan.total_minutes == 30


def test_default_budget_is_180_minutes():
    """预算默认180分钟。"""
    catalog = SkillCatalog(skills=frozenset({"A"}))
    activities = [
        Activity("a1", 120, (("A", 1),)),
        Activity("a2", 120, (("A", 2),)),
    ]
    snapshot = LearnerSnapshot(levels={"A": 0})
    role = RoleProfile(targets=(RoleTarget("A", 2, 5),))

    plan = plan_week(catalog, activities, snapshot, role)

    # 两个活动共240分钟超出默认预算，只能选一个，收益5。
    assert plan.total_minutes == 120
    assert plan.total_gain == 5


def test_no_profitable_plan_returns_empty():
    """没有任何有收益的合法计划时返回空计划。"""
    catalog = SkillCatalog(skills=frozenset({"A", "X"}))
    activities = [Activity("x1", 30, (("X", 1),))]  # X 不在岗位中
    snapshot = LearnerSnapshot(levels={"A": 0, "X": 0})
    role = RoleProfile(targets=(RoleTarget("A", 1, 5),))

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ()
    assert plan.total_gain == 0


def test_multi_skill_activity_and_sequential_effect():
    """多技能活动正常生效，且等级在每个活动完成后立即生效。"""
    catalog = SkillCatalog(
        skills=frozenset({"A", "B"}),
        prerequisites=(Prerequisite(skill="B", requires_skill="A", requires_level=1),),
    )
    activities = [
        Activity("a1", 30, (("A", 1),)),
        Activity("combo", 50, (("A", 2), ("B", 1),)),  # 开始前 A 已为1，前置满足
    ]
    snapshot = LearnerSnapshot(levels={"A": 0, "B": 0})
    role = RoleProfile(
        targets=(
            RoleTarget("A", 2, 3),
            RoleTarget("B", 1, 4),
        )
    )

    plan = plan_week(catalog, activities, snapshot, role, budget_minutes=180)

    assert plan.activity_ids == ("a1", "combo")
    assert plan.total_gain == 3 * 2 + 4 * 1
