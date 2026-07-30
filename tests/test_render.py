"""L2:离屏渲染断言。不需要显示器(VTK 会退回 EGL/OSMesa)。"""

import numpy as np
import pytest

from urdf_pet.kinematics import load_model

pytest.importorskip("pyvista", reason="渲染测试需要 [desktop] 依赖")

from imgassert import (  # noqa: E402
    assert_coverage_between,
    assert_images_differ,
    assert_images_stable,
    assert_transparent_background,
    assert_within_canvas,
    foreground_bbox,
)
from urdf_pet.render import render_rgba  # noqa: E402

SIZE = (240, 240)


@pytest.fixture(scope="module")
def model():
    return load_model()


@pytest.fixture(scope="module")
def neutral(model):
    return render_rgba(model, size=SIZE)


def test_renders_rgba_of_expected_size(neutral):
    assert neutral.shape == (SIZE[1], SIZE[0], 4)
    assert neutral.dtype == np.uint8


def test_background_is_transparent(neutral):
    assert_transparent_background(neutral)


def test_pet_is_visible_and_framed(neutral):
    # 占比区间放得比较宽,只拦"缩成一点"和"糊满全屏"两类灾难,不锁死构图
    assert_coverage_between(neutral, 0.08, 0.60)
    assert_within_canvas(neutral)


def test_pet_is_roughly_upright(neutral):
    """站立的生物应该是高的:包围盒高度必须大于宽度。"""
    r0, c0, r1, c1 = foreground_bbox(neutral)
    assert (r1 - r0) > (c1 - c0), f"包围盒 {r1 - r0}x{c1 - c0} 不像一只站着的生物"


def test_render_is_stable(model, neutral):
    """渲染必须稳定,否则后续任何图像回归都失去意义。

    容差不是零:实测 GPU 边缘抗锯齿约每 50 帧会抖动几个像素,
    详见 imgassert.RENDER_JITTER 的说明。"""
    assert_images_stable(neutral, render_rgba(model, size=SIZE))


@pytest.mark.parametrize(
    "joint",
    [
        "neck_pan",
        "neck_tilt",
        "shoulder_l",
        "elbow_l",
        "shoulder_r",
        "elbow_r",
        "hip_l",
        "hip_r",
        "tail",
    ],
)
def test_moving_each_joint_changes_the_image(model, neutral, joint):
    """逐个关节确认渲染真的跟着动。

    这条有双重作用:
    1. 反假绿——FK 算对了、状态更新了,但 actor 变换忘了刷新,
       单测全绿而画面纹丝不动,只有这条能抓到;
    2. 守住默认机位的可见性——如果有人把相机转到某个角度,
       导致整条左臂或尾巴被躯干挡死,这里会红。那种机位下宠物做动作
       用户根本看不见,等于白做。
    """
    q = model.neutral_cfg()
    q[model.actuated_names.index(joint)] = 0.5
    assert_images_differ(neutral, render_rgba(model, q, size=SIZE))


def test_mesh_geometry_is_rejected_for_now():
    """阶段 3 之前遇到 mesh 视觉体要明确报错,而不是静默画出个空场景。"""
    from urdf_pet.render.scene import _primitive_to_mesh

    class _Empty:
        box = cylinder = sphere = None
        mesh = object()

    with pytest.raises(NotImplementedError):
        _primitive_to_mesh(_Empty())
