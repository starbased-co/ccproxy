# Type stubs for psutil
from typing import NamedTuple

class Memory(NamedTuple):
    rss: int
    vms: int
    shared: int
    text: int
    lib: int
    data: int
    dirty: int

class Process:
    def __init__(self, pid: int) -> None: ...
    def cpu_percent(self, interval: float | None = None) -> float: ...
    def memory_info(self) -> Memory: ...
    def create_time(self) -> float: ...

class NoSuchProcess(Exception): ...  # noqa: N818

def pid_exists(pid: int) -> bool: ...
