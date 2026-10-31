"""把所有用例的「今天」钉在 2026-10-31。

不钉的话，一过零点就会红一片：数据都写在 10-31，而 ``get_today()`` 返回 11-01，
``has_record`` 立刻变 False。2026-11-01 凌晨真的红过一次，排查了半天才发现
不是代码坏了，是测试自己太依赖真实时钟。

演示时同理：启动命令必须带 ``HAMSTER_TODAY=2026-10-31``，否则过了 0 点，
首页会从「今天 82 分钟」变成「今天还没记录」。
"""
import pytest

from app import main


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    monkeypatch.setattr(main, "_PINNED_TODAY", "2026-10-31")
