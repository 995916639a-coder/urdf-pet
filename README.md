# urdf-pet

一个悬浮在桌面上的小宠物,它的身体不是贴图,而是一副真实的机器人关节树(URDF)。

当前进度:**阶段 0 完成**——手写的几何体小生物 `blob`(9 个关节),
普通窗口 + 每个关节一个滑块,姿态由自写的正运动学实时解算。

规划见 [plan.md](plan.md);开发与验证约定见 [CLAUDE.md](CLAUDE.md)。

## 跑起来

```bash
conda activate urdf-pet
python scripts/dev_preview.py              # 滑块预览窗口
python scripts/dev_preview.py my.urdf      # 换一副身体
```

## 开发

```bash
python -m pip install -e ".[dev]"            # 核心 + 测试(无 GUI)
python -m pip install -e ".[dev,desktop]"    # 加上渲染与桌面壳

bash scripts/check.sh                        # 提交前跑这个(lint + 全部测试)
bash scripts/check.sh fast                   # 只跑 lint + 运动学,秒级

python scripts/visual_check.py --pose wave   # 截图到 screenshots/,人工目视
```
