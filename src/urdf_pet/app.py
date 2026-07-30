"""阶段 0 的交付物:一个普通带边框窗口,左边 3D 视图,右边每个关节一个滑块。

刻意不碰透明/置顶/点穿透——那些是阶段 2 的事(见 plan.md 第 4 节)。
"""

from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from urdf_pet.kinematics.loader import PetModel, load_model
from urdf_pet.render.viewport import PetViewport

SLIDER_STEPS = 1000


class JointSlider(QWidget):
    """一个关节一行:名字 + 滑块 + 当前弧度值。滑块整数刻度线性映射到关节限位。"""

    def __init__(self, name: str, lower: float, upper: float, on_change):
        super().__init__()
        self.name, self.lower, self.upper = name, lower, upper
        self._on_change = on_change

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setValue(self._to_steps(0.0))
        self.slider.valueChanged.connect(self._emit)

        self.value_label = QLabel()
        self.value_label.setMinimumWidth(56)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        name_label = QLabel(name)
        name_label.setMinimumWidth(84)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in (name_label, self.slider, self.value_label):
            layout.addWidget(w)
        self._refresh_label()

    def _to_steps(self, radians: float) -> int:
        frac = (radians - self.lower) / (self.upper - self.lower)
        return int(round(np.clip(frac, 0.0, 1.0) * SLIDER_STEPS))

    @property
    def radians(self) -> float:
        return self.lower + (self.upper - self.lower) * self.slider.value() / SLIDER_STEPS

    def set_radians(self, radians: float) -> None:
        self.slider.setValue(self._to_steps(radians))

    def _refresh_label(self) -> None:
        self.value_label.setText(f"{self.radians:+.2f}")

    def _emit(self) -> None:
        self._refresh_label()
        self._on_change()


class PetWindow(QMainWindow):
    """阶段 0 主窗口。"""

    def __init__(self, model: PetModel | None = None):
        super().__init__()
        self.model = model or load_model()
        self.setWindowTitle(f"urdf-pet —— {self.model.name}(阶段 0)")

        self.viewport = PetViewport(self.model)

        limits = self.model.limits
        self.sliders = [
            JointSlider(name, float(limits[i, 0]), float(limits[i, 1]), self._apply)
            for i, name in enumerate(self.model.actuated_names)
        ]

        reset = QPushButton("回到中立姿态")
        reset.clicked.connect(self.reset)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel(f"{self.model.dof} 个关节"))
        for s in self.sliders:
            panel_layout.addWidget(s)
        panel_layout.addWidget(reset)
        panel_layout.addStretch(1)
        panel.setFixedWidth(340)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.viewport, stretch=1)
        layout.addWidget(panel)
        self.setCentralWidget(central)
        self.resize(1000, 640)

        self._apply()

    @property
    def configuration(self) -> np.ndarray:
        """当前滑块对应的关节角向量,顺序同 model.actuated_names。"""
        return np.array([s.radians for s in self.sliders])

    def reset(self) -> None:
        for slider, value in zip(self.sliders, self.model.neutral_cfg(), strict=True):
            slider.set_radians(float(value))

    def _apply(self) -> None:
        self.viewport.set_configuration(self.configuration)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = PetWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
