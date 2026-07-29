# URDF 物理桌面宠物 —— 项目规划书

> 一句话定位:一个悬浮在桌面上的小宠物,它的身体不是贴图,而是一副**真实的机器人关节树(URDF)**;它会呼吸、会被你拖着晃、(未来)会伸手够你的鼠标。最终目标是任何人都能把自己的 URDF 拖进来,在桌面上养一只"机器人形态"的宠物。
>
> 技术基调:**大部分用 Python 实现**,Rust 仅作为可选的性能加速模块(想练手时的切入点,非必需)。

---

## 1. 这个项目为什么独特

市面上的桌面宠物几乎都是**贴图 / Live2D / 骨骼动画**——本质是逐帧或蒙皮动画,身体没有真实的物理结构。

本项目的差异点:**用机器人的关节树(URDF)作为宠物的身体规格**。这意味着:

- 每个动作都是**实时解算**出来的(正运动学驱动姿态),而不是预先画好的帧;
- 它能表现出"物理感"——被拖动时肢体因惯性甩动、重力下垂、伸手够目标;
- 天然支持"导入任意 URDF",让别人也能生成自己的机器人宠物。

**做机器人的人**和**做桌面宠物的人**几乎是两个不相交的圈子,本项目正好落在这个缝隙上——这是它的护城河,也是它区别于"GitHub 上第 N 个桌面宠物 / 第 N 个 URDF viewer"的地方。

---

## 2. 技术栈(Python 为主)

| 层 | 选型 | 说明 |
|---|---|---|
| URDF 解析 + 几何 | **yourdfpy**(→ trimesh) | 解析 URDF、构建 link 树;手写的几何体 URDF 无需外部 mesh 文件,trimesh 直接生成 box/cylinder/sphere |
| 运动学 FK/IK | **Pinocchio** 或自写 numpy | 你的主场;FK 驱动姿态,IK 用于"够光标"等行为 |
| 物理手感 | 自写 Python(numpy) | 空闲摆动(正弦)、拖拽惯性(弹簧-阻尼)、重力下垂 |
| 3D 渲染 | **PySide6 + PyVista(pyvistaqt)** | PyVista 基于 VTK,`QtInteractor` 可嵌入 PySide6 窗口,支持透明背景;备选 Qt3D / QtQuick3D |
| 桌面壳 | **PySide6**(无边框/透明/置顶)+ **pywin32**(点穿透) | 纯 Python 即可,无需 Rust |
| 可选加速 | **Rust + PyO3 / maturin** | 把 IK 数值解、物理积分等热点写成 Python 可调用的 Rust 扩展;非必需,想练 Rust 时的理想切入点 |

**关于 Rust 的定位(诚实说明)**:以桌面宠物(单只、物理简单)的规模,Python + numpy 完全够用,Rust **不是必需**。但如果你想练手,最真实、最有价值的切入点是用 PyO3/maturin 把运动学/物理的计算热点(如数值 IK、弹簧-阻尼积分)封装成 Rust 扩展供 Python 调用——这正是业界加速 Python 的标准做法(Pinocchio 本身就是 C++ 加速),而且是一条干净的 Python↔Rust 边界,练到的是能迁移的真本事。它被设计成"可插拔的加速层",拔掉也不影响项目跑起来。

> 技术栈仍是建议方案,渲染库(PyVista vs Qt3D vs QtQuick3D)可在阶段 0.5 的验证后再最终敲定。

---

## 3. 可直接复用的现成轮子(不必重复造)

- **yourdfpy**(PyPI):目前"野外 URDF"加载最稳的 Python 解析库,输出 trimesh 场景,自带可视化。
- **trimesh**:几何处理;原生几何体 URDF 直接生成 primitive,绕开 mesh 文件。
- **PyVista + pyvistaqt**:VTK 的高层封装,`QtInteractor` 可嵌入 PySide6,工业级 3D 渲染。
- **Pinocchio**:高性能刚体运动学/动力学(你已在用),FK/IK 主力。
- **pywin32**:Windows 平台点穿透(`WS_EX_TRANSPARENT | WS_EX_LAYERED`)等窗口底层控制。
- **PyO3 / maturin**:把 Rust 编译成 Python 扩展的标准工具链(可选加速层用)。
- 桌面壳的窗口配置与点穿透坑,可参考社区已有的桌面宠物项目经验(见附录)。

---

## 4. 分阶段路线

核心原则:**把"桌面壳"和"URDF 身体"两条线拆开,每个阶段都单独可玩、都不难,正反馈尽量早。**

