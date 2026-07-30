"""把连杆树画出来:URDF 视觉体 → PyVista actor,再由 FK 结果驱动其变换。

设计要点:几何体只在初始化时构建一次,每帧只更新 actor 的 4x4 变换矩阵。
这既是动画该有的做法,也让"同样的 q 必然渲染出同样的像素"成立——
L2 层的图像断言依赖这个确定性(见 CLAUDE.md)。

本模块不 import 任何 Qt 相关的东西,因此可以在 off_screen 模式下独立跑。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyvista as pv

from urdf_pet.kinematics.fk import link_transforms
from urdf_pet.kinematics.loader import PetModel

DEFAULT_COLOR = (0.7, 0.7, 0.7, 1.0)


@dataclass
class VisualPart:
    """一个视觉体:所属连杆 + 连杆坐标系下的固定偏移 + 网格 + 颜色。"""

    link: str
    local: np.ndarray  # (4, 4)
    mesh: pv.PolyData
    rgba: tuple[float, float, float, float]


def _primitive_to_mesh(geometry) -> pv.PolyData:
    """URDF 原生几何体 → PyVista 网格。三者都以自身原点为中心,与 URDF 约定一致。"""
    if geometry.sphere is not None:
        return pv.Sphere(radius=geometry.sphere.radius, theta_resolution=32, phi_resolution=32)
    if geometry.cylinder is not None:
        # URDF 圆柱沿 +z,高度以原点为中心
        return pv.Cylinder(
            direction=(0.0, 0.0, 1.0),
            radius=geometry.cylinder.radius,
            height=geometry.cylinder.length,
            resolution=32,
        )
    if geometry.box is not None:
        x, y, z = geometry.box.size
        return pv.Cube(x_length=x, y_length=y, z_length=z)
    if geometry.mesh is not None:
        raise NotImplementedError("mesh 视觉体留到阶段 3 的通用 URDF 导入再支持")
    raise ValueError("视觉体没有可识别的几何类型")


def collect_visual_parts(model: PetModel) -> list[VisualPart]:
    """遍历 URDF 的全部 <visual>,构建渲染用的零件表。"""
    palette = {m.name: tuple(m.color.rgba) for m in model.urdf.robot.materials if m.color}

    parts: list[VisualPart] = []
    for link_name, link in model.urdf.link_map.items():
        for visual in link.visuals:
            rgba = DEFAULT_COLOR
            if visual.material is not None:
                # 颜色可能内联在 visual 上,也可能只写了个名字、定义在 robot 顶层
                if visual.material.color is not None:
                    rgba = tuple(visual.material.color.rgba)
                else:
                    rgba = palette.get(visual.material.name, DEFAULT_COLOR)
            parts.append(
                VisualPart(
                    link=link_name,
                    local=np.eye(4) if visual.origin is None else np.array(visual.origin),
                    mesh=_primitive_to_mesh(visual.geometry),
                    rgba=rgba,
                )
            )
    return parts


class PetScene:
    """宠物的渲染场景。构造时建 actor,之后只调 set_configuration 更新姿态。"""

    def __init__(self, model: PetModel, plotter: pv.Plotter):
        self.model = model
        self.plotter = plotter
        self.parts = collect_visual_parts(model)
        self.actors = [
            plotter.add_mesh(
                part.mesh,
                color=part.rgba[:3],
                opacity=part.rgba[3],
                smooth_shading=True,
                specular=0.3,
                specular_power=15,
            )
            for part in self.parts
        ]
        self.set_configuration(model.neutral_cfg())

    def set_configuration(self, q: np.ndarray) -> None:
        """由 FK 算出各连杆位姿,再叠加视觉体的局部偏移,写进 actor 变换。"""
        transforms = link_transforms(self.model, q)
        for part, actor in zip(self.parts, self.actors, strict=True):
            actor.user_matrix = transforms[part.link] @ part.local

    def reset_camera(self) -> None:
        """固定一个 3/4 侧前方机位(+x 是宠物正面)。

        机位不是随手定的,是扫方位角量出来的:对每个关节测"转动它画面变化多少",
        取"最差关节变化量最大"的角度。太正面(≈0°)尾巴被躯干挡死,摆尾白做;
        太侧面(≈-70°)整条左臂被挡死。-40° 处最差关节仍有 0.9% 的画面变化,
        九个关节的动作全部可见。tests/test_render.py 会守住这个性质。
        """
        self.plotter.camera_position = [(0.881, -0.739, 0.30), (0.0, 0.0, 0.02), (0.0, 0.0, 1.0)]
        # 1.35 会让耳朵顶到画面上边缘被切掉,1.15 上下各留出约 7% 余量
        self.plotter.camera.zoom(1.15)


def render_rgba(
    model: PetModel,
    q: np.ndarray | None = None,
    size: tuple[int, int] = (400, 400),
) -> np.ndarray:
    """离屏渲染一帧,返回 (H, W, 4) 的 RGBA 数组,背景透明。

    L2 层的图像断言全部建立在这个函数上。
    """
    plotter = pv.Plotter(off_screen=True, window_size=list(size))
    try:
        scene = PetScene(model, plotter)
        scene.set_configuration(model.neutral_cfg() if q is None else q)
        scene.reset_camera()
        return np.asarray(plotter.screenshot(transparent_background=True, return_img=True))
    finally:
        plotter.close()
