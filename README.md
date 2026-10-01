# learning_planner

每周学习路径规划库。由上层直接调用，无接口层；技能目录、候选活动、
学员快照均由调用方传入，计算数据仅存内存，调用不会修改传入的快照。

## 用法

```python
from learning_planner import (
    Activity, LearnerSnapshot, Prerequisite,
    RoleProfile, RoleTarget, Skill, SkillCatalog, plan_week,
)

catalog = SkillCatalog({
    "A": Skill("A"),
    "B": Skill("B", (Prerequisite("A", 2),)),  # B 要求 A 达到 2 级
})
activities = [
    Activity("a1", 30, {"A": 1}),
    Activity("a2", 30, {"A": 2}),
    Activity("b1", 30, {"B": 1}),
]
snapshot = LearnerSnapshot({"A": 0, "B": 0})
role = RoleProfile((RoleTarget("B", 1, 10),))

plan = plan_week(catalog, activities, snapshot, role)  # 默认预算 180 分钟
for step in plan.activities:
    print(step.activity.activity_id, step.resulting_levels)
print(plan.total_minutes, plan.benefit)
```

## 规则摘要

- 技能等级 0..5；岗位为部分技能指定目标等级与 1..10 的业务权重。
- 前置关系构成有向无环图（建目录时校验，发现环抛 `ValueError`）。
- 活动声明的每个等级不得超过当前等级 +1，且至少一项有提升；
  所有被提升技能的前置阈值必须在活动开始前满足，
  同一活动内部的提升不能互相解锁。
- 活动不可拆分、不可重复；计划按返回顺序执行；总时长不超过预算。
- 收益 = 各岗位技能本周减少的缺口 × 业务权重之和；
  收益相同取总时长最短；无有收益计划时返回空计划。

## 测试

```bash
python3 -m pytest tests/ -q
```