### 阶段 0 —— 独立窗口最小版(预计 1–2 天)
- 用 yourdfpy 加载一个 URDF,PyVista 渲染出来,拖滑块能让关节动(先用普通带边框窗口,不碰透明/桌面集成)。
- **降难技巧:先不用真机 URDF**(会牵扯一堆外部 STL/DAE 网格文件),而是**手写一个极简 URDF,只用 box / cylinder / sphere 等原生几何体**拼一个卡通小生物,彻底绕开 mesh 加载。
- **交付物**:一个能加载并滑块控制的桌面程序;一只"几何体小生物"。

### 阶段 0.5 —— 透明窗口验证(spike,半天)
- **单独验证一个技术风险点**:PySide6 无边框透明窗口里,PyVista/VTK 能否渲染出**背景透明**的 3D(只见宠物、不见窗口底色)。
- 这是全项目最不确定的一环,提前踩一脚,通过就继续路线 A,不通过就切到备选路线(见第 7 节)。
- **交付物**:一个透明背景、能看到 3D 小生物的空窗口。

### 阶段 1 —— 让它"活"起来
物理手感是灵魂,难度递增,逐个加:
1. **空闲呼吸 / 摆动**:关节做小幅正弦摆动,立刻显得"活着"。几乎零成本。
2. **拖拽惯性**:鼠标拖身体时肢体因惯性甩动、慢慢停下。用弹簧-阻尼 `F = -k·x - c·v` 实现。
3. (可选,后期)**IK 够光标 / 重力下垂 / 平衡**:发挥 FK/IK/Pinocchio 专长,锦上添花。
- **交付物**:一只会呼吸、被拖会晃的小生物。

### 阶段 2 —— 组装成真桌面宠物
- 把渲染视图放进阶段 0.5 验证过的透明壳,配好无边框 / 置顶 / 点穿透(pywin32)。
- **交付物**:小生物悬浮在桌面上,不挡背后点击。最有成就感的一刻。

### 阶段 3 及以后 —— 导入任意 URDF(终极形态)
- 支持拖拽任意 URDF(含 mesh 文件)在桌面生成宠物。
- 作为面向机器人极客的"彩蛋"和技术深度证明。

---

## 5. 项目文件层次结构(顶层设计)

设计原则:**按关注点分层,且每一层对应一个开发阶段**——你一眼就能看出"现在该动哪个目录"。渲染(`render/`)与桌面壳(`desktop/`)刻意解耦,让阶段 0/1 能先在普通窗口里跑渲染,阶段 2 再套壳。采用现代 Python 的 `src/` 布局。

```
urdf-pet/
├── pyproject.toml              # 依赖与打包(PySide6, pyvista, yourdfpy, pin...)
├── README.md
├── LICENSE
├── docs/
│   └── plan.md                 # 本规划书
│
├── src/
│   └── urdf_pet/
│       ├── __init__.py
│       ├── app.py              # 应用入口:组装 kinematics + behavior + render + desktop
│       ├── config.py           # 配置:选哪只宠物、窗口位置、开关项
│       │
│       ├── kinematics/         # 【阶段0】URDF 解析 + 运动学(核心)
│       │   ├── loader.py       #   yourdfpy 封装:URDF → link 树 / trimesh 场景
│       │   ├── fk.py           #   正运动学:关节角 → 各 link 位姿
│       │   └── ik.py           #   逆运动学(阶段1后期,够光标用)
│       │
│       ├── behavior/           # 【阶段1】物理手感 / 宠物行为
│       │   ├── idle.py         #   空闲呼吸 / 摆动
│       │   ├── drag.py         #   拖拽惯性(弹簧-阻尼)
│       │   ├── gravity.py      #   重力下垂(可选)
│       │   └── controller.py   #   关节控制器 PD / 阻抗(远期"控制手感"支线)
│       │
│       ├── render/             # 3D 渲染(把关节树画出来,与窗口壳解耦)
│       │   ├── scene.py        #   场景管理:link → 渲染 actor,随 FK 更新变换
│       │   └── viewport.py     #   可嵌入的 3D 视图(PyVista QtInteractor 封装)
│       │
│       ├── desktop/            # 【阶段2】桌面壳
│       │   ├── window.py       #   无边框 / 透明 / 置顶窗口
│       │   └── passthrough.py  #   平台相关点穿透(pywin32 等)
│       │
│       └── io/                 # 【阶段3】通用 URDF 导入
│           └── importer.py     #   拖拽加载、mesh 路径解析、校验
│
├── assets/
│   └── urdf/
│       └── blob/               # 【阶段0】手写的几何体小生物
│           └── blob.urdf
│
├── rust_ext/                   # 可选 Rust 加速扩展(PyO3 / maturin)
│   ├── Cargo.toml
│   └── src/
│       └── lib.rs              #   IK 数值解 / 物理积分等热点(拔掉不影响主线)
│
├── scripts/
│   └── dev_preview.py          # 快速起一个渲染预览,调手感用
│
└── tests/
    ├── test_kinematics.py
    └── test_behavior.py
```

