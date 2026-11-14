"""Build complete component ZIPs and a portable library ZIP for a release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


BUNDLE_NAME = "wechat-layout-copilot"
EXCLUDED_DIRECTORIES = {".git", "__pycache__", "dist", "output"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def source_files(root):
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRECTORIES)
        for name in names:
            if (current / name).is_symlink():
                raise ValueError(f"源目录包含符号链接，请先准备实际素材 {current / name}")
        for name in sorted(filenames):
            path = current / name
            if path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if path.is_symlink():
                raise ValueError(f"源文件包含符号链接，请先准备实际文件 {path}")
            files.append(path)
    return sorted(files)


def output_directory(root, requested):
    destination = requested.resolve()
    if destination == root:
        raise ValueError("输出目录不能是组件库根目录，请使用dist或库外目录")
    if destination.is_relative_to(root) and not destination.is_relative_to(root / "dist"):
        raise ValueError("库内输出只能放在dist目录，请保留组件源文件")
    return destination


def independent_links(folder, files):
    for source in files:
        if source.suffix.lower() != ".md":
            continue
        for target in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
            target = target.split(' "', 1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme in {"https", "http", "mailto"} or target.startswith("#"):
                continue
            if parsed.scheme or target.startswith("//"):
                raise ValueError(f"单项组件说明包含不可携带的链接 {source}: {target}")
            referenced = (source.parent / unquote(parsed.path)).resolve()
            if not referenced.is_relative_to(folder):
                raise ValueError(f"单项组件引用了目录外材料，请改为公开链接或补齐素材 {source}: {target}")
            if not referenced.is_file():
                raise ValueError(f"单项组件缺少引用文件 {source}: {target}")


def release_plan(root, files):
    for name in ("SKILL.md", "README.md", "index.html", "LICENSE"):
        if not (root / name).is_file():
            raise ValueError(f"组件库缺少入口文件 {name}")
    skills = root / "skills"
    if not skills.is_dir():
        raise ValueError("组件库缺少skills目录")
    plans = []
    folders = sorted(skills.iterdir())
    workflows = root / "workflows"
    if workflows.is_dir():
        folders.extend(sorted(workflows.iterdir()))
    for folder in folders:
        if not folder.is_dir() or folder.name in EXCLUDED_DIRECTORIES:
            continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", folder.name):
            raise ValueError(f"组件目录名不适合公开下载 {folder.name}")
        if not (folder / "SKILL.md").is_file():
            raise ValueError(f"组件缺少SKILL.md {folder.name}")
        members = [path for path in files if path.is_relative_to(folder)]
        independent_links(folder, members)
        package_members = [
            ((Path(folder.name) / path.relative_to(folder)).as_posix(), path)
            for path in members
        ]
        if not (folder / "LICENSE").is_file():
            package_members.append(((Path(folder.name) / "LICENSE").as_posix(), root / "LICENSE"))
        plans.append((folder.name + ".zip", package_members))
    if not plans:
        raise ValueError("未找到可打包的组件")
    plans.append((BUNDLE_NAME + ".zip", [
        ((Path(BUNDLE_NAME) / path.relative_to(root)).as_posix(), path)
        for path in files
    ]))
    if len({name for name, _ in plans}) != len(plans):
        raise ValueError("组件包名称与整包名称重复")
    return plans


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def temporary_file(directory, suffix):
    handle = tempfile.NamedTemporaryFile(prefix=".downloads-", suffix=suffix,
                                         dir=directory, delete=False)
    handle.close()
    return Path(handle.name)


def archive_file(path, members, snapshot):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, source in members:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, snapshot[source])
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"压缩包校验失败 {path.name}")
        if len(archive.namelist()) != len(members):
            raise ValueError(f"压缩包文件数量不一致 {path.name}")
        for name, source in members:
            if archive.read(name) != snapshot[source]:
                raise ValueError(f"压缩包内容与来源不一致 {name}")


def build(root, requested, overwrite=False):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("组件库根目录不存在")
    destination = output_directory(root, requested)
    files = source_files(root)
    plans = release_plan(root, files)
    snapshot = {path: path.read_bytes() for path in files}
    targets = [destination / name for name, _ in plans]
    for target in targets:
        if target.is_symlink() or target.is_dir():
            raise ValueError(f"输出目标需要是普通ZIP文件 {target}")
        if target.exists() and not overwrite:
            raise ValueError(f"输出已存在，请换目录或使用--overwrite {target}")
    destination.mkdir(parents=True, exist_ok=True)
    lock_path = destination / ".build-downloads.lock"
    try:
        lock_handle = lock_path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError(f"已有下载包构建占用此目录 {lock_path}") from error
    staged = {}
    backups = {}
    previous = {}
    committed = []
    preserved = set()
    generated = {}
    try:
        lock_handle.write(str(os.getpid()))
        lock_handle.flush()
        for target in targets:
            previous[target] = digest(target)
            if target.exists() and not overwrite:
                raise ValueError(f"输出已存在，请换目录或使用--overwrite {target}")
        records = []
        for (name, members), target in zip(plans, targets):
            staged[target] = temporary_file(destination, ".zip.part")
            archive_file(staged[target], members, snapshot)
            generated[target] = digest(staged[target])
            records.append({"name": name, "bytes": staged[target].stat().st_size,
                            "sha256": generated[target], "files": len(members)})
        if source_files(root) != files or any(path.read_bytes() != content for path, content in snapshot.items()):
            raise ValueError("构建期间源文件已变化，请重新构建")
        for target in targets:
            if target.is_symlink() or digest(target) != previous[target]:
                raise ValueError(f"构建期间输出已变化，请保留新内容后重新构建 {target}")
            if previous[target] is not None:
                backups[target] = temporary_file(destination, ".backup")
                backups[target].write_bytes(target.read_bytes())
        for target in targets:
            if target.is_symlink() or digest(target) != previous[target]:
                raise ValueError(f"提交期间输出已变化，请保留新内容后重新构建 {target}")
            os.replace(staged[target], target)
            committed.append(target)
        component_count = sum(path.name == "SKILL.md" and path.parent.parent == root / "skills" for path in files)
        return {"out_dir": str(destination), "components": component_count,
                "workflows": len(plans) - component_count - 1,
                "bundle": BUNDLE_NAME + ".zip", "files": records}
    except BaseException as error:
        recovery = []
        for target in reversed(committed):
            try:
                if target.exists() and digest(target) != generated[target]:
                    if target in backups:
                        preserved.add(backups[target])
                        recovery.append(str(backups[target]))
                    else:
                        recovery.append(str(target))
                    continue
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                if target in backups:
                    preserved.add(backups[target])
                    recovery.append(str(backups[target]))
                else:
                    recovery.append(str(target))
        if recovery:
            raise OSError(str(error) + "\n请保留这些恢复材料 " + ", ".join(recovery)) from error
        raise
    finally:
        for temporary in list(staged.values()) + list(backups.values()):
            if temporary not in preserved:
                temporary.unlink(missing_ok=True)
        lock_handle.close()
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="组件库根目录，默认采用本脚本的上级项目目录")
    parser.add_argument("--out-dir", type=Path, help="输出目录，默认采用组件库dist目录")
    parser.add_argument("--overwrite", action="store_true", help="原子替换同名下载包")
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    destination = args.out_dir or root / "dist"
    try:
        result = build(root, destination, args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
