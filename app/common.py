# -*- coding: utf-8 -*-
"""共享常量、配置读写、存档定位与通用工具。"""
import glob
import os
import re
import sys

import meta_update

from . import version

APP_VERSION = version.VERSION
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    HERE = os.path.dirname(sys.executable)
    BUILTIN_DIR = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BUILTIN_DIR = HERE
CFG = os.path.join(HERE, "config.json")
OUT_HTML = os.path.join(HERE, "仙友助手.html")
OUT_VERSION = os.path.join(HERE, "仙友助手版本.js")


def _writable(directory):
    """目录当前用户是否可写（用于识别 C:\\ 根、Program Files 等需要提权的位置）。"""
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".write_probe_%d" % os.getpid())
        with open(probe, "wb") as f:
            f.write(b"1")
        os.remove(probe)
        return True
    except OSError:
        return False


if FROZEN and not _writable(HERE):
    # exe 放在只读目录（C:\ 根、Program Files 等）时，config.json 与页面写不进去会报
    # PermissionError；改写到用户目录，与缓存同根，避免要求管理员权限。
    _data = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                         "WorldApartTouchProgress")
    if _writable(_data):
        CFG = os.path.join(_data, "config.json")
        OUT_HTML = os.path.join(_data, "仙友助手.html")
        OUT_VERSION = os.path.join(_data, "仙友助手版本.js")


def set_output_dir(directory):
    """把页面生成物重定向到指定目录。

    默认仍写仓库根（开发预览）；发布由 tools/release.py 指向 仙友助手/，
    避免开发预览与发布产物互相覆盖。
    """
    global OUT_HTML, OUT_VERSION
    target = os.path.abspath(directory or HERE)
    os.makedirs(target, exist_ok=True)
    OUT_HTML = os.path.join(target, "仙友助手.html")
    OUT_VERSION = os.path.join(target, "仙友助手版本.js")
    return target


DEFAULT_MODULES = {"bedroom": True, "talent": True, "items": True, "pill": True,
                   "forge": True, "event": True, "quest": True}

unpack = meta_update.unpack


# ---------------- 配置与存档定位 ----------------
STEAM_APPID_A1 = 4209920  # 不问凡尘的 Steam AppID


def _module_defaults():
    """老模块 + 插件模块的默认开关：新增模块默认开启，无需改这里。"""
    defaults = dict(DEFAULT_MODULES)
    try:
        from . import registry
        for spec in registry.MODULES:
            defaults.setdefault(spec.KEY, True)
    except Exception:
        pass
    return defaults


def load_cfg():
    raw = meta_update._read_json(CFG, {}) or {}
    modules = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    return {
        "decrypted_dir": str(raw.get("decrypted_dir") or ""),
        "game_dir": str(raw.get("game_dir") or ""),
        "save_file": str(raw.get("save_file") or ""),
        "modules": {name: bool(modules.get(name, default))
                    for name, default in _module_defaults().items()},
    }


def save_cfg(cfg):
    raw = meta_update._read_json(CFG, {}) or {}
    modules = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    modules = dict(modules)
    for name, default in _module_defaults().items():
        modules[name] = bool((cfg.get("modules") or {}).get(name, default))
    data = {
        "decrypted_dir": cfg.get("decrypted_dir", ""), "game_dir": cfg.get("game_dir", ""),
        "save_file": cfg.get("save_file", ""), "modules": modules,
    }
    try:
        meta_update._atomic_json(CFG, data)
        return True
    except Exception as e:
        print("配置保存失败：%s" % e)
        return False


def _read_registry_value(key_path, value_name):
    """尝试读取 Windows 注册表值（Python 3 原生实现，不走 winreg 导入）。"""
    try:
        import winreg
        key_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM64": winreg.HKEY_LOCAL_MACHINE,
        }
        hive = key_map.get(key_path.split("\\")[0])
        if hive is None:
            return None
        subkey = "\\".join(key_path.split("\\")[1:])
        access = winreg.KEY_READ | (winreg.KEY_WOW64_64KEY if key_path.startswith("HKLM64") else 0)
        try:
            handle = winreg.OpenKey(hive, subkey, 0, access)
        except OSError:
            try:
                handle = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
            except OSError:
                return None
        try:
            val, _ = winreg.QueryValueEx(handle, value_name)
            return str(val) if val else None
        finally:
            winreg.CloseKey(handle)
    except Exception:
        return None


