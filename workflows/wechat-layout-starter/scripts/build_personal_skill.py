"""Build a portable personal WeChat layout Skill from a confirmed profile."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile


REPOSITORY = "frederick-kk/wechat-layout-copilot"
COMPONENT_LIMIT = 100 * 1024 * 1024
TOTAL_LIMIT = 500 * 1024 * 1024
COMPONENTS = {
    "wechat-avatar-profile", "wechat-svg-envelope", "wechat-svg-flip-card",
    "wechat-svg-parallax", "wechat-svg-vinyl", "wechat-svg-pull-tab",
    "wechat-svg-timeline", "wechat-svg-open-window", "wechat-svg-wipe-compare",
    "wechat-svg-zoom-detail", "wechat-svg-click-reveal", "wechat-svg-blinds",
    "wechat-svg-spotlight", "wechat-svg-accordion-panels", "wechat-svg-puzzle-assemble",
    "wechat-svg-confetti", "wechat-svg-hotspots", "wechat-svg-switch",
    "wechat-svg-layer-peel", "wechat-svg-press-reveal", "wechat-svg-hold-cards",
    "wechat-svg-quiz", "wechat-svg-story-branches", "wechat-svg-motion-path",
    "wechat-svg-typewriter", "wechat-svg-data-chart", "wechat-svg-drawline",
    "wechat-xiumi-gallery", "wechat-layout-blocks", "wechat-xiumi-svg-layout",
}
PRIVATE_KEYS = {
    "api_key", "authorization", "cookie", "cookies", "password", "access_token",
    "refresh_token", "session", "secret", "token",
}
EXCLUDED_DIRECTORIES = {".git", "__pycache__", "dist", "output"}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"}
RESERVED_NAMES.update(f"COM{number}" for number in range(1, 10))
RESERVED_NAMES.update(f"LPT{number}" for number in range(1, 10))


def require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"请填写 {field}")
    return value.strip()


def check_private_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower().replace("-", "_") in PRIVATE_KEYS:
                raise ValueError("排版配置中包含登录或密钥字段，请移除后重试")
            check_private_fields(item)
    elif isinstance(value, list):
        for item in value:
            check_private_fields(item)


def safe_filename(name):
    if (
        not isinstance(name, str) or not name or len(name) > 160
        or name in {".", ".."} or name.endswith((" ", "."))
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
        or name.split(".", 1)[0].upper() in RESERVED_NAMES
    ):
        raise ValueError("素材或压缩包包含不适合本地使用的文件名")
    return name


def validate_profile(profile):
    if not isinstance(profile, dict) or type(profile.get("schema_version")) is not int or profile["schema_version"] != 1:
        raise ValueError("配置需要使用 schema_version 1")
    allowed = {"schema_version", "skill_name", "display_name", "account", "style", "components", "delivery", "assets"}
    if set(profile) - allowed:
        raise ValueError("配置存在未知的顶层字段，请按配置格式整理")
    check_private_fields(profile)
    name = require_text(profile.get("skill_name"), "skill_name")
    if name != profile["skill_name"] or len(name) >= 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("skill_name需要少于64位的小写英文、数字与连字符")
    require_text(profile.get("display_name"), "display_name")
    account = profile.get("account")
    if not isinstance(account, dict):
        raise ValueError("请提供 account 账号信息")
    require_text(account.get("name"), "account.name")
    style = profile.get("style")
    if not isinstance(style, dict) or not isinstance(style.get("rules"), dict) or not style["rules"]:
        raise ValueError("请先整理 style.rules 排版规则")
    sources = style.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("请先提供已读取的风格参考文章")
    for source in sources:
        if not isinstance(source, dict) or not (source.get("url") or source.get("file")):
            raise ValueError("每份风格来源需要url或file")
        if source.get("url"):
            parsed = urlsplit(require_text(source["url"], "style.sources[].url"))
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                raise ValueError("风格来源URL需要使用完整网页地址")
        require_text(source.get("observed"), "style.sources[].observed")
    components = profile.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("请先选择需要使用的组件")
    names = []
    for component in components:
        if not isinstance(component, dict) or not isinstance(component.get("id"), str) or component["id"] not in COMPONENTS:
            raise ValueError("选择的组件不在当前30款组件目录中")
        names.append(component["id"])
        require_text(component.get("use_when"), "components[].use_when")
        require_text(component.get("placement"), "components[].placement")
    if len(set(names)) != len(names):
        raise ValueError("组件选择重复，请合并同一组件的使用规则")
    delivery = profile.get("delivery")
    if not isinstance(delivery, dict) or not isinstance(delivery.get("editor"), str) or delivery["editor"] not in {"wechat", "xiumi", "ask"}:
        raise ValueError("delivery.editor需要填写wechat、xiumi或ask")
    if delivery.get("mode") != "draft":
        raise ValueError("本打包器的delivery.mode需要填写draft")
    assets = profile.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("assets需要使用素材列表")
    asset_names = []
    for asset in assets:
        if not isinstance(asset, dict) or not (asset.get("source") or asset.get("path")):
            raise ValueError("每项assets素材需要source或path")
        asset_names.append(safe_filename(asset.get("name")))
    if len({name.casefold() for name in asset_names}) != len(asset_names):
        raise ValueError("素材文件名重复，请为每份素材指定不同的name")
    return profile


def read_file(path, snapshots, limit=COMPONENT_LIMIT):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"需要可读取的普通文件 {path.name}")
    if path.stat().st_size > limit:
        raise ValueError(f"文件过大 {path.name}")
    content = path.read_bytes()
    if len(content) > limit:
        raise ValueError(f"文件过大 {path.name}")
    checksum = hashlib.sha256(content).hexdigest()
    if path in snapshots and snapshots[path] != checksum:
        raise ValueError(f"制作期间输入文件发生变化 {path.name}")
    snapshots[path] = checksum
    return content


def local_path(value, directory):
    value = require_text(value, "本地素材路径")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = directory / path
    if path.is_symlink():
        raise ValueError("请提供素材实际文件，避免使用符号链接")
    return path.resolve()


def write_bytes(destination, content, budget):
    budget[0] += len(content)
    if budget[0] > TOTAL_LIMIT:
        raise ValueError("本次打包的素材超过500MB，请缩小选择范围")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(content)


def copy_profile_materials(profile, config_directory, staged, snapshots, budget):
    for index, source in enumerate(profile["style"]["sources"], 1):
        if not source.get("file"):
            continue
        original = local_path(source["file"], config_directory)
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", original.name)
        name = safe_filename(f"{index:02}-{cleaned[:130]}")
        relative = Path("references/source-articles") / name
        write_bytes(staged / relative, read_file(original, snapshots), budget)
        source["file"] = relative.as_posix()
    for asset in profile.get("assets", []):
        original = local_path(asset.get("source") or asset.get("path"), config_directory)
        relative = Path("assets") / asset["name"]
        write_bytes(staged / relative, read_file(original, snapshots), budget)
        asset.pop("source", None)
        asset["path"] = relative.as_posix()


def component_files(directory):
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"组件目录不存在或不是普通目录 {directory.name}")
    files = []
    for current, names, filenames in os.walk(directory, followlinks=False):
        parent = Path(current)
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRECTORIES)
        for name in names:
            child = parent / name
            if child.is_symlink() or not child.resolve().is_relative_to(directory.resolve()):
                raise ValueError("组件目录包含符号链接或外部目录")
        for name in sorted(filenames):
            if name.endswith((".pyc", ".pyo")):
                continue
            child = parent / name
            if child.is_symlink():
                raise ValueError("组件素材需要使用实际文件")
            for part in child.relative_to(directory).parts:
                safe_filename(part)
            files.append(child)
    if not (directory / "SKILL.md").is_file():
        raise ValueError(f"组件缺少SKILL.md {directory.name}")
    return files


def copy_local_component(library, slug, staged, snapshots, budget):
    directory = library / "skills" / slug
    files = component_files(directory)
    total = 0
    names = set()
    for source in files:
        relative = source.relative_to(directory)
        key = relative.as_posix().casefold()
        if key in names:
            raise ValueError("组件存在大小写冲突的文件名")
        names.add(key)
        content = read_file(source, snapshots)
        total += len(content)
        if total > COMPONENT_LIMIT:
            raise ValueError(f"单个组件展开后超过100MB {slug}")
        write_bytes(staged / "components" / slug / relative, content, budget)
    return {"id": slug, "source": "local-library"}, (directory, files)


def download(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "wechat-layout-starter/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if not response.geturl().startswith("https://"):
                raise ValueError("组件下载需要使用HTTPS")
            content = bytearray()
            while chunk := response.read(1024 * 1024):
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError("下载文件超过大小限制")
            return bytes(content)
    except urllib.error.HTTPError as error:
        raise ValueError(f"GitHub下载未完成，HTTP {error.code}，稍后可重新运行") from None
    except urllib.error.URLError:
        raise ValueError("无法连接GitHub，请检查当前网络后重新运行") from None


def latest_assets():
    payload = download(f"https://api.github.com/repos/{REPOSITORY}/releases/latest", 5 * 1024 * 1024)
    release = json.loads(payload)
    if not isinstance(release, dict) or not isinstance(release.get("assets"), list):
        raise ValueError("未取得GitHub组件发布信息")
    return release.get("tag_name"), {item["name"]: item for item in release["assets"]}


def unpack_component(content, slug, staged, budget):
    target = staged / "components" / slug
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if len(members) > 10000:
            raise ValueError("组件压缩包条目过多")
        total, seen = 0, set()
        validated = []
        for member in members:
            name = member.filename
            path = PurePosixPath(name)
            if "\\" in name or path.is_absolute() or not path.parts or path.parts[0] != slug:
                raise ValueError("组件压缩包存在目录外路径")
            if any(part in {".", ".."} for part in name.rstrip("/").split("/")):
                raise ValueError("组件压缩包存在目录跳转路径")
            for part in path.parts:
                safe_filename(part)
            key = path.as_posix().rstrip("/").casefold()
            if key in seen:
                raise ValueError("组件压缩包存在重复文件名")
            seen.add(key)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("组件压缩包包含链接或特殊文件")
            if member.flag_bits & 1:
                raise ValueError("组件压缩包不应包含加密文件")
            total += member.file_size
            if total > COMPONENT_LIMIT:
                raise ValueError("单个组件展开后超过100MB")
            validated.append((member, Path(*path.parts[1:])))
        for member, relative in validated:
            if member.is_dir():
                continue
            with archive.open(member) as stream:
                content = stream.read(COMPONENT_LIMIT + 1)
            if len(content) != member.file_size:
                raise ValueError("组件文件长度与压缩包记录不一致")
            write_bytes(target / relative, content, budget)
    if not (target / "SKILL.md").is_file():
        raise ValueError(f"组件压缩包缺少SKILL.md {slug}")


def component_heading(folder, slug):
    text = (folder / "components" / slug / "SKILL.md").read_text(encoding="utf-8-sig")
    match = re.search(r"(?m)^# ([^\n]+)", text)
    return match[1].strip() if match else slug


def table_cell(value):
    return str(value).replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def skill_text(profile, staged):
    name = profile["skill_name"]
    display = profile["display_name"]
    account = profile["account"]["name"]
    description = f"使用{account}已确认的文章风格、素材和选定组件排版公众号正文，按约定保存到微信公众平台或秀米草稿，并在需要时微调排版。"
    rows = []
    for component in profile["components"]:
        slug = component["id"]
        title = table_cell(component_heading(staged, slug))
        rows.append(f"| [{title}](components/{slug}/SKILL.md) | {table_cell(component['use_when'])} | {table_cell(component['placement'])} |")
    return f'''---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
---

# {display}

为「{account}」排版公众号文章。先读取[专属排版配置](profile.json)，按其中的风格来源、规则、素材及组件使用场景处理本次正文。

## 处理一篇文章

1. 读取用户本次提供的完整正文、图片与目标草稿。延续正文内容和叙述顺序，按配置调整视觉排版。用户另有改写要求时再处理文字。
2. 按[环境与浏览器准备](references/environment.md)检查当前浏览器能力，读取本机Ego lite的当前操作说明，复用已授权的工作窗口和登录状态。需要用户扫码时让用户完成登录，收到继续信号后推进。
3. 根据正文含义，从下表选择本篇适用的组件。读取对应子Skill及配置中的settings、frequency和输入要求，整理需要的文字、图片或真实公众号名片。只询问本次确实缺少的材料。
4. 将组件模板中的示例头像、署名、正文和插画替换为本账号与当前正文的素材，落实profile.json中的排版规则。缺少用户素材时给出具体缺项或采用用户已同意的简化排版。
5. 按[排版与草稿交付](references/format-and-deliver.md)生成可编辑排版并微调，核对全部正文、图片、链接、组件交互及窄屏布局。
6. 依据delivery.editor保存到用户指定的微信公众平台或秀米草稿。配置为ask且本次也未指定目标时，简短确认本次保存位置。用户已要求同步草稿时连续完成保存与重开检查。
7. 交付实际草稿位置和组件使用位置，按实际完成情况说明浏览器、编辑器保存、公众号同步与手机微信的检查结果。发布或群发需要用户明确指令。

## 已选组件与使用场景

| 组件 | 什么内容下使用 | 放在什么位置 |
|---|---|---|
{chr(10).join(rows)}

完整的频率、素材要求与参数保存在profile.json，制作时结合对应子Skill读取。读者只需要提供本篇正文和素材，沿用已确认配置即可开始。

## 继续微调

用户明确要求以后沿用某项字号、颜色、间距或组件规则时，再同步profile.json与后续排版。单篇微调记录在当前稿件，已有稿件和用户改动先读取后更新。

组件包中的示例用于理解效果。账号身份、文章主文与实际素材采用本次配置和用户提供的内容。

所选组件的版本和来源见[组件来源记录](references/component-sources.json)。
'''


def make_archive(staged, destination):
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staged.rglob("*")):
            if path.is_file():
                name = (Path(staged.name) / path.relative_to(staged)).as_posix()
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("专属Skill压缩包完整性检查未通过")


def build(config, out_dir, library=None, downloads=None):
    snapshots = {}
    raw = read_file(config, snapshots, 5 * 1024 * 1024)
    profile = validate_profile(json.loads(raw.decode("utf-8-sig")))
    name = profile["skill_name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    destination, archive_path = out_dir / name, out_dir / (name + ".zip")
    if destination.exists() or destination.is_symlink() or archive_path.exists() or archive_path.is_symlink():
        raise ValueError("同名Skill文件夹或ZIP已存在，请换一个名称或输出位置")
    lock = out_dir / ("." + name + ".build.lock")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("同名Skill正在打包，请等本次运行结束后再重试") from None
    committed_zip = False
    zip_checksum = None
    try:
        handle.write(str(os.getpid()))
        handle.flush()
        with tempfile.TemporaryDirectory(prefix=".wechat-layout-build-", dir=out_dir) as temporary:
            temporary = Path(temporary)
            staged = temporary / name
            staged.mkdir()
            budget, local_sources, provenance = [0], [], []
            copy_profile_materials(profile, config.parent, staged, snapshots, budget)
            release, assets = (None, {}) if library or downloads else latest_assets()
            for component in profile["components"]:
                slug = component["id"]
                if library:
                    record, source = copy_local_component(library, slug, staged, snapshots, budget)
                    local_sources.append(source)
                else:
                    expected_digest = None
                    if downloads:
                        content = read_file(downloads / (slug + ".zip"), snapshots)
                        record = {"id": slug, "source": "local-download"}
                    else:
                        asset = assets.get(slug + ".zip")
                        if not asset:
                            raise ValueError(f"当前发布版本缺少组件包 {slug}")
                        url = asset.get("browser_download_url", "")
                        if not url.startswith(f"https://github.com/{REPOSITORY}/releases/download/"):
                            raise ValueError("组件下载地址与公开仓库不一致")
                        content = download(url, COMPONENT_LIMIT)
                        expected_digest = asset.get("digest")
                        record = {"id": slug, "source": "github-release", "release": release}
                    checksum = hashlib.sha256(content).hexdigest()
                    if expected_digest and expected_digest != "sha256:" + checksum:
                        raise ValueError(f"下载的组件校验值不一致 {slug}")
                    unpack_component(content, slug, staged, budget)
                    record["archive_sha256"] = checksum
                provenance.append(record)
            references = Path(__file__).resolve().parents[1] / "references"
            for filename in ["format-and-deliver.md", "environment.md"]:
                write_bytes(staged / "references" / filename, read_file(references / filename, snapshots), budget)
            license_source = library / "LICENSE" if library else staged / "components" / profile["components"][0]["id"] / "LICENSE"
            if license_source.is_file():
                write_bytes(staged / "LICENSE", read_file(license_source, snapshots), budget)
            profile_text = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
            write_bytes(staged / "profile.json", profile_text.encode("utf-8"), budget)
            write_bytes(staged / "SKILL.md", skill_text(profile, staged).encode("utf-8"), budget)
            write_bytes(staged / "references/component-sources.json", (json.dumps(provenance, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), budget)
            staged_archive = temporary / (name + ".zip")
            make_archive(staged, staged_archive)
            zip_checksum = hashlib.sha256(staged_archive.read_bytes()).hexdigest()
            if any(not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum for path, checksum in snapshots.items()):
                raise ValueError("打包期间输入资料发生变化，请重新运行")
            if any(component_files(directory) != files for directory, files in local_sources):
                raise ValueError("打包期间组件材料发生变化，请重新运行")
            if destination.exists() or destination.is_symlink():
                raise ValueError("输出目录已被其他操作创建，请换名称或输出位置")
            os.link(staged_archive, archive_path)
            committed_zip = True
            os.rename(staged, destination)
            committed_zip = False
        return {"status": "built", "skill_directory": str(destination), "zip": str(archive_path), "components": len(profile["components"]), "source": "local-library" if library else "local-downloads" if downloads else "github-release", "release": release, "zip_sha256": zip_checksum}
    except BaseException:
        if committed_zip and archive_path.is_file() and hashlib.sha256(archive_path.read_bytes()).hexdigest() == zip_checksum:
            archive_path.unlink()
        raise
    finally:
        handle.close()
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="已确认的个人排版配置JSON")
    parser.add_argument("--out-dir", required=True, type=Path, help="专属Skill文件夹与ZIP的父目录")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--library-root", type=Path, help="使用已下载的完整组件库")
    source.add_argument("--downloads-dir", type=Path, help="使用已有的单项组件ZIP")
    args = parser.parse_args()
    try:
        result = build(args.config.resolve(), args.out_dir.resolve(), args.library_root.resolve() if args.library_root else None, args.downloads_dir.resolve() if args.downloads_dir else None)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "needs_input", "message": str(error)}, ensure_ascii=True))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
