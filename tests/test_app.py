"""L3:Qt 冒烟。需要一个 X 显示(本机 :0,CI 里用 xvfb)。

这一层只验证一件事:**信号链是通的**——滑块动了,运动学状态和渲染变换都跟着变了。
"好不好看"不归这层管,归 L4(scripts/visual_check.py)。
"""

import numpy as np
import pytest

pytest.importorskip("PySide6", reason="Qt 测试需要 [desktop] 依赖")
pytest.importorskip("pyvistaqt")

from PySide6.QtWidgets import QApplication  # noqa: E402

from urdf_pet.app import SLIDER_STEPS, PetWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    w = PetWindow()
    yield w
    w.viewport.close()
    w.close()


def test_window_builds_one_slider_per_joint(window):
    assert len(window.sliders) == window.model.dof
    assert [s.name for s in window.sliders] == list(window.model.actuated_names)


def quantization_tolerance(model) -> float:
    """滑块是 SLIDER_STEPS 级整数刻度,任何角度都会被吸附到最近的刻度上。

    最大误差是最宽关节量程的半格(约 1.2e-3 rad,肉眼不可见)。
    断言必须容忍它,否则测试是在挑剔一个不存在的缺陷。
    """
    span = float((model.limits[:, 1] - model.limits[:, 0]).max())
    return span / SLIDER_STEPS


def test_starts_at_neutral(window):
    np.testing.assert_allclose(
        window.configuration, window.model.neutral_cfg(), atol=quantization_tolerance(window.model)
    )


def test_slider_extremes_map_to_joint_limits(window):
    lim = window.model.limits
    for i, slider in enumerate(window.sliders):
        slider.slider.setValue(0)
        assert slider.radians == pytest.approx(lim[i, 0])
        slider.slider.setValue(SLIDER_STEPS)
        assert slider.radians == pytest.approx(lim[i, 1])


def test_slider_drives_kinematics(window):
    """核心断言:动滑块 → viewport 里的关节角真的变了。

    这条断的是信号链,不是渲染像素——像素归 L2/L4。
    """
    tol = quantization_tolerance(window.model)
    limits = window.model.limits
    for i, slider in enumerate(window.sliders):
        window.reset()
        # 目标取各关节自己量程的 70% 处,而不是统一的某个弧度值——
        # 肘关节限位是 [-2.20, 0.20],统一用 0.5 会被夹住,那样测的是 clamp 不是信号链
        target = float(limits[i, 0] + 0.70 * (limits[i, 1] - limits[i, 0]))
        slider.set_radians(target)

        assert slider.radians == pytest.approx(target, abs=tol), f"{slider.name} 滑块读数不对"
        np.testing.assert_allclose(window.viewport.configuration, window.configuration, atol=1e-12)
        assert window.viewport.configuration[i] == pytest.approx(target, abs=tol)


def test_slider_updates_actor_transform(window):
    """再往下一层:关节角变了,渲染 actor 的变换矩阵也必须变。

    这里抓的是"状态更新了但 actor 忘了刷新"——L2 用像素抓同一件事,
    这里用矩阵抓,不依赖 GPU,所以在没有渲染能力的环境里也拦得住。
    """
    scene = window.viewport.scene
    index = {part.link: i for i, part in enumerate(scene.parts)}
    before = scene.actors[index["head_link"]].user_matrix.copy()

    window.sliders[window.model.actuated_names.index("neck_pan")].set_radians(0.8)

    after = scene.actors[index["head_link"]].user_matrix
    assert not np.allclose(before, after), "转了脖子,头部 actor 的变换却没变"


def test_reset_returns_to_neutral(window):
    for slider in window.sliders:
        slider.set_radians(0.4)
    window.reset()
    np.testing.assert_allclose(
        window.configuration, window.model.neutral_cfg(), atol=quantization_tolerance(window.model)
    )
