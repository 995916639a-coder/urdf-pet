"""正运动学:关节角 → 每个连杆相对根连杆的位姿。

自己用 numpy 实现,而不是直接调 yourdfpy 的场景图。原因不是不信任 yourdfpy,
而是:两套独立实现能互相对拍(见 tests/test_kinematics.py),这才构成验证;
另外这一层将来是 Rust 加速层最自然的替换点(plan.md 第 2 节)。
"""

from __future__ import annotations

import numpy as np

from urdf_pet.kinematics.loader import PetModel


def rotation_about_axis(axis: np.ndarray, angle: float) -> np.ndarray:
    """罗德里格斯公式,返回 3x3 旋转矩阵。axis 必须已归一化。"""
    kx, ky, kz = axis
    K = np.array([[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]])
    return np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)


def joint_transform(spec, value: float) -> np.ndarray:
    """单个关节的父→子变换:固定 origin 再叠加关节自身的运动。"""
    motion = np.eye(4)
    if spec.type in ("revolute", "continuous"):
        motion[:3, :3] = rotation_about_axis(spec.axis, value)
    elif spec.type == "prismatic":
        motion[:3, 3] = spec.axis * value
    # fixed(及未支持的类型)保持恒等
    return spec.origin @ motion


def link_transforms(model: PetModel, q: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """返回 {连杆名: 4x4 位姿},均相对于根连杆。

    q 按 model.actuated_names 的顺序;None 表示中立姿态。
    """
    q = model.neutral_cfg() if q is None else np.asarray(q, dtype=float)
    if q.shape != (model.dof,):
        raise ValueError(f"q 形状应为 ({model.dof},),实际 {q.shape}")

    values = dict(zip(model.actuated_names, q, strict=True))

    # 按父连杆分组,自根向下遍历。URDF 保证是树,不会有环。
    by_parent: dict[str, list] = {}
    for spec in model.joints:
        by_parent.setdefault(spec.parent, []).append(spec)

    transforms = {model.root_link: np.eye(4)}
    stack = [model.root_link]
    while stack:
        parent = stack.pop()
        for spec in by_parent.get(parent, ()):
            transforms[spec.child] = transforms[parent] @ joint_transform(
                spec, values.get(spec.name, 0.0)
            )
            stack.append(spec.child)

    missing = set(model.link_names) - set(transforms)
    if missing:
        raise ValueError(f"这些连杆没有连到根上:{sorted(missing)}")
    return transforms
