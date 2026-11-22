# -*- coding: utf-8 -*-
"""在 PyInstaller 打出的 exe 里查覆盖模式相关符号（用 mmap，避免整文件读成字符串）。

用法：python tools/scan_exe_strings.py <exe> [关键词...]
"""
import mmap
import sys

DEFAULT_KEYS = [
    b"app.overlay", b"run_overlay", b"watch_parent", b"RegisterHotKey",
    b"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", b"_await_page", b"xianyou_overlay_running",
    b"WS_EX_NOACTIVATE", b"overlay_compat", b"SetWindowPos", b"parent-pid",
    b"--overlay", b"show_after", b"xianyou_assistant", b"SW_SHOWNOACTIVATE",
]


def main(argv):
    if not argv:
        print("用法：python tools/scan_exe_strings.py <exe>")
        return 2
    path = argv[0]
    keys = [k.encode() if isinstance(k, str) else k for k in (argv[1:] or DEFAULT_KEYS)]
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        print("文件：%s  大小：%d" % (path, len(mm)))
        for key in keys:
            hits = []
            start = 0
            while len(hits) < 5:
                pos = mm.find(key, start)
                if pos < 0:
                    break
                hits.append(pos)
                start = pos + 1
            print("  %-40s %s" % (key.decode("ascii", "replace"), hits or "未找到"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
