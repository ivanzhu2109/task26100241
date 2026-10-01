# task26100241

每周学习路径规划库。由上层直接调用 `learning_path.plan_week`，无接口层；
技能目录、候选活动、学员快照均由调用方传入，计算仅存内存，不会修改传入的快照。

## 用法

```python
from learning_path import (
    Activity, LearnerSnapshot, Prerequisite,
    RoleProfile, RoleTarget, SkillCatalog, plan_week,
)

catalog = SkillCatalog(
    skills=frozenset({"A", "B"}),
    prerequisites=(Prerequisite(skill="B", requires_skill="A", requires_level=2),),
)
activities = [
    Activity("a1", 30, (("A", 1),)),
    Activity("a2", 30, (("A", 2),)),
    Activity("b1", 30, (("B", 1),)),
]
snapshot = LearnerSnapshot(levels={"A": 0, "B": 0})
role = RoleProfile(targets=(RoleTarget("B", 1, 10),))

plan = plan_week(catalog, activities, snapshot, role, budget_minutes=90)
# plan.activity_ids == ("a1", "a2", "b1")，按返回顺序执行
# plan.total_minutes == 90，plan.total_gain == 10
```

`budget_minutes` 缺省为 180。收益相同取总时长最短；无有收益计划时返回空计划。

## 测试

```bash
python3 -m pytest tests/ -q
```
