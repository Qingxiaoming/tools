"""跨平台文件独占锁（防止多实例并发写同一文件）。"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Iterator


@contextlib.contextmanager
def exclusive_file_lock(lock_path: Path) -> Iterator[None]:
    """对 lock_path 获取非阻塞独占锁；被占用时抛出 TimeoutError。

    POSIX 用 fcntl.flock，Windows 用 msvcrt.locking；进程退出时系统自动释放。
    """
    lock_path = Path(lock_path)
    if sys.platform == "win32":
        import msvcrt

        f = open(lock_path, "a+b")
        try:
            f.seek(0, 2)
            if f.tell() == 0:
                f.write(b"x")
                f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            raise TimeoutError("lock busy") from None
        try:
            yield
        finally:
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            f.close()
    else:
        import fcntl

        f = open(lock_path, "a+")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            raise TimeoutError("lock busy") from None
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()
