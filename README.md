# urdf-pet

一个悬浮在桌面上的小宠物,它的身体不是贴图,而是一副真实的机器人关节树(URDF)。

规划见 [plan.md](plan.md)。

## 开发

```bash
python -m pip install -e ".[dev]"        # 核心 + 测试(无 GUI)
python -m pip install -e ".[dev,desktop]" # 加上渲染与桌面壳
pytest
ruff check . && ruff format --check .
```
