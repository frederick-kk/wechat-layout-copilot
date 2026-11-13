"""Render a repeatable multi-hotspot SVG component using Python stdlib."""

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


def color(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{field} 请使用六位十六进制颜色")
    return value.upper()


def width_em(character):
    if unicodedata.combining(character) or character == "\u200d":
        return 0
    if unicodedata.east_asian_width(character) in {"F", "W"}:
        return 1
    if character in "ilI.,;:!'| `":
        return 0.4
    if character in "WM@#%&":
        return 1
    return 0.8 if character.isascii() else 1


def check_xml_text(value, field):
    for character in value:
        codepoint = ord(character)
        valid = codepoint in {9, 10, 13} or 32 <= codepoint <= 0xD7FF or 0xE000 <= codepoint <= 0x10FFFF
        noncharacter = 0xFDD0 <= codepoint <= 0xFDEF or codepoint & 0xFFFF in {0xFFFE, 0xFFFF}
        if not valid or noncharacter:
            raise ValueError(f"{field} 含无法写入 XML 的字符 U+{codepoint:04X}")


def lines(value, field, limit, max_lines):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 需要非空文字")
    check_xml_text(value, field)
    result = []
    for paragraph in value.split("\n"):
        current = ""
        advance = 0
        for character in paragraph:
            size = width_em(character)
            if current and advance + size > limit:
                result.append(current)
                current = ""
                advance = 0
            current += character
            advance += size
        result.append(current)
    if len(result) > max_lines:
        raise ValueError(f"{field} 排成 {len(result)} 行，当前画面可容纳 {max_lines} 行，请精简或拆分")
    return result


def image_source(value, base_directory, protected_inputs):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("base_image 需要本地光栅图路径或 HTTPS 地址")
    check_xml_text(value, "base_image")
    parsed = urlsplit(value)
    if parsed.scheme == "https":
        if not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
            raise ValueError("base_image 的 HTTPS 地址格式有误")
        return value
    if parsed.scheme and not re.match(r"^[A-Za-z]:[/\\]", value):
        raise ValueError("base_image 仅支持 HTTPS 或本地 PNG、JPEG、WebP")
    path = Path(value)
    if not path.is_absolute():
        path = base_directory / path
    protected_inputs.add(path.resolve())
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("base_image 文件需要有效 PNG、JPEG 或 WebP 文件头")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def read_config(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置顶层需要 JSON 对象")
    unknown = set(config) - {"title", "hint", "accent", "background", "base_image", "spots"}
    if unknown:
        raise ValueError("未知配置字段 " + ", ".join(sorted(unknown)))
    title = lines(config.get("title"), "title", 14, 2)
    hint = lines(config.get("hint", "点击卡片查看，再点返回"), "hint", 21, 1)
    accent = color(config.get("accent", "#197B8B"), "accent")
    background = color(config.get("background", "#FFF9EE"), "background")
    spots = config.get("spots")
    if not isinstance(spots, list) or not 2 <= len(spots) <= 4:
        raise ValueError("spots 需要 2～4 个热区")
    prepared = []
    for index, spot in enumerate(spots):
        field = f"spots[{index}]"
        if not isinstance(spot, dict):
            raise ValueError(f"{field} 需要 JSON 对象")
        unknown = set(spot) - {"label", "title", "body", "rect"}
        if unknown:
            raise ValueError(f"{field} 含未知字段 " + ", ".join(sorted(unknown)))
        rect = spot.get("rect", [40, 150 + index * 100, 520, 76])
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError(f"{field}.rect 需要 [x,y,width,height]")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in rect):
            raise ValueError(f"{field}.rect 需要有限数字")
        x, y, width, height = rect
        if x < 0 or y < 0 or width < 100 or height < 60 or x + width > 600 or y + height > 600:
            raise ValueError(f"{field}.rect 须在600×600内，宽至少100、高至少60")
        label = lines(spot.get("label"), f"{field}.label", (width - 72) / 32, 1)
        prepared.append({
            "rect": rect,
            "label": label,
            "title": lines(spot.get("title"), f"{field}.title", 14, 2),
            "body": lines(spot.get("body"), f"{field}.body", 14, 6),
        })
    protected_inputs = {path.resolve()}
    source = image_source(config["base_image"], path.parent, protected_inputs) if "base_image" in config else None
    return {"title": title, "hint": hint, "accent": accent, "background": background, "spots": prepared, "base_image": source, "protected_inputs": protected_inputs}


def text_nodes(text_lines, x, y, size, line_height, fill, weight="400"):
    return "\n".join(
        f'<text x="{x:g}" y="{y + index * line_height:g}" fill="{fill}" font-size="{size:g}" font-weight="{weight}" font-family="sans-serif" xml:space="preserve">{html.escape(line)}</text>'
        for index, line in enumerate(text_lines)
    )


def render(config, prefix):
    prefix = prefix.replace("-", "_")
    accent = config["accent"]
    background = config["background"]
    nodes = [
        '<section style="margin:20px 0;padding:0;line-height:0;">',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 600 600" width="100%" style="display:block;width:100%;height:auto;" data-component="wechat-svg-hotspots" data-instance="{prefix}" role="group" aria-label="多热区点击查看说明">',
        '<desc>点击编号热区打开对应说明，点击返回回到总图。</desc>',
        f'<rect width="600" height="600" rx="20" fill="{background}"/>',
    ]
    if config["base_image"]:
        source = html.escape(config["base_image"], quote=True)
        nodes.append(f'<image x="0" y="0" width="600" height="600" preserveAspectRatio="xMidYMid meet" href="{source}" xlink:href="{source}"/>')
    else:
        nodes.append(text_nodes(config["title"], 40, 60, 36, 44, "#1F2937", "700"))
        nodes.append(text_nodes(config["hint"], 40, 132, 24, 30, "#52616A"))
        nodes.append(f'<path d="M42 565 Q175 530 305 563 T555 561" fill="none" stroke="{accent}" stroke-width="3" stroke-dasharray="5 10" opacity="0.35"/>')
    for index, spot in enumerate(config["spots"]):
        x, y, width, height = spot["rect"]
        trigger = f"{prefix}_open_{index}"
        label = html.escape(spot["label"][0], quote=True)
        nodes.extend([
            f'<g id="{trigger}" data-hotspot="{index}" style="cursor:pointer;" role="button" aria-label="{label}">',
            f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="14" fill="{background}" fill-opacity="0.94" stroke="{accent}" stroke-width="2" pointer-events="all"/>',
            f'<circle cx="{x + 31:g}" cy="{y + height / 2:g}" r="20" fill="{accent}" pointer-events="none"/>',
            text_nodes([str(index + 1)], x + 21, y + height / 2 + 11, 30, 34, "#FFFFFF", "700"),
            text_nodes(spot["label"], x + 66, y + height / 2 + 12, 32, 40, "#1F2937", "700"),
            '</g>',
        ])
    for index, spot in enumerate(config["spots"]):
        trigger = f"{prefix}_open_{index}"
        close = f"{prefix}_back_{index}"
        nodes.extend([
            f'<g visibility="hidden" style="visibility:hidden;" data-hotspot-detail="{index}">',
            f'<set attributeName="visibility" to="visible" begin="{trigger}.click" end="{close}.click" restart="always"/>',
            f'<g opacity="0" data-hotspot-fade="{index}">',
            f'<animate attributeName="opacity" from="0" to="1" dur="0.28s" begin="{trigger}.click" fill="freeze" restart="always"/>',
            f'<rect width="600" height="600" rx="20" fill="{background}" pointer-events="visiblePainted"/>',
            f'<path d="M40 150 H560" stroke="{accent}" stroke-width="3"/>',
            text_nodes(spot["title"], 40, 70, 36, 44, "#1F2937", "700"),
            text_nodes(spot["body"], 40, 206, 36, 44, "#1F2937"),
            f'<g id="{close}" data-hotspot-back="{index}" role="button" aria-label="返回总图" style="cursor:pointer;">',
            f'<rect x="40" y="500" width="520" height="60" rx="14" fill="{accent}" pointer-events="visiblePainted"/>',
            text_nodes(["返回总图"], 236, 542, 32, 40, "#FFFFFF", "700"),
            '</g>',
            '</g>',
            '</g>',
        ])
    nodes.extend(['</svg>', '</section>'])
    return "\n".join(nodes) + "\n"


def preview(fragment):
    return f'''<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>多热区点击与返回</title>
<body style="margin:0;background:#F3F3EF;color:#1F2937;font-family:system-ui,sans-serif;">
<main style="max-width:600px;margin:24px auto;padding:16px;">
<h1 style="font-size:24px;line-height:1.5;">多热区点击与返回</h1>
<p style="font-size:16px;line-height:1.8;">点开各个节点，再返回总图。组件高度保持一致。</p>
{fragment}
</main>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--id-prefix", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    prefix = args.id_prefix or f"hotspots_{uuid.uuid4().hex[:16]}"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", prefix):
        parser.error("id-prefix 须以英文字母开头，仅含字母、数字、下划线或连字符，最多64位")
    prefix = prefix.replace("-", "_")
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    resolved = [path.resolve() for path in targets]
    if len(set(resolved)) != len(resolved):
        parser.error("片段与预览需要不同输出路径")
    if args.config.resolve() in resolved:
        parser.error("输出路径不能覆盖输入配置")
    if any(path.is_dir() for path in targets):
        parser.error("输出路径指向目录，请指定文件名")
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("输出文件已存在，请换路径或使用 --overwrite")
    try:
        config = read_config(args.config)
        if config["protected_inputs"].intersection(resolved):
            parser.error("输出路径不能覆盖输入配置或本地源图片")
        fragment = render(config, prefix)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    payloads = [fragment] + ([preview(fragment)] if args.preview_out else [])
    staged = []
    committed = []
    previous = {}
    try:
        for path, content in zip(targets, payloads):
            path.parent.mkdir(parents=True, exist_ok=True)
            previous[path] = path.read_bytes() if args.overwrite and path.exists() else None
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as output:
                staged.append((path, Path(output.name)))
                output.write(content)
        for path, temporary in staged:
            if args.overwrite:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
            committed.append(path)
    except OSError as error:
        for path in reversed(committed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous[path])
        parser.error(str(error))
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)
    print(json.dumps({
        "files": [str(path) for path in resolved],
        "instance": prefix,
        "hotspots": len(config["spots"]),
        "canvas": [600, 600],
        "body_font_size": 36,
        "validation": "generated; browser, editor and phone checks pending",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