def _find_steam_libs():
    """扫描所有 Steam 库目录。"""
    libs = set()
    # 1. 注册表找 Steam 安装目录
    for reg_key in [r"HKLM64\SOFTWARE\Valve\Steam", r"HKLM\SOFTWARE\Valve\Steam",
                    r"HKLM64\SOFTWARE\WOW6432Node\Valve\Steam",
                    r"HKCU\SOFTWARE\Valve\Steam"]:
        for value_name in ("InstallPath", "SteamPath"):
            p = _read_registry_value(reg_key, value_name)
            if p and os.path.isdir(p):
                libs.add(os.path.normpath(p))
                # 读 libraryfolders.vdf
                vdf = os.path.join(p, "steamapps", "libraryfolders.vdf")
                if os.path.isfile(vdf):
                    try:
                        with open(vdf, encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        for m in re.finditer(r'"path"\s+"([^"]+)"', content):
                            lp = m.group(1).replace("\\\\", "\\")
                            if os.path.isdir(lp):
                                libs.add(os.path.normpath(lp))
                    except Exception:
                        pass
    # 2. 硬编码常见路径兜底
    for drive in "CDEFGH":
        for suffix in [r"SteamLibrary", r"Program Files\Steam", r"Program Files (x86)\Steam"]:
            p = drive + ":\\" + suffix
            if os.path.isdir(p):
                libs.add(os.path.normpath(p))
    return list(libs)


def _find_game_dir():
    """自动定位不问凡尘（WorldApart.exe / A1 目录）的安装位置。"""
    # 优先：所有 Steam 库里的 steamapps\common\A1
    for lib in _find_steam_libs():
        candidate = os.path.join(lib, "steamapps", "common", "A1")
        wa = os.path.join(candidate, "WorldApart.exe")
        if os.path.isfile(wa):
            return os.path.normpath(candidate)
    # 兜底：扫描 exe 同目录及上级的 A1
    for candidate in [os.path.join(HERE, "A1"), os.path.join(HERE, "..", "A1"),
                      os.path.join(HERE, "..", "..", "A1")]:
        if os.path.isfile(os.path.join(candidate, "WorldApart.exe")):
            return os.path.normpath(candidate)
    return ""


def find_dir(cfg, interactive=True):
    """定位 BepInEx\\decrypted 目录，返回路径（空字符串表示失败）。"""
    configured = (cfg.get("decrypted_dir") or "").strip()
    if configured and os.path.isdir(configured):
        return configured

    # ---- 先确保 game_dir 有值 ----
    game_dir = (cfg.get("game_dir") or "").strip()
    if not game_dir or not os.path.isfile(os.path.join(game_dir, "WorldApart.exe")):
        found = _find_game_dir()
        if found:
            game_dir = found
            cfg["game_dir"] = game_dir

    # ---- 从 game_dir 推断 decrypted ----
    if game_dir:
        # 常见情况：游戏目录\BepInEx\decrypted
        candidate = os.path.join(game_dir, "BepInEx", "decrypted")
        if os.path.isdir(candidate) and glob.glob(os.path.join(candidate, "*gameworld*")):
            cfg["decrypted_dir"] = os.path.normpath(candidate)
            save_cfg(cfg)
            return cfg["decrypted_dir"]
        # 目录存在但还没存档（玩家没启动过游戏）
        if os.path.isdir(candidate):
            # 还是存下来，下次启动就有了
            cfg["decrypted_dir"] = os.path.normpath(candidate)
            save_cfg(cfg)
            if interactive:
                print("找到 decrypted 目录了，但里面还没有存档副本。")
                print("请先启动游戏，停在主菜单约 20 秒，让插件导出存档。")
                print("然后重新运行仙友助手.exe 就行。")
            return cfg["decrypted_dir"]  # 暂时返回，下次存档就有了
        # BepInEx 目录都不存在 → 玩家没跑一键安装
        bepinex = os.path.join(game_dir, "BepInEx")
        if not os.path.isdir(bepinex) and interactive:
            print("★ 找到游戏目录了（%s），但还没装 BepInEx 插件！" % game_dir)
            print("请先运行仙友助手文件夹里的「一键安装.bat」，")
            print("它会自动安装插件并写好配置。装完后启动游戏停 20 秒，再回来。")
        elif interactive:
            # BepInEx 存在但 decrypted 目录不存在 → 玩家没启动过游戏
            print("BepInEx 插件目录存在，但 decrypted 文件夹还没生成。")
            print("请启动游戏，停在主菜单约 20 秒，让插件导出存档。")
        return ""

    # ---- 没找到 game_dir，尝试自动扫盘 ----
    print("正在自动扫描 Steam 游戏目录……")
    found = _find_game_dir()
    if found:
        cfg["game_dir"] = found
        dec_candidate = os.path.join(found, "BepInEx", "decrypted")
        if os.path.isdir(dec_candidate) and glob.glob(os.path.join(dec_candidate, "*gameworld*")):
            cfg["decrypted_dir"] = os.path.normpath(dec_candidate)
            save_cfg(cfg)
            return cfg["decrypted_dir"]
        elif os.path.isdir(dec_candidate):
            cfg["decrypted_dir"] = os.path.normpath(dec_candidate)
            save_cfg(cfg)
            if interactive:
                print("★ 找到游戏目录和 decrypted 文件夹了，但里面还没有存档。")
                print("请先启动游戏，停在主菜单约 20 秒。")
            return cfg["decrypted_dir"]
        else:
            cfg["decrypted_dir"] = os.path.normpath(dec_candidate)
            save_cfg(cfg)
            if interactive:
                print("★ 找到游戏目录了（%s），但还没装插件。" % found)
                print("请先运行「一键安装.bat」，然后启动游戏停 20 秒。")
            return ""

    # ---- 全部自动检测失败，交互式引导 ----
    if not interactive:
        return ""

    print()
    print("── 自动检测失败，需要手动指定 ──")
    print("我没能在常见位置自动找到你的游戏。请在 Steam 库里右键「不问凡尘」")
    print("→ 管理 → 浏览本地文件，打开后把地址栏里的路径复制过来（A1 文件夹）。")
    print()
    path = input("把不问凡尘的游戏文件夹路径粘贴到这里: ").strip().strip('"').strip("'")
    if path:
        # 玩家可能粘贴的是 A1 文件夹
        if os.path.isfile(os.path.join(path, "WorldApart.exe")):
            cfg["game_dir"] = os.path.normpath(path)
            dec = os.path.join(path, "BepInEx", "decrypted")
            if os.path.isdir(dec) and glob.glob(os.path.join(dec, "*gameworld*")):
                cfg["decrypted_dir"] = os.path.normpath(dec)
            elif os.path.isdir(dec):
                cfg["decrypted_dir"] = os.path.normpath(dec)
                print("已记住 decrypted 路径，但里面还没有存档。启动游戏停 20 秒就好。")
            else:
                cfg["decrypted_dir"] = os.path.normpath(dec)
                print("路径已记录。请先运行「一键安装.bat」装插件，然后启动游戏停 20 秒。")
            save_cfg(cfg)
            return cfg.get("decrypted_dir", "")
        else:
            # 也让玩家直接粘贴 decrypted
            if os.path.isdir(path):
                cfg["decrypted_dir"] = os.path.normpath(path)
                cfg["game_dir"] = meta_update.game_dir_from_config(cfg, path) or cfg.get("game_dir", "")
                save_cfg(cfg)
                return cfg["decrypted_dir"]
            print("这个路径里没找到 WorldApart.exe 或 decrypted 文件夹。")
    return ""


def find_save_root():
    local_low = os.path.expanduser(r"~\AppData\LocalLow")
    candidates = glob.glob(os.path.join(local_low, "*", "*", "StorageV1", "1.0"))
    for candidate in candidates:
        if glob.glob(os.path.join(candidate, "*", "slots", "*", "gameworld.msgpack")):
            return candidate
    return ""


def original_save_index(save_root):
    index = {}
    if not save_root:
        return index
    for path in glob.glob(os.path.join(save_root, "*", "slots", "*", "gameworld.msgpack")):
        rel = os.path.relpath(path, save_root).replace("\\", "_").replace("/", "_") + ".bin"
        index[rel] = path
    return index


def source_time(copy_path, originals):
    original = originals.get(os.path.basename(copy_path))
    path = original if original and os.path.isfile(original) else copy_path
    try:
        return os.path.getmtime(path), original or ""
    except OSError:
        return 0.0, original or ""


def save_files(dec):
    files = []
    for path in glob.glob(os.path.join(dec, "*gameworld*")):
        try:
            if os.path.getsize(path) > 100000:
                files.append(path)
        except OSError:
            pass
    return files


def state_signature(dec, cfg):
    result = []
    for path in save_files(dec) if dec else []:
        try:
            stat = os.stat(path)
            result.append((os.path.basename(path), stat.st_mtime_ns, stat.st_size))
        except OSError:
            pass
    try:
        cfg_stamp = os.stat(CFG).st_mtime_ns
    except OSError:
        cfg_stamp = 0
    return tuple(sorted(result)), cfg_stamp, tuple(sorted(k for k, v in cfg["modules"].items() if v))




# ---------------- 通用工具 ----------------
def bag_entries(bag):
    """展开背包条目：玩家背包是 [索引, 条目] 的嵌套列表，NPC 背包是普通列表。"""
    entries = bag.get("items") if isinstance(bag, dict) else bag
    result = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("item_id") is not None:
                result.append(node)
                return
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(entries)
    return result
