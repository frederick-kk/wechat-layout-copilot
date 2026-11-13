"""Render a click-controlled before/after wipe using SVG and SMIL."""

import argparse
import base64
import html
import json
import math
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def xml_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 需要非空文字")
    for character in value:
        point = ord(character)
        valid = point in {9, 10, 13} or 32 <= point <= 0xD7FF or 0xE000 <= point <= 0x10FFFF
        if not valid or 0xFDD0 <= point <= 0xFDEF or point & 0xFFFF in {0xFFFE, 0xFFFF}:
            raise ValueError(f"{field} 含无法写入 XML 的字符 U+{point:04X}")
    return value


def wrap(value, field, width, maximum):
    xml_text(value, field)
    result = []
    for paragraph in value.split("\n"):
        line = ""
        used = 0
        for character in paragraph:
            advance = 0 if unicodedata.combining(character) or character == "\u200d" else 1
            if character.isascii() and character not in "WM@#%&":
                advance = 0.8
            if line and used + advance > width:
                result.append(line)
                line, used = "", 0
            line += character
            used += advance
        result.append(line)
    if len(result) > maximum:
        raise ValueError(f"{field} 排成{len(result)}行，当前画面可容纳{maximum}行，请精简或拆分")
    return result


def color(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"{field} 请使用六位 HEX 色值")
    return value.upper()


def image_source(value, directory, inputs, field):
    xml_text(value, field)
    parsed = urlsplit(value)
    if parsed.scheme == "https":
        if not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
            raise ValueError(f"{field} 需要有效 HTTPS 图片地址")
        return value
    if parsed.scheme and not re.match(r"^[A-Za-z]:[/\\]", value):
        raise ValueError(f"{field} 支持本地 PNG、JPEG、WebP 或 HTTPS 地址")
    path = Path(value)
    if not path.is_absolute():
        path = directory / path
    inputs.add(path.resolve())
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError(f"{field} 文件头需要 PNG、JPEG 或 WebP")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def read_config(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置需要 JSON 对象")
    unknown = set(config) - {"title", "before", "after", "accent", "background", "duration"}
    if unknown:
        raise ValueError("未知配置字段 " + ", ".join(sorted(unknown)))
    prepared = {"title": wrap(config.get("title"), "title", 14, 1),
                "accent": color(config.get("accent", "#177F91"), "accent"),
                "background": color(config.get("background", "#FFF9EF"), "background"),
                "inputs": {path.resolve()}}
    seconds = config.get("duration", 0.7)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0.15 <= seconds <= 3:
        raise ValueError("duration 需要0.15到3之间的秒数")
    prepared["duration"] = seconds
    for name in ["before", "after"]:
        item = config.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"{name} 需要 label、title、body，可选 image")
        if set(item) - {"label", "title", "body", "image"}:
            raise ValueError(f"{name} 含未知字段")
        scene = {"label": wrap(item.get("label"), f"{name}.label", 6, 1)}
        scene["image"] = image_source(item["image"], path.parent, prepared["inputs"], f"{name}.image") if "image" in item else None
        scene["title"] = wrap(item.get("title"), f"{name}.title", 13, 2) if "title" in item or not scene["image"] else []
        scene["body"] = wrap(item.get("body"), f"{name}.body", 13, 4) if "body" in item or not scene["image"] else []
        prepared[name] = scene
    return prepared


def text_nodes(lines, x, y, size, fill, weight="400", spacing=44):
    nodes = []
    for index, line in enumerate(lines):
        baseline = y + index * spacing
        nodes.append(
            f'<text x="{x}" y="{baseline}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" font-family="sans-serif" xml:space="preserve">'
            f'{html.escape(line)}</text>'
        )
    return "\n".join(nodes)


def scene(item, accent, background, after):
    nodes = [f'<rect x="0" y="80" width="600" height="390" fill="{background}"/>']
    if item["image"]:
        source = html.escape(item["image"], quote=True)
        nodes.append(f'<image x="0" y="80" width="600" height="390" href="{source}" xlink:href="{source}" preserveAspectRatio="xMidYMid meet"/>')
    else:
        if after:
            nodes.append(f'<rect x="32" y="112" width="536" height="326" rx="18" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>')
            nodes.append(f'<rect x="52" y="150" width="8" height="250" rx="4" fill="{accent}"/>')
        else:
            nodes.append('<path d="M32 122H568 M32 432H568" stroke="#A9B4B9" stroke-width="2" stroke-dasharray="5 8"/>')
        title_color = accent if after else "#68777E"
        nodes.append(text_nodes(item["title"], 80 if after else 40, 170, 36, title_color, "700"))
        nodes.append(text_nodes(item["body"], 80 if after else 40, 284, 34, "#27383F", spacing=42))
    nodes.append(f'<rect x="20" y="92" width="200" height="44" rx="10" fill="{accent if after else "#68777E"}"/>')
    nodes.append(text_nodes(item["label"], 34, 123, 26, "#FFFFFF", "700"))
    return "\n".join(nodes)


