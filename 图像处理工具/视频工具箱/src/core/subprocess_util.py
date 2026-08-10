"""统一管理 ffmpeg 等子进程：退出工具箱时自动结束，避免占用文件。"""

from __future__ import annotations

import atexit
import subprocess
import sys
from typing import Any, List

from .config import SUBPROCESS_CREATE_NO_WINDOW

_active_procs: List[subprocess.Popen] = []
_job_handle: int | None = None
_job_initialized = False

# Windows Job：父进程/Job 句柄关闭时终止其内所有子进程
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


def _init_windows_job() -> None:
    global _job_handle, _job_initialized
    if _job_initialized or sys.platform != "win32":
        _job_initialized = True
        return
    _job_initialized = True
    try:
        import ctypes
        from ctypes import wintypes

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            kernel32.CloseHandle(handle)
            return
        _job_handle = handle
    except Exception:
        _job_handle = None


def _assign_to_job(proc: subprocess.Popen) -> None:
    if sys.platform != "win32" or not _job_handle:
        return
    try:
        import ctypes

        ctypes.windll.kernel32.AssignProcessToJobObject(
            _job_handle, int(proc._handle)
        )
    except Exception:
        pass


def init_process_job() -> None:
    """应用启动时调用一次。"""
    _init_windows_job()


def tracked_popen(*args: Any, **kwargs: Any) -> subprocess.Popen:
    """创建受跟踪的子进程；关闭工具箱时会终止仍在运行的进程。"""
    flags = kwargs.pop("creationflags", 0)
    if sys.platform == "win32":
        flags |= SUBPROCESS_CREATE_NO_WINDOW
    proc = subprocess.Popen(*args, creationflags=flags, **kwargs)
    _active_procs.append(proc)
    _assign_to_job(proc)
    return proc


def _prune_finished() -> None:
    global _active_procs
    _active_procs = [p for p in _active_procs if p.poll() is None]


def terminate_all_tracked_processes() -> None:
    """终止所有仍在运行的受跟踪子进程（关闭窗口或进程退出时）。"""
    _prune_finished()
    for proc in list(_active_procs):
        if proc.poll() is not None:
            continue
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in list(_active_procs):
        if proc.poll() is not None:
            continue
        # 关闭管道以解除读取线程的阻塞
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        try:
            if proc.stderr:
                proc.stderr.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _active_procs.clear()


def get_media_duration(path: str) -> float | None:
    """用 ffprobe 获取视频时长（秒），失败返回 None。"""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        creationflags=SUBPROCESS_CREATE_NO_WINDOW,
    )
    try:
        return float(proc.stdout.strip())
    except Exception:
        return None


atexit.register(terminate_all_tracked_processes)

__all__ = [
    "init_process_job",
    "tracked_popen",
    "terminate_all_tracked_processes",
    "get_media_duration",
]
