'''Render an original, configurable SVG article component using Python stdlib.'''

import argparse
import base64
import html
import json
import math
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlsplit

COMPONENT = "wechat-svg-zoom-detail"


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


def source_image(value, config_path):
    value = text(value, "image")
    parsed = urlsplit(value)
    if parsed.scheme.lower() == "https":
        if not parsed.hostname or parsed.username or parsed.password or any(character.isspace() for character in value):
            raise ValueError("image 需要完整 HTTPS 图片地址")
        return value, None
    if parsed.scheme and not re.match(r"^[A-Za-z]:[/\\]", value):
        raise ValueError("image 需要本地光栅图片或 HTTPS 地址")
    path = Path(value)
    if not path.is_absolute():
        path = config_path.parent / path
    path = path.resolve()
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("image 须为 PNG、JPEG、GIF 或 WebP")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}", path


def original_scene(accent):
    return f'''<rect width="600" height="360" rx="16" fill="#E7F0F0" />
<rect x="24" y="25" width="552" height="310" rx="15" fill="#FFFFFF" />
<rect x="48" y="52" width="180" height="18" rx="8" fill="{accent}" opacity="0.25" />
<text x="48" y="119" font-size="34" fill="#24343B" font-weight="700">我的项目方案</text>
<path d="M48 151 H255 M48 185 H225 M48 218 H235" stroke="#A4B7BB" stroke-width="15" stroke-linecap="round" />
<rect x="310" y="73" width="235" height="222" rx="15" fill="#FFF3D7" />
<text x="332" y="113" font-size="26" fill="#705E35">看这里的细节</text>
<path d="M337 245 V200 H376 V245 M393 245 V167 H432 V245 M449 245 V140 H488 V245" fill="{accent}" />
<path d="M331 257 H519" stroke="#705E35" stroke-width="3" />
<circle cx="524" cy="91" r="8" fill="#E2B44D" />'''


def build(config, config_path):
    accent, background = theme(config)
    title = wrapped(config.get("title"), "title", 15, 1)
    focus = config.get("focus", [290, 70, 260, 156])
    if not isinstance(focus, list) or len(focus) != 4:
        raise ValueError("focus 需要 [x,y,width,height]，坐标基于600×360原画布")
    x = numeric(focus[0], "focus.x", 0, 600)
    y = numeric(focus[1], "focus.y", 0, 360)
    width = numeric(focus[2], "focus.width", 60, 599)
    height = numeric(focus[3], "focus.height", 36, 359)
    if x + width > 600 or y + height > 360:
        raise ValueError("focus 不能超出600×360原画布")
    seconds = numeric(config.get("duration", 0.5), "duration", 0.1, 3)
    resources = set()
    if "image" in config:
        source, path = source_image(config["image"], config_path)
        scene = f'<image href="{html.escape(source, quote=True)}" width="600" height="360" preserveAspectRatio="xMidYMid meet" />'
        if path is not None:
            resources.add(path)
    else:
        scene = original_scene(accent)
    prefix = "zoom_" + uuid.uuid4().hex
    target = f"{x:g} {y:g} {width:g} {height:g}"
    content = labels(title, 36, 59, 34, weight="700")
    content += f'''<svg x="24" y="90" width="552" height="331.2" viewBox="0 0 600 360" style="overflow:hidden;" data-zoom-viewport="true">
<animate attributeName="viewBox" from="0 0 600 360" to="{target}" begin="{prefix}_zoom.click" dur="{seconds:g}s" fill="freeze" restart="always" />
<animate attributeName="viewBox" from="{target}" to="0 0 600 360" begin="{prefix}_reset.click" dur="{seconds:g}s" fill="freeze" restart="always" />
{scene}</svg>'''
    content += button(prefix + "_zoom", "zoom", "放大细节", 36, 446, 252, accent)
    content += button(prefix + "_reset", "reset", "返回全景", 312, 446, 252, accent)
    return frame(content, 530, background, "点击放大同一幅画面的指定区域，再返回完整画面。"), {
        "title": config["title"], "canvas": [600, 530], "focus": focus,
        "image_mode": "user_image" if "image" in config else "original_vector_demo",
    }, resources


if __name__ == "__main__":
    main()
