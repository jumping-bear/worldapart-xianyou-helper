# -*- coding: utf-8 -*-
"""解析 PyInstaller 一次性包的归档目录，列出打进去的模块。

PyInstaller 6.x 的 CArchive（都在文件尾部最后一屏内可定位）：
    cookie(28) + MAGIC(8) + python_libname(NUL 结尾) + toc_len(4) + TOC
    cookie = pkg_len(4) toc_off(4) toc_len(4) pyvers(4) cookie_len(4) 版本相关(4)
    TOC 条目 = entry_len(4) offset(4) clen(4) ulen(4) cflag(1) typecode(1) name

用途：核对"游戏目录里那份 仙友助手.exe"到底带了哪些模块，
      重点是 app.overlay（覆盖模式）在不在，以及和仓库当前源码是否一致。
"""
import os
import struct
import sys

MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"


def parse_carchive(path):
    data = open(path, "rb").read()
    magic = data.rfind(MAGIC)
    if magic < 0:
        raise SystemExit("找不到 MEI 魔数")
    cookie = data[magic - 28:magic]
    pkg_len, toc_off, toc_len, pyvers, cookie_len, _extra = struct.unpack("!IIIIII", cookie)
    pos = magic + 8
    end = data.index(b"\0", pos)
    libname = data[pos:end].decode("ascii", "replace")
    pos = end + 1
    toc_len2 = struct.unpack("!I", data[pos:pos + 4])[0]
    pos += 4
    toc = data[pos:pos + toc_len2]
    entries = []
    p = 0
    while p + 18 <= len(toc):
        entry_len = struct.unpack("!I", toc[p:p + 4])[0]
        if entry_len < 18 or p + entry_len > len(toc):
            break
        offset, clen, ulen = struct.unpack("!III", toc[p + 4:p + 16])
        cflag = toc[p + 16]
        typecode = chr(toc[p + 17])
        name = toc[p + 18:p + entry_len].decode("utf-8", "replace")
        entries.append({"name": name, "offset": offset, "clen": clen, "ulen": ulen,
                        "cflag": cflag, "type": typecode})
        p += entry_len
    return {"size": len(data), "pyvers": pyvers, "libname": libname,
            "pkg_len": pkg_len, "toc_len": toc_len2, "entries": entries}


def report(path):
    info = parse_carchive(path)
    entries = info["entries"]
    stat = {}
    for e in entries:
        stat[e["type"]] = stat.get(e["type"], 0) + 1
    pyz = [e for e in entries if e["type"] == "z"]
    print("=" * 72)
    print(os.path.basename(path) + "  " + path)
    print("  大小=%d  pyc版本=%d  运行库=%s  条目=%d" % (info["size"], info["pyvers"], info["libname"], len(entries)))
    print("  类型统计：%s" % stat)
    for e in pyz:
        print("  PYZ：%s  压缩=%d  原始=%d" % (e["name"], e["clen"], e["ulen"]))
    names = [e["name"] for e in entries]
    print("  含 overlay 的条目：%s" % ([n for n in names if "overlay" in n.lower()] or "（无）"))
    print("  顶层模块：%s" % ", ".join(n for n in names if "/" not in n and n.endswith(".pyc")))
    return info


if __name__ == "__main__":
    for path in sys.argv[1:]:
        if os.path.isfile(path):
            report(path)
        else:
            print("缺少文件：%s" % path)
