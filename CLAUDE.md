# CLAUDE.md

给 Claude Code 的项目工作说明。项目规划见 [plan.md](plan.md)。

---

## 环境

```bash
conda activate urdf-pet          # python 3.11,依赖已装
```

没激活时也可以直接用 `~/miniforge3/envs/urdf-pet/bin/python`,但**必须**同时带上
`LD_LIBRARY_PATH=$CONDA_PREFIX/x11compat`——pip 装的 PySide6 需要
`libxcb-cursor.so.0`,系统里没有(装它要 root),我们从 conda-forge 装了一份,
用一个只含这一个符号链接的 `x11compat/` 目录暴露出去,避免整个 conda lib
遮盖系统库。`conda activate` 时 `etc/conda/activate.d/x11compat.sh` 会自动处理;
`scripts/check.sh` 也做了兜底。

依赖分层(见 `pyproject.toml`):核心层(numpy/trimesh/yourdfpy)**不含 GUI**,
`[desktop]` 才引入 PySide6/PyVista。这个分层不是洁癖,是为了让 L1 层能在没有
图形栈的地方跑。

本机有真实 X11 显示(`DISPLAY=:0`),GUI 程序可以直接启动。

---

## 验证哲学(先读这段,再读下面的层级)

这个项目的风险几乎全部集中在**"看起来对不对"**:透明背景有没有真的透、宠物姿态
有没有崩、拖拽手感弹不弹。这类属性默认无法被自动验证,于是很容易滑向"代码写完了,
跑个 import 测试就说完成"——这是本项目最需要防的失败模式。

因此整套流程只有一个中心思想:

> **把视觉属性翻译成可断言的数值,只把审美判断留给"渲染成图,亲眼看"。**

具体到四条硬规矩:

1. **不许用"能跑通"冒充"是对的"**。`import` 成功、窗口能弹出来、没有报错,
   这些都**不构成**功能正确的证据。
2. **每个改动必须有一条"如果我把这个功能改坏,哪条断言会红"的答案**。答不上来,
   说明那条测试没有价值。不确定时就**做变异测试**:故意把实现改坏,确认对应断言
   真的变红,再改回来。(已验证有效:FK 的三处变异全部被对拍测试抓到。)
3. **改完必须实跑,不许靠推理声称通过**。声称"应该是绿的"而没有实际运行,
   等同于没有验证。
4. **测试红了先分清是产品错还是测试错**,不要条件反射式地放宽断言。
   放宽之前必须有实测数据支撑(例如 `RENDER_JITTER` 是压测 50 帧量出来的)。

---

## 四层验证

| 层 | 跑什么 | 需要 X 显示 | 进 CI |
|---|---|---|---|
| L0 | `ruff check` / `ruff format --check` | 否 | ✅ |
| L1 | 纯逻辑单测(运动学、物理) | 否 | ✅ |
| L2 | 离屏渲染断言(RGBA 缓冲区数值断言) | **否**(VTK 退回 EGL/OSMesa) | ✅(xvfb job) |
| L3 | Qt 冒烟(滑块 → 关节角信号链) | **是**(本机 :0,CI 用 xvfb) | ✅(xvfb job) |
| L4 | 真机目视(启动真窗口 → 截图 → 亲眼看) | 是 | ❌ |

L0–L3 由一条命令跑完:

```bash
bash scripts/check.sh          # 全跑,约 8 秒
bash scripts/check.sh fast     # 只跑 L0 + L1,秒级
```

**改完任何代码,先跑这条,再说话。**

### L1 —— 纯逻辑单测

运动学和物理是纯函数,最容易测,也最该测狠一点。

- **对拍,而不是自证**:自写的 FK 必须与 `yourdfpy` 自带的场景图逐位姿比对
  (`test_fk_matches_yourdfpy`)。两套独立实现算出同一个结果,才叫验证;
  自己的结果喂给自己的断言,那叫复述。变异测试证实:真正扛事的就是这一条。
- **性质断言优先于 golden 值**:物理不要断言"第 30 帧角度等于 0.1234",要断言
  它的**性质**——弹簧-阻尼必须收敛、阻尼下能量单调不增、静止输入下不得漂移、
  关节角永远不越限。性质断言不会因为手感调参就整片变红。

### L2 —— 离屏渲染断言(本项目最关键的一层)

PyVista 的 `off_screen=True` 能在没有显示器时渲染并取回 RGBA 数组(实测有无
`DISPLAY` 结果逐像素一致)。于是"画面对不对"可以变成数值断言。
可复用的断言在 `tests/imgassert.py`:

