"""Render spotlight as an original SVG/SMIL component."""

import argparse
import base64
import html
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from pathlib import Path

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

def common_config(path, allowed):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置需要JSON对象")
    extra = set(config) - allowed - {"title", "accent", "background"}
    if extra:
        raise ValueError("未知配置字段 " + ", ".join(sorted(extra)))
    prepared = {
        "title": wrap(config.get("title"), "title", 14, 1),
        "accent": color(config.get("accent", "#167E99"), "accent"),
        "background": color(config.get("background", "#FFF9EF"), "background"),
        "inputs": {path.resolve()},
    }
    return config, prepared


def svg_start(config, component, height):
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;" data-component="{component}" role="group">
<rect width="600" height="{height}" rx="20" fill="{config['background']}"/>
{text_nodes(config['title'], 28, 53, 36, '#27383F', '700')}
'''


def visible_sets(events, visible, hidden, initial):
    style = 'visible' if initial else 'hidden'
    nodes = [f'visibility="{style}" style="visibility:{style};"']
    shows = ';'.join(events[name] for name in visible)
    hides = ';'.join(events[name] for name in hidden)
    return nodes[0], (f'<set attributeName="visibility" to="visible" begin="{shows}" fill="freeze"/>' if shows else '') + (f'<set attributeName="visibility" to="hidden" begin="{hides}" fill="freeze"/>' if hides else '')


def text_button(identifier, action, label, x, y, width, accent, foreground="#FFFFFF"):
    return f'''<g id="{identifier}" data-action="{action}" style="cursor:pointer;">
