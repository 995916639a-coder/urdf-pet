"""可嵌入 Qt 的 3D 视图。

只有这个模块碰 Qt——scene.py 保持纯 PyVista,才能在 off_screen 下独立跑 L2 测试。
因此它**不**在 render/__init__.py 里导出:import urdf_pet.render 不应该把 Qt 拉进来。
"""

from __future__ import annotations

import numpy as np
from pyvistaqt import QtInteractor

from urdf_pet.kinematics.loader import PetModel
from urdf_pet.render.scene import PetScene


class PetViewport(QtInteractor):
    """一个显示宠物的 Qt 控件。对外只暴露 set_configuration。"""

    def __init__(self, model: PetModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.set_background("white")
        self.scene = PetScene(model, self)
        self.scene.reset_camera()
        self._q = model.neutral_cfg()

    @property
    def configuration(self) -> np.ndarray:
        return self._q.copy()

    def set_configuration(self, q: np.ndarray) -> None:
        self._q = self.model.clamp(q)
        self.scene.set_configuration(self._q)
        self.render()
