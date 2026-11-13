"""Update release and per-Skill instructions after all thirty GIFs are complete."""

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
VERSION = "0.5.0"
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
    actual = gif_info(gif)
    expected_play = "operation-illustration" if entry.kind == "workflow" else "component-demo"
    if not isinstance(metadata, dict) or metadata.get("slug") != entry.name:
        raise ValueError(f"GIF记录的组件身份不一致 {sidecar}")
    if metadata.get("source") != "browser-capture" or metadata.get("play") != expected_play:
        raise ValueError(f"GIF来源或演示类型不一致 {sidecar}")
    if metadata.get("visible_changes") is not True or isinstance(metadata.get("loop"), bool) or metadata.get("loop") != 0:
        raise ValueError(f"GIF需要可见变化并循环播放 {sidecar}")
    for field in ["distinct_frames", "source_frame_count"]:
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise ValueError(f"GIF记录缺少有效的{field} {sidecar}")
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


def layout_evidence(root, snapshots):
    path = root / "output/brand-audit/narrow-checks.json"
    if not path.is_file():
        return set()
    rows = read_json(path, snapshots)
    if not isinstance(rows, list):
        raise ValueError(f"窄屏检查记录需要数组 {path}")
    passed = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("width") not in {320, 375}:
            continue
        if row.get("pageOverflow") is not False or row.get("readingOverflow") is not False or row.get("duplicates") != []:
            raise ValueError(f"窄屏检查存在未通过项 {row.get('slug')}")
        passed.add((row.get("slug"), row["width"]))
    return passed


def capture_evidence(root, entry, metadata, snapshots):
    path = root / "output/brand-gif-frames" / entry.name / "frames.json"
    if not path.is_file():
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


def style_record(entry, record, metadata, assets, captured, widths):
    workflow = entry.kind == "workflow"
    return {
        "version": VERSION,
        "component": entry.name,
        "title": entry.title,
        "kind": entry.kind,
        "author_ip": {
            "demo_name": "FRE.D 进一",
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
            "image_placement": "配图留在对应动画组或状态组中",
            "interaction": "保留事件ID、SMIL时序及透明点击区",
            "multiple_instances": "为各实例生成独立ID，并同步更新事件与素材引用",
            "standalone_reuse": "读取本组件HTML模板及相邻素材，按本次正文与风格修改",
        },
        "validation": {
            "gif_sha256": metadata["sha256"],
            "gif_frames": metadata["frame_count"],
            "gif_size": [metadata["width"], metadata["height"]],
            "browser_capture_600": captured,
            "layout_widths": widths,
            "demo_type": "operation-illustration" if workflow else "component-demo",
            "editor_save_reload": "pending-for-branded-output",
            "wechat_sync_and_phone": "pending",
            "native_account_jump": "pending-in-wechat" if entry.name == "wechat-avatar-profile" else "not-applicable",
        },
    }


def section_text(entry, captured, widths):
    opener = "操作示意" if entry.kind == "workflow" else "可操作演示"
    text = f'''{SECTION}

[查看{opener}](examples/brand-preview.html) · [查看GIF](examples/demo.gif) · [读取品牌样式与素材](examples/brand-style.json)

1. 先看GIF选择效果，再读取 `examples/brand-style.json` 和 `examples/brand-component.html`，确认本组件的画布、配色及素材。
2. 按本次任务采用使用者自己的头像、账号资料、正文与配图。直接修改本地品牌HTML模板和相邻素材即可复用单项包。原有生成器的参数能力以本Skill正文为准。
3. 文字保留原生编辑。图片放在对应动画组或状态组里，保留事件ID、SMIL时序与透明点击区。同篇放多个实例时，分别生成独立ID并同步事件引用。
4. 修改后检查完整动作与返回，核对文字、图片和按钮边界，再检查目标编辑器中的保存结果。
'''
    evidence = []
    if captured:
        evidence.append("600px浏览器操作／播放采集")
    if widths == [320, 375]:
        evidence.append("320／375px布局检查")
    if evidence:
        text += "\n本版已有" + "、".join(evidence) + "，GIF记录与实际文件校验一致。\n"
    if entry.kind == "workflow":
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

30套组件Skill，先看GIF选效果，再让AI替你排版。

