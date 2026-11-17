# -*- coding: utf-8 -*-
"""发布流程：版本一致性检查、页面生成、打包、工坊 vdf 生成。

用法：
    python tools/release.py --check      # 只读预检（并行开发自检用）
    python tools/release.py --dry-run    # 生成页面与 vdf 到 tmp/release-preview，不打包
    python tools/release.py              # 正式发布（不含 Steam 上传，上传仍需人工）

约定：
    * 版本号唯一来源是 app/version.py；
    * 快照是源文件，发布不重新解包、不访问游戏目录；
    * 页面只写 仙友助手/，根目录产物仅用于开发预览；
    * 失败一律在写入前拦下（先检查后写入），覆盖式写入都走临时文件 + 原子替换。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(ROOT, "release")
APP_DIR = os.path.join(ROOT, "仙友助手")
WORKSHOP_DIR = os.path.join(ROOT, "workshop_release")
DIST_DIR = os.path.join(ROOT, "dist")
CONFIG = os.path.join(ROOT, "config.json")
LOCK = os.path.join(ROOT, ".release.lock")
DESC_LIMIT = 8000


def _version():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app.version import VERSION
    return VERSION


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except OSError:
        return ""


def _write_atomic(path, text):
    tmp = path + ".%s.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _first_line(path):
    return (_read(path).splitlines() or [""])[0].strip()


def _vdf(value):
    """VDF 字符串转义：换行与引号与现有 vdf 的写法保持一致。"""
    return json.dumps(str(value), ensure_ascii=False)[1:-1]


def _slash(path):
    """SteamCMD 对反斜杠敏感，路径统一用正斜杠，免去双重转义。"""
    return os.path.abspath(path).replace("\\", "/")


def _has_decrypted_dir():
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except Exception:
        return False
    path = str(cfg.get("decrypted_dir") or "")
    return bool(path) and os.path.isdir(path)


def preflight(version):
    """返回 (错误, 待办)：错误阻断发布，待办是发布人需要补齐的文案。"""
    errors, todos = [], []
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        errors.append("app/version.py 的 VERSION 不是 x.y.z：%s" % version)

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from tools import packaging
    _datas, problems, notes = packaging.check(ROOT)
    errors.extend(problems)
    todos.extend(note for note in notes if not note.startswith("打包期"))
    readme = os.path.join(APP_DIR, "使用说明.txt")
    expect = "不问凡尘 · 仙友助手 v%s" % version
    if not os.path.isfile(readme):
        errors.append("缺少 仙友助手/使用说明.txt")
    elif _first_line(readme) != expect:
        todos.append("使用说明首行待更新为「%s」（发布时会自动改写）" % expect)

    for name in ("工坊描述.txt", "工坊描述_en.txt"):
        path = os.path.join(WORKSHOP_DIR, name)
        text = _read(path)
        if not text:
            errors.append("缺少 workshop_release/%s" % name)
            continue
        if "v%s" % version not in text.splitlines()[0]:
            todos.append("%s 首行版本号待更新为 v%s" % (name, version))
        if name.endswith("_en.txt"):
            encoded = len(_vdf(text).encode("utf-8"))
            if encoded >= DESC_LIMIT:
                errors.append("工坊英文描述转义后 %d 字节，超过 %d 上限" % (encoded, DESC_LIMIT))

    changenote = os.path.join(RELEASE_DIR, "changenote.txt")
    if not os.path.isfile(changenote):
        errors.append("缺少 release/changenote.txt")
    elif "v%s" % version not in _first_line(changenote):
        todos.append("release/changenote.txt 仍不是 v%s 的更新说明" % version)

    title = os.path.join(RELEASE_DIR, "title.txt")
    if not _first_line(title):
        errors.append("缺少 release/title.txt（工坊标题的一句话摘要）")

    if not os.path.isfile(os.path.join(RELEASE_DIR, "workshop.vdf.tpl")):
        errors.append("缺少 release/workshop.vdf.tpl")
    if not os.path.isfile(os.path.join(WORKSHOP_DIR, "preview.png")):
        errors.append("缺少 workshop_release/preview.png")

    if not _has_decrypted_dir():
        todos.append("本机未找到可用的解密存档目录，--dry-run 将跳过页面生成")

    try:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        status = ""
    if status:
        todos.append("工作区有未提交改动（%d 行），建议先提交基线再发布" % len(status.splitlines()))
    return errors, todos


def generate_pages(out_dir, version):
    if not _has_decrypted_dir():
        return False
    command = [sys.executable, "xianyou_assistant.py", "--once", "--no-browser",
               "--out-dir", out_dir]
    print("生成页面：%s" % out_dir)
    subprocess.run(command, cwd=ROOT, check=True)
    html = os.path.join(out_dir, "仙友助手.html")
    if not os.path.isfile(html):
        raise SystemExit("页面生成失败：%s 不存在" % html)
    html_text = _read(html)
    if "__VER__" in html_text or ("v%s" % version) not in html_text:
        print("提示：页面标题区未注入版本 v%s，请确认 APP_VERSION 替换正常" % version)
    return True


def generate_vdf(target, version, content_dir):
    template = _read(os.path.join(RELEASE_DIR, "workshop.vdf.tpl"))
    title = "%s v%s（%s）" % ("仙友助手", version, _first_line(os.path.join(RELEASE_DIR, "title.txt")))
    changenote = _read(os.path.join(RELEASE_DIR, "changenote.txt")).strip()
    description = _read(os.path.join(WORKSHOP_DIR, "工坊描述_en.txt")).strip()
    body = (template
            .replace("{{CONTENT}}", _vdf(_slash(content_dir)))
            .replace("{{PREVIEW}}", _vdf(_slash(os.path.join(WORKSHOP_DIR, "preview.png"))))
            .replace("{{TITLE}}", _vdf(title))
            .replace("{{DESCRIPTION}}", _vdf(description))
            .replace("{{CHANGENOTE}}", _vdf(changenote)))
    _write_atomic(target, body)
    print("生成 vdf：%s" % target)
    return title


def update_readme(version):
    path = os.path.join(APP_DIR, "使用说明.txt")
    lines = _read(path).splitlines()
    if not lines:
        raise SystemExit("使用说明为空")
    lines[0] = "不问凡尘 · 仙友助手 v%s" % version
    _write_atomic(path, "\n".join(lines) + "\n")
    print("使用说明首行已更新为 v%s" % version)


def build_exe():
    staging = os.path.join(DIST_DIR, "staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    command = [sys.executable, "-m", "PyInstaller", "TouchProgress.spec", "--noconfirm",
               "--distpath", staging, "--workpath", os.path.join(ROOT, "build", "staging")]
    print("打包：%s" % " ".join(command[1:]))
    subprocess.run(command, cwd=ROOT, check=True)
    exe = os.path.join(staging, "仙友助手.exe")
    if not os.path.isfile(exe):
        raise SystemExit("打包失败：未生成 %s" % exe)
    shutil.copy2(exe, os.path.join(APP_DIR, "仙友助手.exe"))
    print("已更新 仙友助手/仙友助手.exe")
    return staging


def make_zip(staging, version):
    target = os.path.join(staging, "仙友助手v%s.zip" % version)
    files = []
    for base, _dirs, names in os.walk(APP_DIR):
        for name in names:
            path = os.path.join(base, name)
            files.append((os.path.relpath(path, APP_DIR).replace("\\", "/"), path))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, path in sorted(files):
            info = zipfile.ZipInfo("仙友助手/" + relative, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(path, "rb") as f:
                archive.writestr(info, f.read())
    print("已生成 %s（%d 个文件）" % (target, len(files)))
    return target


def acquire_lock(version):
    if os.path.isfile(LOCK):
        age = time.time() - os.path.getmtime(LOCK)
        if age < 7200:
            raise SystemExit("另一工作区正在发布（锁：%s，%.0f 分钟前）。"
                             "确认无人在发布后可删除该文件再试。" % (LOCK, age / 60))
    _write_atomic(LOCK, json.dumps({"version": version, "time": int(time.time()), "pid": os.getpid()}))
    return LOCK


def release(version):
    lock = acquire_lock(version)
    try:
        generate_pages(APP_DIR, version)
        update_readme(version)
        staging = build_exe()
        archive = make_zip(staging, version)
        generate_vdf(os.path.join(WORKSHOP_DIR, "workshop.vdf"), version, APP_DIR)
        print("发布产物就绪：%s" % archive)
        print("下一步：人工执行 workshop_release\\upload_to_workshop.bat")
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


def main(argv):
    version = _version()
    errors, todos = preflight(version)
    print("版本：%s" % version)
    for note in todos:
        print("待办：%s" % note)
    for error in errors:
        print("错误：%s" % error)
    if errors:
        print("预检未通过：%d 项阻断问题" % len(errors))
        return 2
    if "--check" in argv:
        if todos:
            print("预检通过（%d 项发布待办需在发布前处理）" % len(todos))
            return 1
        print("预检全部通过")
        return 0
    if "--dry-run" in argv:
        out = os.path.join(ROOT, "tmp", "release-preview")
        os.makedirs(out, exist_ok=True)
        generate_pages(out, version)
        title = generate_vdf(os.path.join(out, "workshop.vdf"), version, APP_DIR)
        print("试运行完成：%s（标题：%s）" % (out, title))
        return 0
    release(version)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
