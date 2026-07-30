"""L4:启动真窗口 → 截图 → 人(或 Claude)亲眼看。

这一层回答 L0–L3 回答不了的问题:它好看吗?透明是不是真透?姿态自然吗?

    python scripts/visual_check.py                 # 中立姿态
    python scripts/visual_check.py --pose wave     # 预设姿态
    python scripts/visual_check.py --full          # 连桌面一起截(验证合成效果)

截图落在 screenshots/(已 gitignore)。--full 会拍到真实桌面内容,
只在需要验证"宠物与桌面背景的合成"时才用。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from urdf_pet.app import PetWindow

OUT_DIR = Path(__file__).resolve().parents[1] / "screenshots"

# 几个便于目视检查的预设姿态(关节名 → 弧度)
POSES: dict[str, dict[str, float]] = {
    "neutral": {},
    "wave": {"shoulder_l": -1.6, "elbow_l": -1.1, "neck_tilt": -0.25, "tail": 0.6},
    "sit": {"hip_l": 1.0, "hip_r": 1.0, "neck_tilt": 0.3, "tail": -0.4},
    "extremes": {},  # 全部关节推到上限,用来看有没有穿模
}


def build_configuration(model, pose: str) -> np.ndarray:
    if pose == "extremes":
        return model.limits[:, 1].copy()
    q = model.neutral_cfg()
    for name, value in POSES[pose].items():
        q[model.actuated_names.index(name)] = value
    return model.clamp(q)


def _x11grab(path: Path, region: str | None = None) -> None:
    """用 ffmpeg 抓 X11 的真实合成像素。region 形如 "1000x640+120+80"。"""
    cmd = ["ffmpeg", "-loglevel", "error", "-f", "x11grab"]
    if region:
        size, x, y = region.split("+")[0], *region.split("+")[1:]
        cmd += ["-video_size", size, "-i", f":0.0+{x},{y}"]
    else:
        cmd += ["-i", ":0.0"]
    subprocess.run([*cmd, "-frames:v", "1", "-y", str(path)], check=True)


def grab_window(window, path: Path) -> None:
    """只抓宠物窗口所占的屏幕矩形,不拍到桌面上的其它内容。

    不能用 QWidget.grab():QtInteractor 的 3D 内容画在原生 OpenGL 表面上,
    Qt 的控件级抓图取不到,结果是一块纯黑。必须走 X11 抓真实合成结果。
    """
    g = window.frameGeometry()
    _x11grab(path, f"{g.width()}x{g.height()}+{g.x()}+{g.y()}")


def grab_screen(path: Path) -> None:
    """整屏截图。会拍到真实桌面内容,只在验证合成效果时使用。"""
    _x11grab(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pose", default="neutral", choices=sorted(POSES))
    parser.add_argument("--full", action="store_true", help="截整个屏幕而不是只截窗口")
    parser.add_argument("--keep-open", action="store_true", help="截完不退出,留着手动看")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{args.pose}{'_full' if args.full else ''}.png"

    app = QApplication.instance() or QApplication(sys.argv)
    window = PetWindow()
    window.show()

    def shoot():
        # 直接推滑块,让信号链自己驱动渲染——这和用户真实操作的路径完全一致。
        # (早先的写法是先设 viewport 再 blockSignals 同步滑块,结果把刷新读数的
        #  回调一起挡掉了,截出来九个关节全显示 +0.00。)
        for slider, value in zip(
            window.sliders, build_configuration(window.model, args.pose), strict=True
        ):
            slider.set_radians(float(value))
        window.raise_()
        window.activateWindow()
        app.processEvents()
        grab_screen(out) if args.full else grab_window(window, out)
        print(f"已保存 {out}")
        if not args.keep_open:
            app.quit()

    # 等窗口真正映射到屏幕上再截,否则可能抓到一片空白
    QTimer.singleShot(1200, shoot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
