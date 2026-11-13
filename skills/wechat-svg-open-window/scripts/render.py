"""Generate an original inline SVG interaction using Python standard library."""

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


def text_lines(value, field, max_lines=4, width=14):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 需要非空文字")
    for character in value:
        codepoint = ord(character)
        valid = codepoint in {9, 10, 13} or 32 <= codepoint <= 0xD7FF or 0xE000 <= codepoint <= 0x10FFFF
        if not valid or 0xFDD0 <= codepoint <= 0xFDEF or codepoint & 0xFFFF in {0xFFFE, 0xFFFF}:
            raise ValueError(f"{field} 含无法写入XML的字符 U+{codepoint:04X}")
    result = []
    for paragraph in value.split("\n"):
        line = ""
        used = 0
        for character in paragraph:
            if unicodedata.combining(character) or character == "\u200d":
                advance = 0
            elif unicodedata.east_asian_width(character) in {"F", "W"}:
                advance = 1
            elif character in "ilI.,;:!'| `":
                advance = 0.4
            else:
                advance = 0.8 if character.isascii() else 1
            if line and used + advance > width:
                result.append(line)
                line = ""
                used = 0
            line += character
            used += advance
        result.append(line)
    if len(result) > max_lines:
        raise ValueError(f"{field} 排成{len(result)}行，当前画布可容纳{max_lines}行，请精简或拆分")
    return result


