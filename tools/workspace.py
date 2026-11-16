# -*- coding: utf-8 -*-
"""多任务工作区管理：版本线、worktree、本机配置复制与自检。

用法：
    python tools/workspace.py list
    python tools/workspace.py new 1.9 memoria
    python tools/workspace.py new 2.0 rework --from release/1.9
    python tools/workspace.py remove F:\\project\\xy-tasks\\1.9-memoria
    python tools/workspace.py check

约定：
    * main 保持最近一次已发布版本；
    * 每个版本一条 release/<版本> 集成分支；
    * 每个任务一条 feature/<版本>-<任务> 分支，放在独立 worktree；
    * 开发分支不改 app/version.py，版本号由发布负责人在发布时统一修改。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKTREE_PARENT = os.path.join(os.path.dirname(ROOT), "xy-tasks")
VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


def git(args, cwd=None, check=True):
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false"] + args, cwd=cwd or ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise SystemExit("git %s 失败：%s" % (" ".join(args), message))
    return result


def worktrees():
    """解析 git worktree list --porcelain，返回 [{path, branch}]。"""
    output = git(["worktree", "list", "--porcelain"]).stdout
    items, current = [], {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                items.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current["path"] = value
        elif key == "branch":
            current["branch"] = value.replace("refs/heads/", "")
        elif key == "detached":
            current["branch"] = "(detached)"
        elif key == "bare":
            current["branch"] = "(bare)"
    if current:
        items.append(current)
    return items


def branch_exists(name):
    return git(["show-ref", "--verify", "--quiet", "refs/heads/%s" % name],
               check=False).returncode == 0


def valid_branch(name):
    return git(["check-ref-format", "--branch", name], check=False).returncode == 0


def current_branch(path):
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=False)
    return result.stdout.strip() if result.returncode == 0 else "?"


def version_of(path):
    try:
        with open(os.path.join(path, "app", "version.py"), encoding="utf-8") as f:
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)', f.read())
        return match.group(1) if match else "?"
    except OSError:
        return "?"


def dirty_count(path):
    result = git(["status", "--porcelain"], cwd=path, check=False)
    if result.returncode != 0:
        return -1
    return len([line for line in result.stdout.splitlines() if line.strip()])


def tag_exists(name):
    return git(["rev-parse", "--verify", "--quiet", "refs/tags/%s" % name],
               check=False).returncode == 0


def branch_names(patterns):
    args = ["branch", "--list", "--format=%(refname:short)"]
    args.extend(patterns)
    result = git(args, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def slug(text):
    value = re.sub(r'[<>:"/\\|?*\s]+', "-", text).strip(" .-")
    return value


def cmd_new(args):
    version = args.version.strip()
    if not VERSION_RE.match(version):
        raise SystemExit("版本号格式应为 1.9 或 1.9.0：%s" % version)
    task = slug(args.task)
    if not task:
        raise SystemExit("任务名不能为空")
    line = "release/%s" % version
    feature = "feature/%s-%s" % (version, task)
    target = os.path.abspath(args.dir or os.path.join(WORKTREE_PARENT, "%s-%s" % (version, task)))

    if not valid_branch(feature):
        raise SystemExit("分支名不合法：%s" % feature)
    if branch_exists(feature):
        raise SystemExit("分支已存在：%s（先合并或删除旧任务）" % feature)
    if os.path.exists(target):
        raise SystemExit("目录已存在：%s" % target)

    if branch_exists(line):
        if args.from_branch and args.from_branch != line:
            print("提示：%s 已存在，忽略 --from %s" % (line, args.from_branch))
        base = line
    else:
        base = args.from_branch or "main"
        if not branch_exists(base):
            raise SystemExit("基础分支不存在：%s" % base)
        git(["branch", line, base])
        print("已创建版本线：%s（基于 %s）" % (line, base))

    dirty = dirty_count(ROOT)
    if dirty > 0:
        print("提示：主工作区有 %d 处未提交改动，不会带入新任务" % dirty)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    git(["worktree", "add", target, "-b", feature, line])

    config = os.path.join(ROOT, "config.json")
    if os.path.isfile(config):
        shutil.copy2(config, os.path.join(target, "config.json"))
        print("已复制本机配置：config.json")
    else:
        print("提示：主工作区没有 config.json，新工作区首次运行需要重新定位游戏目录")

    print()
    print("工作区：%s" % target)
    print("版本线：%s" % line)
    print("任务分支：%s" % feature)
    print("预览：python xianyou_assistant.py --once --no-browser --out-dir tmp/preview")
    print("提示：开发分支不要改 app/version.py；缓存已按工作区自动隔离。")


def cmd_list(_args):
    items = worktrees()
    main_path = os.path.normcase(os.path.abspath(ROOT))
    checked_out = set()
    print("工作区：")
    for item in items:
        path = item.get("path", "")
        branch = item.get("branch", "?")
        checked_out.add(branch)
        mark = "*" if os.path.normcase(os.path.abspath(path)) == main_path else " "
        count = dirty_count(path)
        state = "无法读取" if count < 0 else ("干净" if count == 0 else "%d 处未提交" % count)
        print("%s %s  [%s]  v%s  %s" % (mark, path, branch, version_of(path), state))

    lines = branch_names(["release/*", "feature/*", "fix/*"])
    if lines:
        print()
        print("版本线与任务分支：")
        for name in lines:
            print("  %s%s" % (name, "（已检出）" if name in checked_out else ""))


def cmd_remove(args):
    items = worktrees()
    target = args.target
    match = None
    for item in items:
        if item.get("branch") == target:
            match = item
            break
    if match is None:
        target_path = os.path.normcase(os.path.abspath(target))
        for item in items:
            if os.path.normcase(os.path.abspath(item.get("path", ""))) == target_path:
                match = item
                break
    if match is None:
        raise SystemExit("没有找到工作区或分支：%s" % target)

    path = match.get("path", "")
    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(ROOT)):
        raise SystemExit("不能删除主工作区")

    count = dirty_count(path)
    if count > 0 and not args.force:
        raise SystemExit("工作区还有 %d 处未提交改动，先提交或加 --force 丢弃" % count)
    git(["worktree", "remove", path] + (["--force"] if args.force else []))
    git(["worktree", "prune"], check=False)
    print("已删除工作区：%s" % path)
    print("分支仍保留：%s（确认合并后可执行 git branch -d %s）" % (match.get("branch"), match.get("branch")))


def cmd_check(_args):
    notes = []
    main_branch = current_branch(ROOT)
    if main_branch != "main":
        notes.append("主工作区当前在 %s，main 应保持最新已发布版本" % main_branch)

    main_version = version_of(ROOT)
    if not tag_exists("v%s" % main_version):
        notes.append("当前版本 v%s 还没有 tag，发布后请打 tag 作为热修锚点" % main_version)

    versions = {}
    print("工作区检查：")
    main_path = os.path.normcase(os.path.abspath(ROOT))
    for item in worktrees():
        path = item.get("path", "")
        branch = item.get("branch", "?")
        count = dirty_count(path)
        version = version_of(path)
        versions.setdefault(version, []).append(branch)
        state = "无法读取" if count < 0 else ("干净" if count == 0 else "%d 处未提交" % count)
        print("  %s  [%s]  v%s  %s" % (path, branch, version, state))
        if count > 0:
            notes.append("%s 有 %d 处未提交改动" % (branch, count))
        if os.path.normcase(os.path.abspath(path)) != main_path and not os.path.isfile(
                os.path.join(path, "config.json")):
            notes.append("%s 缺少 config.json，首次运行需要重新定位游戏目录" % branch)

    lines = set(branch_names(["release/*"]))
    for feature in branch_names(["feature/*"]):
        match = re.match(r"feature/(\d+\.\d+(?:\.\d+)?)-", feature)
        if match:
            line = "release/%s" % match.group(1)
            if line not in lines:
                notes.append("%s 没有对应的版本线 %s" % (feature, line))

    if len(versions) > 1:
        notes.append("多个工作区的版本号不一致：%s" % ", ".join(
            "v%s=%s" % (key, "/".join(value)) for key, value in sorted(versions.items())))
    if len(branch_names(["feature/*"])) > 1:
        notes.append("并行任务较多，合并顺序固定：模块代码 → 快照 → 版本与发布物料")

    print()
    if notes:
        print("提示：")
        for note in notes:
            print("  - %s" % note)
    else:
        print("检查通过，没有发现问题。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="多任务工作区管理")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="为任务创建独立 worktree")
    new.add_argument("version", help="目标版本，例如 1.9")
    new.add_argument("task", help="任务名，例如 memoria")
    new.add_argument("--from", dest="from_branch", help="创建版本线时使用的基础分支，默认 main")
    new.add_argument("--dir", help="工作区目录，默认仓库同级 xy-tasks/<版本>-<任务>")
    new.set_defaults(handler=cmd_new)

    listing = sub.add_parser("list", help="列出工作区与版本线")
    listing.set_defaults(handler=cmd_list)

    remove = sub.add_parser("remove", help="删除工作区（保留分支）")
    remove.add_argument("target", help="工作区路径或分支名")
    remove.add_argument("--force", action="store_true", help="丢弃未提交改动后删除")
    remove.set_defaults(handler=cmd_remove)

    check = sub.add_parser("check", help="检查工作区、版本线与 tag")
    check.set_defaults(handler=cmd_check)

    args = parser.parse_args(argv)
    args.handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
