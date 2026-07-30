"""L1:运动学单测。

核心是 test_fk_matches_yourdfpy —— 自写的 numpy FK 必须和 yourdfpy 自带的场景图
算出同一组位姿。两套独立实现对拍才叫验证;自己的结果喂自己的断言只是复述。
"""

import numpy as np
import pytest

from urdf_pet.kinematics import link_transforms, load_model
from urdf_pet.kinematics.fk import rotation_about_axis


@pytest.fixture(scope="module")
def model():
    return load_model()


def random_cfgs(model, n=12, seed=0):
    """在限位内随机采样 n 组关节角(含边界与全零)。"""
    rng = np.random.default_rng(seed)
    lim = model.limits
    samples = [np.zeros(model.dof), lim[:, 0].copy(), lim[:, 1].copy()]
    samples += [rng.uniform(lim[:, 0], lim[:, 1]) for _ in range(n)]
    return samples


# ---------- 结构 ----------


def test_model_structure(model):
    assert model.name == "blob"
    assert model.root_link == "base_link"
    assert model.dof == 9
    assert model.actuated_names[:2] == ("neck_pan", "neck_tilt")
    assert len(model.link_names) == 10


def test_all_links_reachable_from_root(model):
    # link_transforms 内部会对未连通的连杆报错,这里断言 10 个连杆全部算得出来
    assert set(link_transforms(model)) == set(model.link_names)


def test_limits_are_finite_and_ordered(model):
    lim = model.limits
    assert np.all(np.isfinite(lim))
    assert np.all(lim[:, 0] < lim[:, 1])


# ---------- 与 yourdfpy 对拍 ----------


def test_fk_matches_yourdfpy(model):
    for q in random_cfgs(model):
        mine = link_transforms(model, q)
        model.urdf.update_cfg(q)
        for link in model.link_names:
            theirs = model.urdf.get_transform(link, model.root_link)
            np.testing.assert_allclose(
                mine[link], theirs, atol=1e-9, err_msg=f"连杆 {link} 在 q={q} 处不一致"
            )


def test_fk_is_rigid(model):
    """每个位姿都必须是合法的刚体变换:旋转块正交、行列式为 +1、底行为 [0,0,0,1]。"""
    for q in random_cfgs(model, n=4, seed=1):
        for link, T in link_transforms(model, q).items():
            R = T[:3, :3]
            np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12, err_msg=link)
            assert np.isclose(np.linalg.det(R), 1.0), link
            np.testing.assert_allclose(T[3], [0, 0, 0, 1], atol=1e-12)


# ---------- 反作弊:FK 必须真的随 q 变化 ----------


def test_each_joint_moves_its_subtree(model):
    """逐个关节验证:动它,它的子树必须动,且只有子树动。

    这条防的是"FK 写成了常量"或"关节接错了父子"这类错误——
    整体对拍能过、但单关节响应错位的 bug,只有这样逐个戳才抓得到。
    """
    base = link_transforms(model, model.neutral_cfg())
    subtree = {
        "neck_pan": {"neck_link", "head_link"},
        "neck_tilt": {"head_link"},
        "shoulder_l": {"upperarm_l", "forearm_l"},
        "elbow_l": {"forearm_l"},
        "shoulder_r": {"upperarm_r", "forearm_r"},
        "elbow_r": {"forearm_r"},
        "hip_l": {"thigh_l"},
        "hip_r": {"thigh_r"},
        "tail": {"tail_link"},
    }
    for i, name in enumerate(model.actuated_names):
        q = model.neutral_cfg()
        q[i] = 0.4  # 落在所有关节限位内
        moved = link_transforms(model, q)
        for link in model.link_names:
            changed = not np.allclose(base[link], moved[link], atol=1e-12)
            if link in subtree[name]:
                assert changed, f"动 {name} 时 {link} 没有跟着动"
            else:
                assert not changed, f"动 {name} 时不该动的 {link} 动了"


# ---------- 工具函数与限位 ----------


def test_rotation_about_axis_known_values():
    z90 = rotation_about_axis(np.array([0.0, 0.0, 1.0]), np.pi / 2)
    np.testing.assert_allclose(z90 @ [1, 0, 0], [0, 1, 0], atol=1e-12)
    np.testing.assert_allclose(
        rotation_about_axis(np.array([0.0, 1.0, 0.0]), 0.0), np.eye(3), atol=1e-12
    )


def test_clamp_respects_limits(model):
    lim = model.limits
    assert np.all(model.clamp(np.full(model.dof, 1e3)) == lim[:, 1])
    assert np.all(model.clamp(np.full(model.dof, -1e3)) == lim[:, 0])
    assert np.all(np.isfinite(model.neutral_cfg()))


def test_wrong_shape_rejected(model):
    with pytest.raises(ValueError):
        link_transforms(model, np.zeros(model.dof + 1))