- `assert_transparent_background(rgba)` —— 四角 alpha 必须为 0。
  **这一条就是 plan.md 第 7 节那个"全项目最大不确定点"的自动化版本。**
- `assert_within_canvas` / `assert_coverage_between` —— 宠物没跑出画面、
  没缩成一个点、没糊满全屏。
- `assert_images_differ(a, b)` —— **改了关节角,画面必须真的变**。
  这条抓 GUI 项目最常见的假绿:滑块动了、状态变了、但渲染没更新。
  它还兼职守住默认机位:如果相机角度让整条左臂或尾巴被躯干挡死,这里会红——
  那种机位下宠物做动作用户根本看不见,等于白做。
- `assert_images_stable(a, b)` —— 同样的关节角,两次渲染必须(近乎)一致。
  **容差不是零**:实测 240×240 连续渲染 50 次,有 1 次出现 3 像素差异
  (GPU 边缘抗锯齿不是逐位可复现)。断言 `== 0` 会大约每 50 次假红一次。
  容差 0.05% 与真实信号(最小的关节动作也有 0.88% 像素变化)隔着一个数量级。

后两条是**互相咬合**的:一条防"该变的没变",一条防"不该变的乱变"。

### L3 —— Qt 冒烟

构造真实的 QApplication 和 `PetWindow`,断言**信号链通**:
`slider.set_radians(x)` 之后,`viewport.configuration` 里的关节角确实变成 x,
并且渲染 actor 的变换矩阵也跟着变了。

注意两个坑(都踩过):
- `QT_QPA_PLATFORM=offscreen` **不行**。VTK 仍会去连 X 并拿到无效窗口句柄,
  直接 `BadWindow` 崩溃。必须给一个真实 X 显示(本机 :0,CI 用 `xvfb-run`)。
- 滑块是 1000 级整数刻度,任何角度都会被吸附到最近刻度,最大误差约 1.2e-3 rad。
  断言要用 `quantization_tolerance()`,别用 `atol=1e-9` 去挑剔一个不存在的缺陷。

### L4 —— 真机目视

只有这一层能回答"它好看吗、萌不萌、透明是不是真透"。

```bash
python scripts/visual_check.py --pose wave      # 预设姿态:neutral/wave/sit/extremes
python scripts/visual_check.py --full           # 连桌面一起截(验证合成效果)
```

然后**用 Read 工具打开 `screenshots/` 里那个 PNG 亲眼看**。这一步不能省略成
"截图存下来了所以没问题"。它已经抓到过两个 L0–L3 完全看不见的问题
(3D 区域全黑、滑块读数不刷新)。

- **不能用 `QWidget.grab()`**:QtInteractor 的 3D 内容画在原生 OpenGL 表面上,
  Qt 控件级抓图取到的是一块纯黑。必须用 ffmpeg x11grab 抓真实合成像素。
- **隐私**:默认只抓宠物窗口所占的屏幕矩形。`--full` 会拍到用户的真实桌面,
  只在验证"与桌面背景的合成"时才用,用完即弃,不要提交进仓库
  (`screenshots/` 已 gitignore)。

---

## 各阶段该加哪层测试

对应 plan.md 的路线图:

| 阶段 | 必须新增的验证 |
|---|---|
| 0 URDF 加载 + 滑块 | ✅ 已完成:L1 FK 对拍、L2 渲染断言、L3 滑块信号链 |
| 0.5 透明窗口 spike | **L2 `assert_transparent_background` 用在真窗口截图上**;L4 目视确认 |
| 1 会动 | L1 物理性质断言(收敛/不漂移/不越限);L2 帧间差异 |
| 2 桌面壳 | L4 为主(点穿透、置顶),L3 保证不回归 |
| 3 任意 URDF 导入 | L1 畸形 URDF 的容错(缺 mesh、循环、超长链、多根) |

---

## 惯例

- 中文注释和 commit message。
- `src/` 布局,包名 `urdf_pet`,导入一律 `from urdf_pet.xxx import`。
- **`render/scene.py` 不许 import Qt**,Qt 只出现在 `render/viewport.py` 和
  `desktop/`。`render/__init__.py` 也不导出 viewport——`import urdf_pet.render`
  不应该把 Qt 拉进来。这是 L2 层能脱离 Qt 独立跑的前提,别破坏它。
- `render/` 不许 import `desktop/`。
- 新增依赖要想清楚放 core 还是 `[desktop]`:凡是 import 了 Qt 或 VTK 的,
  一律进 `[desktop]`。
