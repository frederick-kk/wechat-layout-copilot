'''Render an original, configurable SVG article component using Python stdlib.'''

import argparse
import html
import json
import math
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path

COMPONENT = "wechat-svg-motion-path"


def text(value, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} 需要非空文字")
    for character in value:
        point = ord(character)
        valid = point in (9, 10, 13) or 32 <= point <= 0xD7FF or 0xE000 <= point <= 0xFFFD or 0x10000 <= point <= 0x10FFFF
        if not valid or 0xFDD0 <= point <= 0xFDEF or (point & 0xFFFF) in (0xFFFE, 0xFFFF):
            raise ValueError(f"{field} 含不能写入 XML 的字符 U+{point:04X}")
    return value


def numeric(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} 需要有限数字")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} 需要有限数字")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} 须在 {minimum:g} 到 {maximum:g} 之间")
    return value


def color(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"{field} 需要六位 HEX 颜色，例如 #167E99")
    return value.upper()


def theme(config):
    return (color(config.get("accent", "#167E99"), "accent"),
            color(config.get("background", "#FFF9EE"), "background"))


def em_width(character):
    if unicodedata.combining(character) or character in ("\u200d", "\ufe0f"):
        return 0
    if unicodedata.east_asian_width(character) in ("F", "W"):
        return 1
    if character in "WM@#%&":
        return 1
    if character in "ilI.,;:!'| `":
        return 0.4
    if character.isascii():
        return 0.65
    return 1


def wrapped(value, field, width, maximum_lines):
    value = text(value, field)
    result = []
    for paragraph in value.split("\n"):
        line = ""
        used = 0
        for character in paragraph:
            advance = em_width(character)
            if line and used + advance > width:
                result.append(line)
                line = ""
                used = 0
            line += character
            used += advance
        result.append(line)
    if len(result) > maximum_lines:
        raise ValueError(f"{field} 排成 {len(result)} 行，当前画布容纳 {maximum_lines} 行，请精简或拆分")
    return result


def labels(lines, x, y, size=32, step=42, fill="#24343B", weight="400"):
    return "\n".join(
        f'<text x="{x:g}" y="{y + index * step:g}" font-size="{size:g}" fill="{fill}" font-weight="{weight}" xml:space="preserve">{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def button(identifier, action, label, x, y, width, accent):
    return f'''<g id="{identifier}" data-action="{action}" style="cursor:pointer;">
<rect x="{x:g}" y="{y:g}" width="{width:g}" height="58" rx="13" fill="{accent}" />
<text x="{x + width / 2:g}" y="{y + 39:g}" text-anchor="middle" font-size="30" fill="#FFFFFF" style="pointer-events:none;">{html.escape(label)}</text>
</g>'''


def frame(content, height, background, description):
    return f'''<section style="margin:20px 0;padding:0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;" font-family="sans-serif" data-component="{COMPONENT}">
<desc>{html.escape(description)}</desc>
<rect x="1" y="1" width="598" height="{height - 2}" rx="20" fill="{background}" />
{content}
</svg></section>'''


def preview(fragment, title):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<body style="margin:0;background:#F3F2EC;font-family:system-ui,sans-serif;color:#24343B;">
<main style="box-sizing:border-box;max-width:632px;margin:24px auto;padding:16px;">
<h1 style="font-size:24px;line-height:1.5;">{html.escape(title)}</h1>
{fragment}</main></body></html>'''


def write_outputs(outputs, overwrite):
    staged = []
    committed = []
    backups = {}
    try:
        for path, content in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            if overwrite and path.exists():
                with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".bak", delete=False) as backup:
                    backup.write(path.read_bytes())
                    backups[path] = Path(backup.name)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stage:
                staged.append((path, Path(stage.name)))
                stage.write(content)
        for path, temporary in staged:
            if overwrite:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
            committed.append(path)
    except OSError as error:
        recovery_errors = []
        for path in reversed(committed):
            try:
                if path in backups:
                    os.replace(backups[path], path)
                    del backups[path]
                else:
                    path.unlink(missing_ok=True)
            except OSError as recovery:
                saved = backups.pop(path, None)
                recovery_errors.append(f"{path} 恢复失败，备份 {saved}，{recovery}")
        detail = "\n".join(recovery_errors)
        raise OSError(f"输出写入失败，{error}\n{detail}") from error
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    resolved = [path.resolve() for path in targets]
    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict):
            raise ValueError("配置顶层需要 JSON 对象")
        if len(set(resolved)) != len(resolved):
            raise ValueError("片段与预览需要不同输出文件")
        if any(path.is_dir() for path in targets):
            raise ValueError("输出指向目录，请指定文件名")
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError("输出已存在，请换路径或使用 --overwrite")
        fragment, metadata, input_files = build(config, args.config)
        if {args.config.resolve(), *input_files}.intersection(resolved):
            raise ValueError("输出不能覆盖配置文件或原始图片")
        outputs = [(args.out, fragment)]
        if args.preview_out:
            outputs.append((args.preview_out, preview(fragment, metadata["title"])))
        write_outputs(outputs, args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "created", "component": COMPONENT,
                      "files": [str(path) for path in resolved], **metadata}, ensure_ascii=False))


def build(config, config_path):
    accent, background = theme(config)
    title = wrapped(config.get("title"), "title", 15, 1)
    caption = wrapped(config.get("caption", "点击按钮，让小点沿路线出发"), "caption", 20, 1)
    seconds = numeric(config.get("duration", 2), "duration", 0.3, 10)
    points = config.get("points", [[50, 260], [180, 126], [420, 300], [550, 170]])
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError("points 需要四个 [x,y] 点，表示起点、两个控制点和终点")
    prepared = []
    for index, point in enumerate(points):
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"points[{index}] 需要 [x,y]")
        prepared.append([numeric(point[0], f"points[{index}].x", 28, 572),
                         numeric(point[1], f"points[{index}].y", 126, 308)])
    path = f'M {prepared[0][0]:g} {prepared[0][1]:g} C ' + ' '.join(f'{x:g} {y:g}' for x, y in prepared[1:])
    origin_x, origin_y = prepared[0]
    motion_path = 'M 0 0 C ' + ' '.join(f'{x - origin_x:g} {y - origin_y:g}' for x, y in prepared[1:])
    prefix = "motion_" + uuid.uuid4().hex
    start = f"{prefix}_play.click"
    content = labels(title, 36, 59, 34, weight="700") + labels(caption, 36, 103, 25)
    content += f'''<path d="{path}" fill="none" stroke="{accent}" stroke-width="5" stroke-dasharray="7 9" opacity="0.45" />
<g id="{prefix}_marker" data-motion-marker="true" transform="translate({prepared[0][0]:g} {prepared[0][1]:g})">
<g data-motion-traveler="true">
<circle r="20" fill="{accent}" />
<path d="M-7 -7 L9 0 L-7 7 Z" fill="#FFFFFF" />
<animateMotion path="{motion_path}" begin="{start}" dur="{seconds:g}s" rotate="auto" fill="freeze" restart="always" />
</g></g>'''
    content += button(prefix + "_play", "play", "点击出发 / 重新播放", 36, 347, 528, accent)
    return frame(content, 430, background, "图形沿指定的三次贝塞尔路线运动。可点击按钮重播。"), {
        "title": config["title"], "canvas": [600, 430], "path": path, "duration": seconds,
    }, set()


if __name__ == "__main__":
    main()
