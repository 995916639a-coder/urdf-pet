"""起一个滑块预览窗口,调手感用。

python scripts/dev_preview.py                       # 内置的 blob
python scripts/dev_preview.py path/to/other.urdf    # 换一副身体
"""

import sys

from urdf_pet.app import PetWindow
from urdf_pet.kinematics.loader import DEFAULT_URDF, load_model


def main() -> int:
    from PySide6.QtWidgets import QApplication

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URDF
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = PetWindow(load_model(path))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