def color(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{field} 请使用六位HEX颜色")
    return value.upper()


def seconds(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{field} 须为{minimum}到{maximum}之间的有限数字")
    return value


def text_nodes(lines, x, y, size=34, line_height=42, fill="#24343B", bold=False, anchor="start"):
    weight = ' style="font-weight:700;"' if bold else ''
    return "\n".join(
        f'<text x="{x}" y="{y + index * line_height}" font-size="{size}" fill="{fill}" font-family="sans-serif" text-anchor="{anchor}" xml:space="preserve"{weight}>{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def svg_open(prefix, label):
    return f"""<section style="margin:20px 0;padding:0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 460" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none;" data-component="{COMPONENT}" data-instance="{prefix}" role="img" aria-label="{html.escape(label, quote=True)}">"""


def preview(fragment):
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title><body style="margin:0;background:#F5F3ED;color:#24343B;font-family:system-ui,sans-serif;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;line-height:1.5;">{TITLE}</h1>
<p style="font-size:16px;line-height:1.8;">{INSTRUCTION}</p>{fragment}
<p style="font-size:14px;line-height:1.7;">本页用于浏览器检查，编辑器保存与手机微信表现按实际结果核对。</p></main></body></html>"""


def write_outputs(targets, contents, overwrite):
    staged = []
    committed = []
    previous = {}
    try:
        for path, content in zip(targets, contents):
            path.parent.mkdir(parents=True, exist_ok=True)
            previous[path] = path.read_bytes() if overwrite and path.exists() else None
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
                staged.append((path, Path(stream.name)))
                stream.write(content)
        for path, temporary in staged:
            if overwrite:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
            committed.append(path)
    except OSError:
        for path in reversed(committed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous[path])
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    resolved = [path.resolve() for path in targets]
    if len(set(resolved)) != len(resolved):
        parser.error("片段与预览需要不同输出路径")
    if args.config.resolve() in resolved:
        parser.error("输出不能覆盖输入配置")
    if any(path.is_dir() for path in targets):
        parser.error("输出路径指向目录，请指定文件名")
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("输出已存在，请换路径或使用 --overwrite")
    try:
        config = load_config(args.config)
        prefix = COMPONENT.replace("-", "_") + "_" + uuid.uuid4().hex
        fragment = render(config, prefix)
        contents = [fragment] + ([preview(fragment)] if args.preview_out else [])
        write_outputs(targets, contents, args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "created", "component": COMPONENT,
                      "files": [str(path) for path in resolved], "canvas": [600, 460],
                      "instance": prefix}, ensure_ascii=False))

COMPONENT = "wechat-svg-open-window"
TITLE = "双扇开窗"
INSTRUCTION = "点开窗户查看里面的内容，再点合上窗户，可反复体验。"


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置顶层需要JSON对象")
    unknown = set(config) - {"title", "body", "cover_title", "accent", "background", "duration"}
    if unknown:
        raise ValueError("未知字段 " + ", ".join(sorted(unknown)))
    return {"title": text_lines(config.get("title"), "title", 1),
            "body": text_lines(config.get("body"), "body", 4),
            "cover_title": text_lines(config.get("cover_title", "点开这扇窗"), "cover_title", 1),
            "accent": color(config.get("accent", "#167E99"), "accent"),
            "background": color(config.get("background", "#FFF9EE"), "background"),
            "duration": seconds(config.get("duration", 0.6), "duration", 0.1, 3)}


def render(config, prefix):
    accent, background = config["accent"], config["background"]
    opened, closed = f"{prefix}_open.click", f"{prefix}_close.click"
    duration = config["duration"]
    nodes = [svg_open(prefix, TITLE), f'<rect x="1" y="1" width="598" height="458" rx="18" fill="{background}" stroke="{accent}" stroke-width="2"/>',
             text_nodes(config["title"], 40, 70, bold=True),
             text_nodes(config["body"], 40, 130),
             '<g data-window-panel="left" style="pointer-events:none;">',
             f'<animateTransform attributeName="transform" type="translate" from="0 0" to="-300 0" begin="{opened}" dur="{duration}s" fill="freeze"/>',
             f'<animateTransform attributeName="transform" type="translate" from="-300 0" to="0 0" begin="{closed}" dur="{duration}s" fill="freeze"/>',
             f'<rect x="0" y="0" width="300" height="350" fill="{accent}"/>',
             '<path d="M24 24 H276 V326 H24 Z M150 24 V326 M24 175 H276" fill="none" stroke="#FFFFFF" stroke-width="3" opacity="0.45"/>',
             '<circle cx="273" cy="205" r="8" fill="#F8CA74"/>',
             '</g>',
             '<g data-window-panel="right" style="pointer-events:none;">',
             f'<animateTransform attributeName="transform" type="translate" from="0 0" to="300 0" begin="{opened}" dur="{duration}s" fill="freeze"/>',
             f'<animateTransform attributeName="transform" type="translate" from="300 0" to="0 0" begin="{closed}" dur="{duration}s" fill="freeze"/>',
             f'<rect x="300" y="0" width="300" height="350" fill="{accent}"/>',
             '<path d="M324 24 H576 V326 H324 Z M450 24 V326 M324 175 H576" fill="none" stroke="#FFFFFF" stroke-width="3" opacity="0.45"/>',
             '<circle cx="327" cy="205" r="8" fill="#F8CA74"/>',
             '</g>',
             '<g data-window-cover-label="true" opacity="1" style="pointer-events:none;">',
             f'<set attributeName="opacity" to="0" begin="{opened}" fill="freeze"/>',
             f'<set attributeName="opacity" to="1" begin="{closed}+{duration}s" fill="freeze"/>',
             text_nodes(config["cover_title"], 300, 145, fill="#FFFFFF", bold=True, anchor="middle"),
             '</g>']
    for action, label, initial, show, hide in [
        ("open", "点开窗户", "inline", closed, opened),
        ("close", "合上窗户，再看一次", "none", opened, closed),
    ]:
        nodes.extend([f'<g id="{prefix}_{action}" data-window-action="{action}" style="display:{initial};cursor:pointer;">',
                      f'<set attributeName="display" to="inline" begin="{show}" fill="freeze"/>',
                      f'<set attributeName="display" to="none" begin="{hide}" fill="freeze"/>',
                      f'<rect x="36" y="378" width="528" height="58" rx="13" fill="{accent}"/>',
                      text_nodes([label], 300, 417, size=30, fill="#FFFFFF", anchor="middle"), '</g>'])
    nodes.extend(['</svg>', '</section>'])
    return "\n".join(nodes) + "\n"


if __name__ == "__main__":
    main()
