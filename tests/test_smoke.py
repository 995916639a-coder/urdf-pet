"""占位测试:确认包可导入。阶段 0 起会被 test_kinematics.py 等替换。"""

import urdf_pet


def test_import():
    assert urdf_pet.__version__
