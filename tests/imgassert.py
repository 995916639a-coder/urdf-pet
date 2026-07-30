"""L2:把"画面看起来对不对"翻译成可断言的数值。

这些断言是本项目对抗"假绿"的主力(见 CLAUDE.md)。其中
assert_images_differ 和 assert_images_stable 是互相咬合的一对:
一条防"该变的没变"(改了关节角画面却没更新),
一条防"不该变的乱变"(渲染不稳定,导致任何图像回归都失去意义)。
"""

from __future__ import annotations

import numpy as np


def assert_rgba(img: np.ndarray) -> None:
    assert img.ndim == 3 and img.shape[2] == 4, f"期望 (H, W, 4) 的 RGBA,实际 {img.shape}"
    assert img.dtype == np.uint8, f"期望 uint8,实际 {img.dtype}"


def foreground_mask(img: np.ndarray) -> np.ndarray:
    """alpha > 0 的像素即前景。"""
    return img[..., 3] > 0


def coverage(img: np.ndarray) -> float:
    """前景像素占整幅画面的比例。"""
    return float(foreground_mask(img).mean())


def foreground_bbox(img: np.ndarray) -> tuple[int, int, int, int]:
    """前景包围盒 (row0, col0, row1, col1),右下为开区间。无前景时报错。"""
    mask = foreground_mask(img)
    if not mask.any():
        raise AssertionError("画面里没有任何前景像素——大概率什么都没渲染出来")
    rows, cols = np.where(mask)
    return int(rows.min()), int(cols.min()), int(rows.max()) + 1, int(cols.max()) + 1


def assert_transparent_background(img: np.ndarray, margin: int = 4) -> None:
    """四角 margin×margin 的方块必须完全透明。

    这是 plan.md 第 7 节那个"全项目最大不确定点"(透明窗口里做 3D)的自动化版本。
    """
    assert_rgba(img)
    corners = {
        "左上": img[:margin, :margin, 3],
        "右上": img[:margin, -margin:, 3],
        "左下": img[-margin:, :margin, 3],
        "右下": img[-margin:, -margin:, 3],
    }
    for name, alpha in corners.items():
        peak = int(alpha.max())
        assert peak == 0, f"{name}角不透明(alpha 最大 {peak}),背景没有透出去"


def assert_within_canvas(img: np.ndarray, margin: int = 2) -> None:
    """宠物不能贴边——贴边说明被裁掉了或者相机太近。"""
    h, w = img.shape[:2]
    r0, c0, r1, c1 = foreground_bbox(img)
    assert r0 >= margin and c0 >= margin, f"前景贴到了左/上边界:bbox=({r0},{c0},{r1},{c1})"
    assert r1 <= h - margin and c1 <= w - margin, f"前景贴到了右/下边界:bbox=({r0},{c0},{r1},{c1})"


def assert_coverage_between(img: np.ndarray, lo: float, hi: float) -> None:
    """占比过小 = 缩成一个点或渲染失败;过大 = 糊满全屏。"""
    cov = coverage(img)
    assert lo <= cov <= hi, f"前景占比 {cov:.4f} 不在 [{lo}, {hi}] 内"


def diff_fraction(a: np.ndarray, b: np.ndarray) -> float:
    """两幅图有多少比例的像素不同。"""
    assert a.shape == b.shape, f"尺寸不一致:{a.shape} vs {b.shape}"
    return float(np.any(a != b, axis=-1).mean())


# 渲染的允许抖动上限。实测:240x240 下连续渲染 50 次,49 次逐像素一致,
# 有 1 次出现 3 个像素(0.005%)的差异——GPU 对边缘抗锯齿的处理并非逐位可复现。
# 因此不能断言 frac == 0(那样大约每 50 次假红一次)。
# 0.05% 的容差与"真实姿态变化"之间隔着一个数量级以上:
# 实测九个关节里变化最小的 elbow_l 也有 0.88% 的像素改变,不会混淆。
RENDER_JITTER = 0.0005


def assert_images_stable(a: np.ndarray, b: np.ndarray, tol: float = RENDER_JITTER) -> None:
    """同样的输入必须渲染出(近乎)同样的输出,否则图像回归失去意义。"""
    frac = diff_fraction(a, b)
    assert frac <= tol, f"两次渲染差异 {frac:.4%} 超出抖动容差 {tol:.4%},渲染不稳定"


def assert_images_differ(a: np.ndarray, b: np.ndarray, min_fraction: float = 0.005) -> None:
    """改了姿态,画面就必须真的变。专抓"状态变了但渲染没更新"这类静默失效。"""
    frac = diff_fraction(a, b)
    assert frac >= min_fraction, f"画面几乎没变(只有 {frac:.4%} 的像素不同),渲染可能没跟着更新"
