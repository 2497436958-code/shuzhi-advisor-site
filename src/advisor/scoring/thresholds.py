"""四级门槛。数据必须来自官方指标文件，不由前端或模型改写。"""

LEVELS = [
    {
        "level": 1,
        "name": "初始级",
        "min_score": 20.0,
        "min_scenarios": 6,
        "min_constraint_scenarios": 3,
    },
    {
        "level": 2,
        "name": "规范级",
        "min_score": 40.0,
        "min_scenarios": 6,
        "min_constraint_scenarios": 3,
    },
    {
        "level": 3,
        "name": "集成级",
        "min_score": 60.0,
        "min_scenarios": 8,
        "min_constraint_scenarios": 5,
    },
    {
        "level": 4,
        "name": "协同级",
        "min_score": 80.0,
        "min_scenarios": 10,
        "min_constraint_scenarios": 6,
    },
]
