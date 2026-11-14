"""Download selected components for local preview and later personal Skill packing."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote
import zipfile

from build_personal_skill import (
    COMPONENTS, COMPONENT_LIMIT, REPOSITORY, component_files, download,
    latest_assets, read_file, unpack_component,
)


RECORD_NAME = "components-download.json"


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load_record(path):
    if not path.exists():
        if path.is_symlink():
            raise ValueError("组件下载记录需要使用实际文件")
        return {"schema_version": 1, "repository": REPOSITORY, "release": None, "components": {}}, None
    if not path.is_file() or path.is_symlink():
        raise ValueError("输出目录的下载记录需要使用普通文件")
    content = path.read_bytes()
    record = json.loads(content)
    if (
        not isinstance(record, dict) or type(record.get("schema_version")) is not int
        or record["schema_version"] != 1 or record.get("repository") != REPOSITORY
        or not isinstance(record.get("release"), str) or not record["release"]
        or not isinstance(record.get("components"), dict)
    ):
        raise ValueError("输出目录存在无法复用的下载记录，请选择新的输出目录")
    for slug, item in record["components"].items():
        if (
            slug not in COMPONENTS or not isinstance(item, dict)
            or not isinstance(item.get("archive_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", item["archive_sha256"])
            or type(item.get("bytes")) is not int or not 0 < item["bytes"] <= COMPONENT_LIMIT
            or item.get("archive") != slug + ".zip"
            or item.get("folder") != "components/" + slug
        ):
            raise ValueError("输出目录的下载记录不完整，请选择新的输出目录")
    return record, hashlib.sha256(content).hexdigest()


def save_record(path, record, previous):
    if path.is_symlink() or checksum(path) != previous:
        raise ValueError("下载记录在处理中发生变化，请保全当前内容后重试")
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", prefix=".component-record-", suffix=".json", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        if previous is None:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        return checksum(path)
    finally:
        temporary.unlink(missing_ok=True)


def release_assets(pinned):
    if not pinned:
        return latest_assets()
    payload = download(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{quote(pinned, safe='')}", 5 * 1024 * 1024)
    release = json.loads(payload)
    if not isinstance(release, dict) or release.get("tag_name") != pinned or not isinstance(release.get("assets"), list):
        raise ValueError("未取得已固定版本的组件发布信息")
    return pinned, {item["name"]: item for item in release["assets"]}


def same_folder(existing, staged):
    if existing.is_symlink() or not existing.is_dir():
        return False
    expected = {path.relative_to(staged).as_posix(): checksum(path) for path in component_files(staged)}
    actual = {path.relative_to(existing).as_posix(): checksum(path) for path in component_files(existing)}
    return actual == expected


def fetch(components, out_dir):
    if not components or any(not isinstance(slug, str) or slug not in COMPONENTS for slug in components):
        raise ValueError("请选择当前30款目录中的有效组件ID")
    if len(set(components)) != len(components):
        raise ValueError("组件选择重复，请每个组件填写一次")
    out_dir.mkdir(parents=True, exist_ok=True)
    components_dir = out_dir / "components"
    if components_dir.is_symlink() or not components_dir.resolve().is_relative_to(out_dir.resolve()):
        raise ValueError("组件输出目录需要位于指定下载目录内")
    components_dir.mkdir(exist_ok=True)
    lock = out_dir / ".fetch-components.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("该输出目录正在下载组件，请等本次运行结束后重试") from None
    ready, record = [], None
    try:
        handle.write(str(os.getpid()))
        handle.flush()
        record_path = out_dir / RECORD_NAME
        record, previous_record = load_record(record_path)
        assets = None
        budget = [0]
        for slug in components:
            archive_path = out_dir / (slug + ".zip")
            folder = components_dir / slug
            known = record["components"].get(slug)
            reused = archive_path.is_file()
            if archive_path.is_symlink() or folder.is_symlink() or not folder.resolve().is_relative_to(components_dir.resolve()):
                raise ValueError("已有组件需要使用实际文件和目录")
            if archive_path.exists() and not archive_path.is_file():
                raise ValueError(f"已有同名路径不是ZIP文件 {slug}")
            if reused and known:
                content = read_file(archive_path, {})
                digest = hashlib.sha256(content).hexdigest()
                if digest != known["archive_sha256"] or len(content) != known["bytes"]:
                    raise ValueError(f"已有ZIP与下载记录不同，请保全文件后换目录 {slug}")
            else:
                if assets is None:
                    release, assets = release_assets(record["release"])
                    record["release"] = release
                asset = assets.get(slug + ".zip")
                if not isinstance(asset, dict):
                    raise ValueError(f"该发布版本缺少组件ZIP {slug}")
                url = asset.get("browser_download_url", "")
                if not isinstance(url, str) or not url.startswith(f"https://github.com/{REPOSITORY}/releases/download/"):
                    raise ValueError("组件下载地址与公开仓库不一致")
                expected = asset.get("digest")
                if reused:
                    content = read_file(archive_path, {})
                    digest = hashlib.sha256(content).hexdigest()
                    if not expected and content != download(url, COMPONENT_LIMIT):
                        raise ValueError(f"已有ZIP与发布文件不同，请换下载目录 {slug}")
                else:
                    content = download(url, COMPONENT_LIMIT)
                    digest = hashlib.sha256(content).hexdigest()
                if expected and expected != "sha256:" + digest:
                    raise ValueError(f"组件ZIP校验值不一致，请保全已有文件后换目录 {slug}")
                if known and digest != known["archive_sha256"]:
                    raise ValueError(f"组件与固定版本下载记录不一致 {slug}")
            with tempfile.TemporaryDirectory(prefix=".component-download-", dir=out_dir) as temporary:
                temporary = Path(temporary)
                unpack_component(content, slug, temporary, budget)
                staged = temporary / "components" / slug
                folder_exists = folder.exists()
                if folder_exists and not same_folder(folder, staged):
                    raise ValueError(f"已有组件目录包含不同内容，请保全改动后换下载目录 {slug}")
                staged_zip = temporary / (slug + ".zip")
                staged_zip.write_bytes(content)
                created_zip = False
                try:
                    if not reused:
                        os.link(staged_zip, archive_path)
                        created_zip = True
                    if not folder_exists:
                        os.rename(staged, folder)
                except BaseException:
                    if created_zip and checksum(archive_path) == digest:
                        archive_path.unlink()
                    raise
            if checksum(archive_path) != digest:
                raise ValueError(f"组件ZIP在处理中发生变化 {slug}")
            record["components"][slug] = {
                "archive": slug + ".zip", "folder": "components/" + slug,
                "archive_sha256": digest, "bytes": len(content),
            }
            previous_record = save_record(record_path, record, previous_record)
            ready.append({"id": slug, "archive": str(archive_path), "component_directory": str(folder), "status": "reused" if reused else "downloaded"})
        return {"status": "ready", "directory": str(out_dir), "release": record["release"], "record": str(out_dir / RECORD_NAME), "components": ready}
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        return {"status": "needs_input", "message": str(error), "directory": str(out_dir), "release": record.get("release") if record else None, "components": ready}
    finally:
        handle.close()
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", nargs="+", required=True, help="用户已选择的稳定组件ID")
    parser.add_argument("--out-dir", required=True, type=Path, help="ZIP与本地组件预览的下载目录")
    args = parser.parse_args()
    try:
        result = fetch(args.components, args.out_dir.resolve())
    except (OSError, ValueError) as error:
        result = {"status": "needs_input", "message": str(error), "components": []}
    print(json.dumps(result, ensure_ascii=True))
    if result["status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