[查看30款品牌GIF演示]({ONLINE}{GALLERY}) · [下载完整组件库]({DOWNLOAD}) · [查看原版交互目录](examples/preview.html) · [选择单项Skill](#30个入口)

v{VERSION}提供全部30款品牌演示与对应GIF，采用纸纹、暖橙和橙帽Fred的示例风格。每项包含可读的Skill、本地HTML模板、独立素材和品牌样式JSON，下载单项包后即可交给AI修改。

已有600px浏览器操作／播放采集记录{captured}／30项、320／375px布局检查{narrow}／30项。头像入口与秀米原生布局提供操作示意。品牌输出的秀米保存重开、公众号同步和真实手机微信效果按目标平台继续核对，各组件原有检查记录见下表。

'''
    return intro + text[heading.start():]


def root_skill(text):
    text, count = re.subn(r'(?m)^  version: "[^"]+"$', f'  version: "{VERSION}"', text, count=1)
    if count != 1:
        raise ValueError("根Skill版本字段已变化，请先核对")
    text = re.sub(r"(?m)^拆信、探照灯和多层视差另有[^\n]+\n\n", "", text, count=1)
    section = f'''{SECTION}

先看[全部30款品牌GIF演示]({GALLERY})，按正文需要选择效果，再读取对应子Skill和 `examples/brand-style.json`。

单项包包含品牌HTML、GIF及其相邻素材。读取 `examples/brand-component.html` 后，可按使用者自己的头像、正文和风格修改。图片留在对应动画组或状态组中，保留事件ID、点击区与时序；多个实例使用独立ID。原有生成器的可用参数以对应子Skill正文为准。

头像入口和秀米原生布局提供操作示意。交付时分别说明本地浏览器、编辑器保存重开、公众号同步和真实手机微信的实际验证范围。
'''
    return replace_section(text, section)


def root_index(text):
    old, new = "examples/preview.html", GALLERY
    if new in text and old not in text:
        return text
    if old not in text:
        raise ValueError("首页使用了其他入口，请先核对index.html")
    return (text.replace(old, new)
            .replace("公众号组件交互预览", "公众号排版外挂 · 30款品牌GIF演示")
            .replace("#f5f3ed", "#f5f2eb")
            .replace("#26383e", "#30271f")
            .replace("#167e99", "#a64c24"))


def build_changes(root):
    snapshots, plans = {}, {}
    manifest = read_json(root / "assets/brand/demo-manifest.json", snapshots)
    if not isinstance(manifest, list) or len(manifest) != 30 or len(ENTRIES) != 30:
        raise ValueError("需要全部30款演示清单")
    records = {record.get("slug"): record for record in manifest if isinstance(record, dict)}
    if len(records) != 30 or set(records) != {entry.name for entry in ENTRIES}:
        raise ValueError("演示清单的组件身份重复或不完整")
    layouts = layout_evidence(root, snapshots)
    captured_count, narrow_count = 0, 0
    for entry in ENTRIES:
        record = records[entry.name]
        if record.get("kind") != entry.kind or record.get("title") != entry.title:
            raise ValueError(f"演示清单与组件目录不一致 {entry.name}")
        metadata, assets = gif_record(root, entry, record, snapshots)
        captured = capture_evidence(root, entry, metadata, snapshots)
        widths = [width for width in [320, 375] if (entry.name, width) in layouts]
        captured_count += int(captured)
        narrow_count += int(widths == [320, 375])
        folder = root / "skills" / entry.name
        skill, newline, bom = text_source(folder / "SKILL.md", snapshots)
        plans[folder / "SKILL.md"] = encoded_text(replace_section(skill, section_text(entry, captured, widths)), newline, bom)
        style = style_record(entry, record, metadata, assets, captured, widths)
        plans[folder / "examples/brand-style.json"] = (json.dumps(style, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for name, transform in [("README.md", lambda text: root_readme(text, captured_count, narrow_count)), ("SKILL.md", root_skill), ("index.html", root_index)]:
        text, newline, bom = text_source(root / name, snapshots)
        plans[root / name] = encoded_text(transform(text), newline, bom)
    for target in plans:
        if not target.resolve().is_relative_to(root) or target.is_symlink() or target.is_dir():
            raise ValueError(f"文档输出需要库内普通文件 {target}")
        if target.exists():
            read_source(target, snapshots)
    return plans, snapshots, {"components": 30, "captured_600": captured_count, "layout_320_375": narrow_count}


def update(root, overwrite):
    root = root.resolve()
    lock = root / ".brand-docs.lock"
    handle = lock.open("x", encoding="utf-8")
    staged = {}
    try:
        handle.write("updating branded component instructions\n")
        plans, snapshots, result = build_changes(root)
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
    args = parser.parse_args()
    try:
        result = update(args.root, args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