def render(config, prefix):
    accent = config["accent"]
    background = config["background"]
    seconds = config["duration"]
    forward, reverse = f"{prefix}_after", f"{prefix}_before"
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 600 600" width="100%" style="display:block;width:100%;height:auto;" data-component="wechat-svg-wipe-compare" role="group" aria-label="点击擦拭查看前后对比">
<desc>点击右侧按钮擦出制作后画面，点击左侧按钮回到制作前。</desc>
<rect width="600" height="600" rx="20" fill="{background}"/>
{text_nodes(config['title'], 30, 48, 36, '#27383F', '700')}
{scene(config['before'], accent, background, False)}
<svg x="-600" y="0" width="600" height="480" overflow="hidden" style="width:600px;height:480px;overflow:hidden;" data-wipe-layer="after">
<animate attributeName="x" attributeType="XML" from="-600" to="0" begin="{forward}.click" dur="{seconds}s" fill="freeze"/>
<animate attributeName="x" attributeType="XML" from="0" to="-600" begin="{reverse}.click" dur="{seconds}s" fill="freeze"/>
<g transform="translate(600 0)" data-wipe-content="after">
<animateTransform attributeName="transform" type="translate" from="600 0" to="0 0" begin="{forward}.click" dur="{seconds}s" fill="freeze"/>
<animateTransform attributeName="transform" type="translate" from="0 0" to="600 0" begin="{reverse}.click" dur="{seconds}s" fill="freeze"/>
{scene(config['after'], accent, background, True)}
</g>
</svg>
<g id="{reverse}" data-wipe-trigger="before" opacity="0.45" style="cursor:pointer;pointer-events:none;opacity:0.45;">
<set attributeName="pointer-events" to="none" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="pointer-events" to="auto" begin="{forward}.click+{seconds}s" fill="freeze"/>
<set attributeName="opacity" to="0.45" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="opacity" to="1" begin="{forward}.click+{seconds}s" fill="freeze"/>
<rect x="24" y="510" width="264" height="62" rx="12" fill="#68777E"/>
{text_nodes(['回到制作前'], 70, 551, 30, '#FFFFFF', '700')}
</g>
<g id="{forward}" data-wipe-trigger="after" opacity="1" style="cursor:pointer;pointer-events:auto;opacity:1;">
<set attributeName="pointer-events" to="none" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="pointer-events" to="auto" begin="{reverse}.click+{seconds}s" fill="freeze"/>
<set attributeName="opacity" to="0.45" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="opacity" to="1" begin="{reverse}.click+{seconds}s" fill="freeze"/>
<rect x="312" y="510" width="264" height="62" rx="12" fill="{accent}"/>
{text_nodes(['查看制作后'], 358, 551, 30, '#FFFFFF', '700')}
</g>
</svg></section>
'''


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>点击擦拭前后对比</title><body style="margin:0;background:#F5F3ED;font-family:system-ui,sans-serif;color:#27383F;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">点击擦拭前后对比</h1><p style="line-height:1.8;">点击亮起的按钮切换，动画完成后可以切回。</p>{fragment}</main></body></html>'''


def write_outputs(targets, payloads, overwrite):
    staged, committed, backups = [], [], {}
    preserve = set()
    try:
        for target, content in zip(targets, payloads):
            target.parent.mkdir(parents=True, exist_ok=True)
            if overwrite and target.exists():
                descriptor, name = tempfile.mkstemp(prefix=".svg_previous_", dir=target.parent)
                os.close(descriptor)
                backups[target] = Path(name)
                shutil.copy2(target, name)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((target, temporary))
                stream.write(content)
        for target, temporary in staged:
            if overwrite:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)
            committed.append(target)
    except OSError as error:
        problems = []
        for target in reversed(committed):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                if target in backups:
                    preserve.add(backups[target])
                    problems.append(f"原文件备份保留于 {backups[target]}")
                else:
                    problems.append(f"请检查本次输出 {target}")
        raise OSError(str(error) + ("；" + "；".join(problems) if problems else "")) from error
    finally:
        for path in [temporary for _, temporary in staged] + list(backups.values()):
            if path not in preserve:
                path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    try:
        config = read_config(args.config)
        resolved = [path.resolve() for path in targets]
        if len(set(resolved)) != len(resolved):
            raise ValueError("片段和预览需要不同路径")
        if config["inputs"].intersection(resolved):
            raise ValueError("输出不能覆盖配置文件或本地源图片")
        if any(path.is_dir() for path in targets):
            raise ValueError("输出路径指向目录，请指定文件名")
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError("输出已存在，请换路径或使用 --overwrite")
        prefix = "wipe_" + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"files": [str(path.resolve()) for path in targets], "canvas": [600, 600],
                      "instance": prefix, "interaction": "click_wipe_with_reverse",
                      "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
