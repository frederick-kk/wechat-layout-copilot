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

COMPONENT = "wechat-svg-typewriter"


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


def clusters(value):
    result = []
    regional_count = 0
    for character in value:
        point = ord(character)
        regional = 0x1F1E6 <= point <= 0x1F1FF
        modifier = 0x1F3FB <= point <= 0x1F3FF
        attach = (result and (unicodedata.combining(character) or character in ("\ufe0f", "\u200d")
                  or result[-1].endswith("\u200d") or modifier or regional and regional_count % 2))
        if attach:
            result[-1] += character
        else:
            result.append(character)
        regional_count = regional_count + 1 if regional else 0
    return result


def build(config, config_path):
    accent, background = theme(config)
    title = wrapped(config.get("title"), "title", 15, 1)
    value = text(config.get("text"), "text")
    interval = numeric(config.get("interval", 0.09), "interval", 0.02, 0.4)
    paragraphs = [clusters(paragraph) for paragraph in value.split("\n")]
    rows = []
    for paragraph in paragraphs:
        row = []
        used = 0
        for cluster in paragraph:
            advance = max((em_width(character) for character in cluster), default=0)
            if row and used + advance > 14:
                rows.append(row)
                row = []
                used = 0
            row.append((cluster, advance))
            used += advance
        rows.append(row)
    if len(rows) > 6:
        raise ValueError(f"text 排成{len(rows)}行，当前画布容纳6行，请精简或拆分")
    prefix = "typewriter_" + uuid.uuid4().hex
    start = f"{prefix}_play.click"
    content = labels(title, 36, 60, 34, weight="700")
    content += f'<path d="M36 92 H564" stroke="{accent}" stroke-width="3" />'
    count = 0
    for row_index, row in enumerate(rows):
        x = 40.0
        for cluster, advance in row:
            delay = count * interval
            content += f'''<g id="{prefix}_char_{count}" data-char-index="{count}" opacity="0" style="opacity:0;">
<set attributeName="opacity" to="0" begin="{start}" fill="freeze" />
<animate attributeName="opacity" from="0" to="1" begin="{start}+{delay:g}s" dur="0.01s" fill="freeze" restart="always" />
<text x="{x:g}" y="{153 + row_index * 44}" font-size="34" fill="#24343B" xml:space="preserve">{html.escape(cluster)}</text>
</g>'''
            x += advance * 34
            count += 1
    content += button(prefix + "_play", "play", "点击打字 / 重新播放", 36, 430, 528, accent)
    return frame(content, 515, background, value), {
        "title": config["title"], "canvas": [600, 515], "characters": count,
        "duration": max(0, count - 1) * interval + 0.01,
    }, set()


if __name__ == "__main__":
    main()