**这套结构的几个用心处**:
- `kinematics / behavior / desktop / io` 分别对应阶段 0 / 1 / 2 / 3,目录即路线图。
- `render/` 独立于 `desktop/`:渲染不依赖"是不是桌面宠物窗口",所以能先在普通窗口调试,后期无痛套壳。
- `rust_ext/` 完全独立于 Python 包,是可插拔加速层,不侵入主逻辑。
- `assets/urdf/blob/` 放手写小生物;将来通用导入的 URDF 走 `io/`,与内置资产分开。

---

## 6. 几个产品判断(建议采纳)

- **手感 > 通用性**。"讨人喜欢"几乎全取决于物理手感萌不萌、灵不灵,而**不在于**"能导入任意 URDF"。桌面宠物的主流受众是普通人,吃的是"这小东西会追我鼠标好可爱";通用 URDF 导入是给极客看的。**顺序别搞反**:先把一只精心设计的小生物 + 好手感打磨到会让人截图分享,再做通用导入。
- **两个受众都能吃到**:精致小生物 → 普通用户;任意 URDF 导入 → 机器人极客 + 简历上的技术深度。
- **随时可以收工**:阶段 0 本身就是一个完整、可放 GitHub 的项目。后面每个阶段都是可选加法,不是必须跨的坎。

---

## 7. 已知难点与规避

| 难点 | 规避方式 |
|---|---|
| **透明窗口里做 3D 渲染**(全项目最大不确定点) | 阶段 0.5 单独做 spike 验证;若 PyVista/VTK 透明背景不理想,切备选路线(下条) |
| 备选渲染路线 | Python 只做"大脑"(FK/IK/物理),渲染交给内嵌 Web 视图(three.js + urdf-loader)+ pywebview 壳。透明是 Web 强项,但会引入少量 JS,不如纯 Python 纯粹,故列为 fallback |
| 真机 URDF 的 STL/DAE mesh 加载麻烦 | 起步用原生几何体手写 URDF,绕开 mesh(阶段 0) |
| 点穿透("点得到宠物、点不到会穿到背后") | Windows 用 pywin32 设 `WS_EX_TRANSPARENT`;注意透明像素点击判定,参考社区踩坑记录 |
| 一次想做太多被劝退 | 严格按阶段推进,阶段 0/1 全程只是普通窗口,不碰桌面集成 |

---

## 8. 后续可延伸方向(远期,不影响当前规划)

- **控制手感实验室**:给关节挂可切换的控制器(纯位置 / PD / 阻抗),直观展示真机"为什么不会瞬移、增益调不好会震荡"——`behavior/controller.py` 已预留位置。
- **重力补偿开关**、**安全状态机可视化**等偏教学的模块。
- 宠物"AI 大脑"(接 LLM,让它能陪聊 / 提醒),列为可选支线(会改变项目性质)。

---

## 附录:参考资源

- yourdfpy (PyPI): https://pypi.org/project/yourdfpy/
- scikit-robot(URDF + trimesh 可视化参考): https://github.com/iory/scikit-robot
- PyVista / pyvistaqt(嵌入 PySide6 的 3D): https://doc.qt.io/qtforpython-6/PySide6/QtQuick3D/index.html
- CrabNebula《Building a Desktop Pet with Tauri》(桌面壳窗口配置思路,可迁移): https://crabnebula.dev/blog/building-a-desktop-pet-with-tauri/
- Tauri v2 桌面宠物点穿透踩坑(思路可迁移到 pywin32): https://dev.to/rain9/tired-of-boring-ai-assistants-i-built-a-desktop-pet-copilot-that-wanders-around-your-screen-and-52pg
- urdf-loader(备选 Web 渲染路线用): https://www.npmjs.com/package/urdf-loader
- PyO3: https://github.com/PyO3/pyo3 ,maturin: https://github.com/PyO3/maturin

---

*本规划书为第 2 稿(技术栈改为 Python 为主 + 可选 Rust,并补充文件结构)。供审阅,各项仍可调整。*