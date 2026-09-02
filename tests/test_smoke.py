"""冒烟测试：保证骨架仓库开箱即绿（make test 至少有 1 个用例通过）。"""

import src


def test_package_importable():
    assert src.__version__  # 包可导入且版本号存在
