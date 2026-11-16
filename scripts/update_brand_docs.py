"""Update release and selected Skill instructions from verified demonstration files."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from build_brand_catalog import gif_info
from build_downloads import digest, temporary_file
from build_preview import ENTRIES
from encode_demo_gifs import commit_pair


SECTION = "## 品牌演示与GIF"
VERSION = "0.7.0"
GALLERY = "examples/brand-gallery.html"
ONLINE = "https://frederick-kk.github.io/wechat-layout-copilot/"
DOWNLOAD = (
    "https://github.com/frederick-kk/wechat-layout-copilot/"
    "releases/latest/download/wechat-layout-copilot.zip"
)
TOKENS = {
    "paper_base": "#FAF6ED",
    "warm_white": "#FFFCF6",
    "ink": "#30271F",
    "accent": "#A94B21",
    "muted": "#765B45",
    "rule": "#C6AA7B",
}


def read_source(path, snapshots):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"需要普通来源文件 {path}")
    content = path.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    if path in snapshots and snapshots[path] != checksum:
        raise ValueError(f"读取期间来源已变化 {path}")
    snapshots[path] = checksum
    return content


def read_json(path, snapshots):
    return json.loads(read_source(path, snapshots).decode("utf-8-sig"))


def finite_positive(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0
    )


def gif_record(root, entry, record, snapshots):
    examples = root / "skills" / entry.name / "examples"
    preview = examples / "brand-preview.html"
    component = examples / "brand-component.html"
    gif = examples / "demo.gif"
    sidecar = examples / "demo-gif.json"
    preview_bytes = read_source(preview, snapshots)
    component_bytes = read_source(component, snapshots)
    gif_bytes = read_source(gif, snapshots)
    metadata = read_json(sidecar, snapshots)
    actual = gif_info(gif, allow_static=entry.kind == "html")
    expected_play = "operation-illustration" if entry.kind == "workflow" else "component-demo"
    if not isinstance(metadata, dict) or metadata.get("slug") != entry.name:
        raise ValueError(f"GIF记录的组件身份不一致 {sidecar}")
    if metadata.get("source") != "browser-capture" or metadata.get("play") != expected_play:
        raise ValueError(f"GIF来源或演示类型不一致 {sidecar}")
    if (entry.kind != "html" and metadata.get("visible_changes") is not True) or isinstance(metadata.get("loop"), bool) or metadata.get("loop") != 0:
        raise ValueError(f"GIF需要可见变化并循环播放 {sidecar}")
    for field in ["distinct_frames", "source_frame_count"]:
        value = metadata.get(field)
        minimum = 1 if entry.kind == "html" and field == "distinct_frames" else 2
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"GIF记录缺少有效的{field} {sidecar}")
    if metadata.get("visible_changes") != (metadata["distinct_frames"] > 1):
        raise ValueError(f"GIF变化标记与实际不同画面数量不一致 {sidecar}")
    if not finite_positive(metadata.get("duration_seconds")):
        raise ValueError(f"GIF记录缺少有效播放时长 {sidecar}")
    for key, value in [("width", actual["width"]), ("height", actual["height"]), ("frame_count", actual["frames"])]:
        if isinstance(metadata.get(key), bool) or metadata.get(key) != value:
            raise ValueError(f"GIF的{key}与实际文件不一致 {sidecar}")
    if metadata.get("sha256") != hashlib.sha256(gif_bytes).hexdigest() or metadata.get("bytes") != len(gif_bytes):
        raise ValueError(f"GIF校验值或字节数不一致 {sidecar}")
    canvas = record.get("canvas")
    if not isinstance(canvas, list) or len(canvas) != 2 or not all(finite_positive(value) for value in canvas):
        raise ValueError(f"演示清单缺少有效画布尺寸 {entry.name}")
    if actual["width"] > canvas[0]:
        raise ValueError(f"GIF宽度大于采集画布 {entry.name}")
    expected_height = actual["width"] * canvas[1] / canvas[0]
    if abs(actual["height"] - expected_height) > 1.5:
        raise ValueError(f"GIF比例与输出舞台不一致 {entry.name}")
    if record.get("preview") != preview.relative_to(root).as_posix() or record.get("gif") != gif.relative_to(root).as_posix():
        raise ValueError(f"演示清单中的文件位置不一致 {entry.name}")
    filenames = record.get("assets")
    if not isinstance(filenames, list) or not filenames or len(set(filenames)) != len(filenames):
        raise ValueError(f"演示清单缺少独立素材列表 {entry.name}")
    assets = {}
    for filename in filenames:
        if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9-]+\.webp", filename):
            raise ValueError(f"素材需要组件内文件名 {entry.name}")
        source = examples / "brand-assets" / filename
        content = read_source(source, snapshots)
        assets[Path(filename).stem] = {
            "path": "brand-assets/" + filename,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    referenced = set(re.findall(r"brand-assets/([a-z0-9-]+\.webp)", (preview_bytes + component_bytes).decode("utf-8")))
    if referenced != set(filenames):
        raise ValueError(f"演示素材与清单不一致 {entry.name}")
    return metadata, assets


def layout_evidence(root, snapshots, extra_records=None):
    paths = [root / "output/brand-audit/narrow-checks.json"]
    paths.extend(extra_records or [])
    passed = set()
    for path in paths:
        if not path.is_file():
            if path in (extra_records or []):
                raise ValueError("本轮窄屏检查文件缺失 " + str(path))
            continue
        rows = read_json(path, snapshots)
        if not isinstance(rows, list):
            raise ValueError("窄屏检查记录需要数组 " + str(path))
        for row in rows:
            if not isinstance(row, dict) or row.get("width") not in {320, 375}:
                continue
            if "pageOverflow" in row:
                valid = row.get("pageOverflow") is False and row.get("readingOverflow") is False and row.get("duplicates") == []
            else:
                layout = row.get("layout", {})
                valid = (row.get("passed") is True and isinstance(layout, dict)
                         and layout.get("viewport") == row["width"]
                         and finite_positive(layout.get("width"))
                         and layout["width"] <= row["width"] + 0.5)
            if not valid or not isinstance(row.get("slug"), str):
                raise ValueError(f"窄屏检查存在未通过项 {row.get('slug')}")
            passed.add((row["slug"], row["width"]))
    return passed


def capture_evidence(root, entry, metadata, snapshots, frames_root=None):
    candidates = []
    if frames_root is not None:
        candidates.append(frames_root / entry.name / "frames.json")
    candidates.append(root / "output/brand-gif-frames" / entry.name / "frames.json")
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return False
    capture = read_json(path, snapshots)
    if capture.get("completed") is not True or capture.get("source") != "browser-capture" or capture.get("slug") != entry.name:
        raise ValueError(f"浏览器采集记录未完成 {path}")
    if capture.get("width") != 600 or not finite_positive(capture.get("height")):
        raise ValueError(f"浏览器采集需要600宽度舞台 {path}")
    if not isinstance(capture.get("actions"), list) or not capture["actions"]:
        raise ValueError(f"浏览器采集缺少操作或播放记录 {path}")
    if not isinstance(capture.get("frames"), list) or len(capture["frames"]) != metadata["source_frame_count"]:
        raise ValueError(f"浏览器采集帧数与GIF记录不一致 {path}")
    if snapshots[path] != metadata.get("source_manifest_sha256"):
        raise ValueError(f"浏览器采集清单已变化 {path}")
    return True


def real_recording(root, snapshots):
    folder = root / "skills/wechat-avatar-profile/examples"
    source = folder / "real-demo.json"
    if not source.is_file():
        return None
    record = read_json(source, snapshots)
    expected = {"video": "account-jump-real.mp4", "viewer": "real-demo.html", "poster": "account-jump-poster.jpg"}
    if any(record.get(key) != filename for key, filename in expected.items()):
        raise ValueError("头像实录的素材位置与组件目录不一致")
    video = read_source(folder / record["video"], snapshots)
    if record.get("sha256") != hashlib.sha256(video).hexdigest() or record.get("bytes") != len(video):
        raise ValueError("头像实录与原片校验记录不一致")
    read_source(folder / record["viewer"], snapshots)
    read_source(folder / record["poster"], snapshots)
    return record


def style_record(entry, record, metadata, assets, captured, widths, recording=None):
    workflow = entry.kind == "workflow"
    result = {
        "version": VERSION,
        "component": entry.name,
        "title": entry.title,
        "kind": entry.kind,
        "author_ip": {
            "demo_name": "小鱼FRED",
            "avatar": assets.get("avatar", {}).get("path"),
            "reuse": "按本次任务采用使用者自己的头像、账号资料和正文",
        },
        "tokens": TOKENS,
        "assets": assets,
        "output_stage": {
            "width": record["canvas"][0],
            "height": record["canvas"][1],
            "aspect_ratio": record["canvas"][0] / record["canvas"][1],
        },
        "files": {
            "template": "brand-component.html",
            "preview": "brand-preview.html",
            "gif": "demo.gif",
            "gif_record": "demo-gif.json",
        },
        "editing": {
            "native_text_editable": True,
            "image_placement": "配图沿用原生HTML中的位置与相邻素材" if entry.kind == "html" else "配图留在对应动画组或状态组中",
            "interaction": "保留原生横滑、展开和视频控件，发布时按目标平台入口检查" if entry.kind == "html" else "保留事件ID、SMIL时序及透明点击区",
            "multiple_instances": "为各实例生成独立ID，并同步更新事件与素材引用",
            "standalone_reuse": "读取本组件HTML模板及相邻素材，按本次正文与风格修改",
        },
        "validation": {
            "gif_sha256": metadata["sha256"],
            "gif_frames": metadata["frame_count"],
            "visible_changes": metadata["visible_changes"],
            "gif_size": [metadata["width"], metadata["height"]],
            "browser_capture_600": captured,
            "layout_widths": widths,
            "demo_type": "operation-illustration" if workflow else "component-demo",
            "editor_save_reload": "pending-for-branded-output",
            "wechat_sync_and_phone": "pending",
            "native_account_jump": "pending-in-wechat" if entry.name == "wechat-avatar-profile" else "not-applicable",
        },
    }
    if recording and entry.name == "wechat-avatar-profile":
        result["files"].update({
            "real_recording": recording["video"],
            "real_demo": recording["viewer"],
            "real_recording_record": "real-demo.json",
        })
        result["validation"]["native_account_jump"] = "observed-in-user-supplied-recording"
        result["validation"]["phone_recording_scope"] = recording["scope"]
    return result


def section_text(entry, captured, widths, recording=None):
    opener = "操作示意" if entry.kind == "workflow" else "可操作演示"
    if entry.kind == "html":
        opener = "原生排版示例"
    interaction_step = "文字保留原生编辑。图片放在对应动画组或状态组里，保留事件ID、SMIL时序与透明点击区。同篇放多个实例时，分别生成独立ID并同步事件引用。"
    if entry.kind == "html":
        interaction_step = "文字与图注保留原生HTML。沿用横滑、展开或视频控件；涉及秀米和公众号的部分按本Skill原生入口制作，再核对保存、同步和手机表现。"
    text = f'''{SECTION}

[查看{opener}](examples/brand-preview.html) · [查看GIF](examples/demo.gif) · [读取品牌样式与素材](examples/brand-style.json)

1. 先看GIF选择效果，再读取 `examples/brand-style.json` 和 `examples/brand-component.html`，确认本组件的画布、配色及素材。
2. 按本次任务采用使用者自己的头像、账号资料、正文与配图。直接修改本地品牌HTML模板和相邻素材即可复用单项包。原有生成器的参数能力以本Skill正文为准。
3. {interaction_step}
4. 修改后检查完整动作与返回，核对文字、图片和按钮边界，再检查目标编辑器中的保存结果。
'''
    evidence = []
    if captured:
        evidence.append("600px浏览器操作／播放采集")
    if widths == [320, 375]:
        evidence.append("320／375px布局检查")
    if evidence:
        text += "\n本版已有" + "、".join(evidence) + "，GIF记录与实际文件校验一致。\n"
    if recording and entry.name == "wechat-avatar-profile":
        text += "\n[查看手机微信真实跳转录像](examples/real-demo.html) · [下载完整原片](examples/account-jump-real.mp4) · [读取录像来源记录](examples/real-demo.json)\n"
        text += "\n用户提供的完整手机实录展示了文章头像入口、微信确认弹窗及进入“小鱼FRED”公众号主页的过程。复用到自己的账号和新稿时，按本Skill的编辑器与手机检查步骤核对。\n"
    elif entry.kind == "workflow":
        text += "\n本组件演示为操作流程示意。真实公众号名片、秀米保存重开、公众号同步与手机效果按目标平台继续核对。\n"
    else:
        text += "\n品牌输出的秀米保存重开、公众号同步与真实手机微信效果待按目标环境核对。\n"
    return text


def replace_section(text, section):
    pattern = re.compile(r"(?ms)^## 品牌演示与GIF\n.*?(?=^## |\Z)")
    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise ValueError("文档存在重复品牌演示章节，请先核对")
    if matches:
        suffix = text[matches[0].end():]
        ending = "\n\n" + suffix if suffix else "\n"
        return text[:matches[0].start()] + section.rstrip() + ending
    return text.rstrip() + "\n\n" + section.rstrip() + "\n"


def text_source(path, snapshots):
    data = read_source(path, snapshots)
    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n"), "\r\n" if "\r\n" in text else "\n", data.startswith(b"\xef\xbb\xbf")


def encoded_text(text, newline, bom):
    return (b"\xef\xbb\xbf" if bom else b"") + text.replace("\n", newline).encode("utf-8")


def root_readme(text, captured, narrow):
    heading = re.search(r"(?m)^## ", text)
    if not text.startswith("# 公众号排版外挂\n") or heading is None:
        raise ValueError("README入口结构已变化，请先核对")
    intro = f'''# 公众号排版外挂

{len(ENTRIES)}套组件Skill，先看示例选效果，再让AI替你排版。

[首次配置下载上手Skill](https://github.com/frederick-kk/wechat-layout-copilot/releases/download/v{VERSION}/wechat-layout-starter.zip) · [读取完整上手流程](workflows/wechat-layout-starter/SKILL.md)

让AI检查环境、学习你的旧稿、引导选择组件，再生成属于你的本地排版Skill。以后提供正文，按个人风格完成排版与草稿保存。

[查看{len(ENTRIES)}款品牌演示]({GALLERY}) · [下载完整组件库](https://github.com/frederick-kk/wechat-layout-copilot/releases/download/v{VERSION}/wechat-layout-copilot.zip) · [查看原版交互目录](examples/preview.html) · [选择单项Skill](#{len(ENTRIES)}个入口)

[直接看本轮新增组件]({GALLERY}#new-components)

v{VERSION}提供{len(ENTRIES)}款品牌示例，采用纸纹、暖橙和橙帽Fred的示例风格。静态原生排版按实际画面提供静帧或GIF。每项包含可读的Skill、本地HTML模板、独立素材和品牌样式JSON。

已有600px浏览器操作／播放采集记录{captured}／{len(ENTRIES)}项、320／375px布局检查{narrow}／{len(ENTRIES)}项。头像入口另附[手机微信真实跳转录像](skills/wechat-avatar-profile/examples/real-demo.html)，秀米原生布局提供操作示意。各组件的目标账号保存、同步与手机检查范围见下表。

'''
    return intro + text[heading.start():]


def root_skill(text):
    text, count = re.subn(r'(?m)^  version: "[^"]+"$', f'  version: "{VERSION}"', text, count=1)
    if count != 1:
        raise ValueError("根Skill版本字段已变化，请先核对")
    text = re.sub(r"(?m)^拆信、探照灯和多层视差另有[^\n]+\n\n", "", text, count=1)
    section = f'''{SECTION}

先看[{len(ENTRIES)}款品牌示例]({GALLERY})，按正文需要选择效果，再读取对应子Skill和 `examples/brand-style.json`。

单项包包含品牌HTML、GIF及其相邻素材。读取 `examples/brand-component.html` 后，可按使用者自己的头像、正文和风格修改。图片留在对应动画组或状态组中，保留事件ID、点击区与时序；多个实例使用独立ID。原有生成器的可用参数以对应子Skill正文为准。

头像入口另附[手机微信真实跳转录像](skills/wechat-avatar-profile/examples/real-demo.html)，秀米原生布局提供操作示意。交付时分别说明本地浏览器、编辑器保存重开、公众号同步和真实手机微信的实际验证范围。
'''
    return replace_section(text, section)


def root_index(text):
    old, new = "examples/preview.html", GALLERY
    if old not in text and new not in text:
        raise ValueError("首页使用了其他入口，请先核对index.html")
    text = re.sub(r"公众号排版外挂 · \d+款(?:本地品牌示例(?: · 待发布)?|品牌GIF演示)", f"公众号排版外挂 · {len(ENTRIES)}款品牌GIF演示", text)
    return (text.replace(old, new)
            .replace("公众号组件交互预览", f"公众号排版外挂 · {len(ENTRIES)}款品牌GIF演示")
            .replace("#f5f3ed", "#f5f2eb")
            .replace("#26383e", "#30271f")
            .replace("#167e99", "#a64c24"))


def build_changes(root, only=None, frames_root=None, layout_records=None):
    snapshots, plans = {}, {}
    manifest = read_json(root / "assets/brand/demo-manifest.json", snapshots)
    if not isinstance(manifest, list) or len(manifest) != len(ENTRIES) or not ENTRIES:
        raise ValueError("演示清单数量需要与组件入口一致")
    records = {record.get("slug"): record for record in manifest if isinstance(record, dict)}
    if len(records) != len(ENTRIES) or set(records) != {entry.name for entry in ENTRIES}:
        raise ValueError("演示清单的组件身份重复或不完整")
    layouts = layout_evidence(root, snapshots, layout_records)
    recording = real_recording(root, snapshots)
    captured_count, narrow_count = 0, 0
    for entry in ENTRIES:
        record = records[entry.name]
        if record.get("kind") != entry.kind or record.get("title") != entry.title:
            raise ValueError(f"演示清单与组件目录不一致 {entry.name}")
        metadata, assets = gif_record(root, entry, record, snapshots)
        captured = capture_evidence(root, entry, metadata, snapshots, frames_root)
        widths = [width for width in [320, 375] if (entry.name, width) in layouts]
        captured_count += int(captured)
        narrow_count += int(widths == [320, 375])
        if only is not None and entry.name not in only:
            continue
        folder = root / "skills" / entry.name
        skill, newline, bom = text_source(folder / "SKILL.md", snapshots)
        plans[folder / "SKILL.md"] = encoded_text(replace_section(skill, section_text(entry, captured, widths, recording)), newline, bom)
        style = style_record(entry, record, metadata, assets, captured, widths, recording)
        plans[folder / "examples/brand-style.json"] = (json.dumps(style, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        record["status"] = "gif-ready"
        record["gif_metadata"] = (folder / "examples/demo-gif.json").relative_to(root).as_posix()
    plans[root / "assets/brand/demo-manifest.json"] = (json.dumps([records[entry.name] for entry in ENTRIES], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for name, transform in [("README.md", lambda text: root_readme(text, captured_count, narrow_count)), ("SKILL.md", root_skill), ("index.html", root_index)]:
        text, newline, bom = text_source(root / name, snapshots)
        plans[root / name] = encoded_text(transform(text), newline, bom)
    for target in plans:
        if not target.resolve().is_relative_to(root) or target.is_symlink() or target.is_dir():
            raise ValueError(f"文档输出需要库内普通文件 {target}")
        if target.exists():
            read_source(target, snapshots)
    return plans, snapshots, {"components": len(ENTRIES), "captured_600": captured_count, "layout_320_375": narrow_count}


def update(root, overwrite, only=None, frames_root=None, layout_records=None):
    root = root.resolve()
    lock = root / ".brand-docs.lock"
    handle = lock.open("x", encoding="utf-8")
    staged = {}
    try:
        handle.write("updating branded component instructions\n")
        plans, snapshots, result = build_changes(root, only, frames_root, layout_records)
        changed = {path: content for path, content in plans.items() if not path.is_file() or path.read_bytes() != content}
        if not overwrite and any(path.exists() for path in changed):
            raise ValueError("更新已有文档需要明确使用--overwrite")
        previous = {path: digest(path) for path in changed}
        for path, content in changed.items():
            staged[path] = temporary_file(path.parent, ".brand-docs.part")
            staged[path].write_bytes(content)
        if any(digest(path) != checksum for path, checksum in snapshots.items()):
            raise ValueError("生成期间来源或文档发生变化，请保留新内容后重试")
        commit_pair(staged, previous)
        result["updated_files"] = len(changed)
        return result
    finally:
        for source in staged.values():
            source.unlink(missing_ok=True)
        handle.close()
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--overwrite", action="store_true", help="更新已有的品牌演示章节与样式记录")
    parser.add_argument("--only", nargs="+", choices=[entry.name for entry in ENTRIES], help="仅更新指定组件及根文档，保留其他组件文件")
    parser.add_argument("--frames-root", type=Path, help="本轮采集帧目录，已有组件继续回查原采集目录")
    parser.add_argument("--layout-records", nargs="+", type=Path, help="本轮窄屏检查JSON数组，合并已有原记录")
    args = parser.parse_args()
    try:
        result = update(args.root, args.overwrite, set(args.only) if args.only else None, args.frames_root, args.layout_records)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
