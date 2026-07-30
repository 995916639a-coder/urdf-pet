"""3D 渲染。刻意不 import desktop/,渲染必须能脱离桌面壳单独跑(见 CLAUDE.md)。"""

from urdf_pet.render.scene import PetScene, render_rgba

__all__ = ["PetScene", "render_rgba"]
