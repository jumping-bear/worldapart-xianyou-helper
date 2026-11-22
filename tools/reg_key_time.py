# -*- coding: utf-8 -*-
"""读取注册表键的最后写入时间，用于判断 TdrDelay 是什么时候被改的。"""
import ctypes
import ctypes.wintypes as wt
import datetime
import sys

advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

HKEY_LOCAL_MACHINE = 0x80000002
KEY_READ = 0x20019


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


def key_last_write(root, path):
    handle = wt.HKEY()
    rc = advapi32.RegOpenKeyExW(wt.HKEY(root), path, 0, KEY_READ, ctypes.byref(handle))
    if rc != 0:
        return None, rc
    try:
        ft = FILETIME()
        rc = advapi32.RegQueryInfoKeyW(
            handle, None, None, None, None, None, None, None, None, None, None, ctypes.byref(ft))
        if rc != 0:
            return None, rc
        ticks = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        # FILETIME -> 本地时间
        epoch = datetime.datetime(1601, 1, 1)
        dt = epoch + datetime.timedelta(microseconds=ticks // 10)
        return dt + (datetime.datetime.now() - datetime.datetime.utcnow()), 0
    finally:
        advapi32.RegCloseKey(handle)


def main():
    paths = [
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"),
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Configuration"),
        (HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\amdkmdag"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\GraphicsDrivers"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\GraphicsDrivers"),
    ]
    for root, path in paths:
        when, rc = key_last_write(root, path)
        if when is None:
            print("%-70s 读取失败 rc=%s" % (path, rc))
        else:
            print("%-70s 最后写入 %s" % (path, when.strftime("%Y-%m-%d %H:%M:%S")))


if __name__ == "__main__":
    sys.exit(main())