<rect x="{x}" y="{y}" width="{width}" height="60" rx="12" fill="{accent}"/>
<text x="{x+width/2:g}" y="{y+40}" text-anchor="middle" font-size="30" fill="{foreground}" font-family="sans-serif" style="pointer-events:none;">{html.escape(label)}</text>
</g>'''




TITLE = '探照灯窗口'
INSTRUCTION = '点击左、中、右按钮切换圆形窗口，也可查看全景或复原。'
PREFIX = 'spot_'
HEIGHT = 620
ARTWORK_HEIGHT = 800


def local_image(value, field, directory, inputs):
    if not isinstance(value, str) or not value.strip() or "://" in value or value.startswith("data:"):
        raise ValueError(f"{field} 需要本地 PNG、JPEG 或 WebP 图片路径")
    source = Path(value)
    if not source.is_absolute():
        source = directory / source
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"{field} 图片不存在")
    data = source.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError(f"{field} 图片内容需要 PNG、JPEG 或 WebP 格式")
    inputs.add(source)
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def read_config(path):
    config, prepared = common_config(path, {"items", "artwork"})
    items = config.get("items")
    if not isinstance(items, list) or len(items) != 3:
        raise ValueError("items需要三组label与body")
    prepared["items"] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {"label", "body"}:
            raise ValueError(f"items[{index}]需要label与body")
        prepared["items"].append({"label": wrap(item["label"], f"items[{index}].label", 3, 1),
                                  "body": wrap(item["body"], f"items[{index}].body", 4, 2)})
    if "artwork" in config:
        artwork = config["artwork"]
        if not isinstance(artwork, dict) or "scene" not in artwork or set(artwork) - {"scene", "paper"}:
            raise ValueError("artwork需要scene图片，可选paper纸纹")
        prepared["artwork"] = {
            key: local_image(value, f"artwork.{key}", path.resolve().parent, prepared["inputs"])
            for key, value in artwork.items()
        }
        prepared["accent"] = color(config.get("accent", "#A64C24"), "accent")
        prepared["background"] = color(config.get("background", "#FAF6ED"), "background")
    return prepared


def render(config, prefix):
    if "artwork" in config:
        return render_artwork(config, prefix)
    accent = config["accent"]
    nodes = [svg_start(config, "wechat-svg-spotlight", HEIGHT)]
    for index, item in enumerate(config["items"]):
        x = 28 + index * 184
        nodes.append(f'<rect x="{x}" y="118" width="176" height="320" rx="15" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>')
        label = html.escape(item["label"][0])
        nodes.append(f'<text x="{x+88}" y="220" text-anchor="middle" font-size="32" font-weight="700" font-family="sans-serif" fill="{accent}" xml:space="preserve">{label}</text>')
        nodes.append(text_nodes(item["body"], x+24, 285, 32, '#27383F', spacing=43))
    events = {name: f'{prefix}_{name}.click' for name in ['left', 'center', 'right', 'full', 'reset']}
    for index, name in enumerate(['left', 'center', 'right']):
        x = 116 + index * 184
        # Two subpaths create an actual circular transparent aperture in a solid cover.
        path = f'M 0 100 H 600 V 450 H 0 Z M {x-104} 276 a 104 104 0 1 0 208 0 a 104 104 0 1 0 -208 0 Z'
        shows = [name] + (['reset'] if name == 'center' else [])
        hides = [other for other in events if other not in shows]
        initial, commands = visible_sets(events, shows, hides, name == 'center')
        nodes.append(f'<g id="{prefix}_cover_{index}" data-spotlight-cover="{name}" {initial}>{commands}<path d="{path}" fill="#22343B" fill-rule="evenodd"/><circle cx="{x}" cy="276" r="104" fill="none" stroke="{accent}" stroke-width="5"/></g>')
    for index, (name, label) in enumerate([('left','左侧'),('center','中间'),('right','右侧'),('full','全景'),('reset','复原')]):
        nodes.append(text_button(f'{prefix}_{name}', name, label, 24+index*112, 480, 104, accent))
    nodes.append(text_nodes(['点按钮移动光圈，或查看全景'], 33, 594, 28, '#68777E'))
    nodes.append('</svg></section>')
    return '\n'.join(nodes)


def render_artwork(config, prefix):
    accent, artwork = config["accent"], config["artwork"]
    nodes = [svg_start(config, "wechat-svg-spotlight", ARTWORK_HEIGHT)]
    if "paper" in artwork:
        # Keep the native heading above a translucent paper texture.
        nodes.insert(1, f'<image x="0" y="68" width="600" height="732" href="{artwork["paper"]}" preserveAspectRatio="xMidYMid slice" opacity="0.36" style="pointer-events:none;"/>')
    nodes.append(text_nodes(["点亮一处，看看藏在细节里的线索"], 28, 87, 22, '#6A5141'))
    nodes.append(f'<svg x="0" y="108" width="600" height="360" viewBox="0 0 600 360" style="overflow:hidden;max-width:none;">'
                 f'<image x="0" y="0" width="600" height="360" href="{artwork["scene"]}" preserveAspectRatio="xMidYMid slice"/>'
                 '</svg>')
    events = {name: f'{prefix}_{name}.click' for name in ['left', 'center', 'right', 'full', 'reset']}
    for index, name in enumerate(['left', 'center', 'right']):
        center = 112 + index * 188
        path = f'M 0 108 H 600 V 468 H 0 Z M {center-96} 288 a 96 96 0 1 0 192 0 a 96 96 0 1 0 -192 0 Z'
        shows = [name] + (['reset'] if name == 'center' else [])
        hides = [other for other in events if other not in shows]
        initial, commands = visible_sets(events, shows, hides, name == 'center')
        nodes.append(f'<g id="{prefix}_cover_{index}" data-spotlight-cover="{name}" {initial}>'
                     f'{commands}<path d="{path}" fill="#30251D" fill-opacity="0.90" fill-rule="evenodd"/>'
                     f'<circle cx="{center}" cy="288" r="97" fill="none" stroke="#E8C184" stroke-width="3"/>'
                     '</g>')
    for index, item in enumerate(config["items"]):
        center = 112 + index * 188
        label = html.escape(item["label"][0])
        nodes.append(f'<text x="{center}" y="516" text-anchor="middle" font-size="30" font-weight="700" font-family="sans-serif" fill="{accent}" xml:space="preserve">{label}</text>')
        nodes.append(text_nodes(item["body"], center-56, 561, 28, '#30251D', spacing=38))
    nodes.append('<path d="M28 624H572" fill="none" stroke="#CBB89C" stroke-width="1"/>')
    for index, (name, label) in enumerate([('left','左侧'),('center','中间'),('right','右侧'),('full','全景'),('reset','复原')]):
        fill = accent if index < 3 else '#EDE1CB'
        foreground = '#FFFFFF' if index < 3 else '#4A382B'
        nodes.append(text_button(f'{prefix}_{name}', name, label, 24+index*112, 650, 104, fill, foreground))
    nodes.append(text_nodes(['想看完整画面，点一下「全景」'], 50, 757, 28, '#6A5141'))
    nodes.append('</svg></section>')
    return '\n'.join(nodes)

def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title><body style="margin:0;background:#F5F3ED;color:#27383F;font-family:system-ui,sans-serif;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">{TITLE}</h1><p style="line-height:1.8;">{INSTRUCTION}</p>{fragment}</main></body></html>'''


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
        if any(path.suffix.lower() not in {".html", ".htm"} for path in targets):
            raise ValueError("输出需要使用.html或.htm文件")
        if len(set(resolved)) != len(resolved):
            raise ValueError("片段和预览需要不同路径")
        protected = config["inputs"] | {Path(__file__).resolve(), (Path(__file__).resolve().parents[1] / "SKILL.md").resolve()}
        if protected.intersection(resolved):
            raise ValueError("输出不能覆盖输入配置、Skill或生成器")
        if any(path.is_dir() for path in targets):
            raise ValueError("输出需要文件名")
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError("输出已存在，请换路径或使用--overwrite")
        prefix = PREFIX + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"files": [str(path.resolve()) for path in targets], "instance": prefix,
                      "canvas": [600, ARTWORK_HEIGHT if "artwork" in config else HEIGHT], "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
