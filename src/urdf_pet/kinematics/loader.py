"""URDF 加载:把 yourdfpy 的解析结果收敛成本项目要用的最小数据结构。

这一层只做"读"和"整理",不做任何运动学计算——计算在 fk.py 里,
两者分开是为了让 fk 能被独立地与 yourdfpy 自带的场景图对拍(见 CLAUDE.md L1)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yourdfpy

# 仓库根目录下的内置资产。阶段 3 做通用导入时,外部 URDF 走 io/importer.py。
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_URDF = REPO_ROOT / "assets" / "urdf" / "blob" / "blob.urdf"

# 会随关节角变化的关节类型;其余(fixed)视作恒等变换。
MOVABLE_TYPES = frozenset({"revolute", "continuous", "prismatic"})


@dataclass(frozen=True)
class JointSpec:
    """一个关节的静态规格。origin 是父连杆到关节的固定变换(4x4)。"""

    name: str
    type: str
    parent: str
    child: str
    origin: np.ndarray  # (4, 4)
    axis: np.ndarray  # (3,) 单位向量
    lower: float
    upper: float

    @property
    def movable(self) -> bool:
        return self.type in MOVABLE_TYPES


@dataclass(frozen=True)
class PetModel:
    """一只宠物的身体规格:连杆树 + 关节表 + 限位。"""

    urdf: yourdfpy.URDF
    name: str
    root_link: str
    link_names: tuple[str, ...]
    joints: tuple[JointSpec, ...]  # 全部关节,含 fixed
    actuated_names: tuple[str, ...]  # 可驱动关节,顺序即 q 的顺序

    @property
    def dof(self) -> int:
        return len(self.actuated_names)

    @property
    def limits(self) -> np.ndarray:
        """(dof, 2) 的下/上限,顺序与 actuated_names 一致。"""
        by_name = {j.name: j for j in self.joints}
        return np.array([[by_name[n].lower, by_name[n].upper] for n in self.actuated_names])

    def neutral_cfg(self) -> np.ndarray:
        """中立姿态:全零,并夹进限位(以防某关节的合法区间不含 0)。"""
        return self.clamp(np.zeros(self.dof))

    def clamp(self, q: np.ndarray) -> np.ndarray:
        lim = self.limits
        return np.clip(np.asarray(q, dtype=float), lim[:, 0], lim[:, 1])


def _axis(raw) -> np.ndarray:
    """URDF 的 axis 缺省为 (1,0,0);顺手归一化,免得后面的罗德里格斯公式失真。"""
    axis = np.array([1.0, 0.0, 0.0]) if raw is None else np.asarray(raw, dtype=float)
    norm = float(np.linalg.norm(axis))
    if norm == 0.0:
        raise ValueError("关节 axis 为零向量")
    return axis / norm


def load_model(path: str | Path = DEFAULT_URDF) -> PetModel:
    """加载 URDF。几何体由 yourdfpy/trimesh 负责,这里不碰渲染。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"URDF 不存在:{path}")

    urdf = yourdfpy.URDF.load(str(path))

    joints = tuple(
        JointSpec(
            name=j.name,
            type=j.type,
            parent=j.parent,
            child=j.child,
            # origin 缺省是恒等;yourdfpy 已解析成 4x4,这里复制一份防止外部改动
            origin=np.eye(4) if j.origin is None else np.array(j.origin, dtype=float),
            axis=_axis(j.axis),
            lower=-np.inf if j.limit is None else float(j.limit.lower),
            upper=np.inf if j.limit is None else float(j.limit.upper),
        )
        for j in urdf.robot.joints
    )

    children = {j.child for j in joints}
    roots = [name for name in urdf.link_map if name not in children]
    if len(roots) != 1:
        raise ValueError(f"期望恰好一个根连杆,实际找到 {roots}")

    return PetModel(
        urdf=urdf,
        name=urdf.robot.name,
        root_link=roots[0],
        link_names=tuple(urdf.link_map),
        joints=joints,
        actuated_names=tuple(urdf.actuated_joint_names),
    )
