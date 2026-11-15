"""Process-local memory guards. Called only inside the OCR-enabled parser child."""

import os

_windows_job = None


class ResourceLimitError(ValueError):
    pass


def apply_memory_limit(megabytes: int):
    limit = megabytes * 1024 * 1024
    try:
        if os.name == "nt":
            _windows_memory_limit(limit)
        else:
            import resource

            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            cap = limit if hard == resource.RLIM_INFINITY else min(limit, hard)
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except (OSError, ValueError):
        raise ResourceLimitError(
            "OCR process memory limits could not be applied; check OS process restrictions"
        ) from None


def _windows_memory_limit(limit: int):
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ExtendedLimits()
    # Both the parser and its OCR descendants share a bounded Windows job.
    info.BasicLimitInformation.LimitFlags = 0x100 | 0x200 | 0x2000  # KILL_ON_JOB_CLOSE
    info.ProcessMemoryLimit = info.JobMemoryLimit = limit
    try:
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    except Exception:
        kernel.CloseHandle(job)
        raise
    # Retain this handle for the parser lifetime; the OS closes it on process exit.
    global _windows_job
    _windows_job = job
