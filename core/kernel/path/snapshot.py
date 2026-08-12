"""
IBCI SnapshotLayout — 快照资产外化布局策略（canonical）。

集中化"save_state 的资产外化到哪个目录、如何命名"的布局决策。
"""
from __future__ import annotations

from core.base.path import IbPath


class SnapshotLayout:
    """
    快照资产外化布局（策略集中化）。

    本类把这些布局决策集中，便于未来统一调整（如改为 project_root/.cache/<hash>）。
    """

    @staticmethod
    def asset_dir_for(save_path: IbPath) -> IbPath:
        """资产外化目录：save_path 的同级 ``.assets`` 目录。

        实现为字符串拼接再包 IbPath——刻意避开 ``IbPath.__add__``（其语义是路径 join，
        ``save_path + ".assets"`` 会产出 ``save_path/.assets`` 子目录而非同级目录）。
        """
        return IbPath.from_native(save_path.to_native() + ".assets")

    @staticmethod
    def asset_file(asset_dir: IbPath, uid: str) -> IbPath:
        """单个资产文件路径（uid + .txt 扩展名）。"""
        return asset_dir / f"{uid}.txt"
