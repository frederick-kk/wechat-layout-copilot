"""Render a repeatable click-to-switch SVG card component using Python stdlib."""

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


def color(value):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("颜色请使用六位十六进制值，例如 #158A9A")
    return value.upper()


def duration(value):
    number = float(value)
    if not math.isfinite(number) or not 0.1 <= number <= 3:
        raise argparse.ArgumentTypeError("动画时长须在 0.1 到 3 秒之间")
    return number


def wrap(value, width=14):
    lines = []
    for paragraph in value.split("\n"):
        current = ""
        used = 0
        for character in paragraph:
            advance = 0 if unicodedata.combining(character) else 1
            if character.isascii() and character not in "WM@#%&":
                advance = 0.8
            if current and used + advance > width:
                lines.append(current)
                current = ""
                used = 0
            current += character
            used += advance
        lines.append(current)
    return lines


def load_cards(path):
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list) or not 2 <= len(payload) <= 8:
        raise ValueError("输入须为包含 2 到 8 张卡片的 JSON 数组")
    for index, card in enumerate(payload, 1):
        if not isinstance(card, dict):
            raise ValueError(f"第 {index} 张卡片须为对象")
        for field in ("title", "body"):
            if not isinstance(card.get(field), str) or not card[field].strip():
                raise ValueError(f"第 {index} 张卡片缺少非空字符串 {field}")
            if any(not (character in "\t\n\r" or " " <= character <= "\ud7ff"
                        or "\ue000" <= character <= "\ufffd" or "\U00010000" <= character <= "\U0010ffff")
                   for character in card[field]):
                raise ValueError(f"第 {index} 张卡片的 {field} 含有不能写入 SVG 的控制字符")
        if len(wrap(card["title"])) > 1:
            raise ValueError(f"第 {index} 张标题过长，当前画布容纳一行，最多约 14 个汉字")
        if len(wrap(card["body"])) > 4:
            raise ValueError(f"第 {index} 张正文过长，当前画布容纳四行，最多约 56 个汉字")
    return payload


def render(cards, accent, background, seconds):
    # Keep event IDs unambiguous for SMIL begin references.
    prefix = "switch_" + uuid.uuid4().hex
    panels = []
    for index, card in enumerate(cards):
        previous = (index - 1) % len(cards)
        enter = f"{prefix}_next_{previous}.click"
        leave = f"{prefix}_next_{index}.click"
        body = "\n".join(
            f'<text x="36" y="{155 + line_index * 43}" font-size="34">{html.escape(line)}</text>'
            for line_index, line in enumerate(wrap(card["body"]))
        )
        button_label = "返回第一张" if index == len(cards) - 1 else "点击，查看下一张"
        display = 'inline' if index == 0 else 'none'
        panels.append(f'''<g data-switch-panel="{index}" display="{display}" style="display:{display};">
  <set attributeName="display" to="inline" begin="{enter}" fill="freeze" />
  <set attributeName="display" to="none" begin="{leave}" fill="freeze" />
  <animate attributeName="opacity" from="0" to="1" begin="{enter}" dur="{seconds}s" fill="freeze" />
  <animateTransform attributeName="transform" type="rotate" from="-4 300 210" to="0 300 210" begin="{enter}" dur="{seconds}s" fill="freeze" />
  <rect x="1" y="1" width="598" height="418" rx="20" fill="{background}" stroke="{accent}" stroke-width="2" />
  <path d="M36 46 H104" stroke="{accent}" stroke-width="5" stroke-linecap="round" />
  <text x="564" y="52" text-anchor="end" fill="{accent}" font-size="27">{index + 1} / {len(cards)}</text>
  <text x="36" y="104" font-size="34" font-weight="700">{html.escape(card['title'])}</text>
  {body}
  <g id="{prefix}_next_{index}" data-switch-trigger="next" style="cursor:pointer;">
    <rect x="36" y="338" width="528" height="58" rx="12" fill="{accent}" />
    <text x="300" y="377" text-anchor="middle" font-size="30" fill="#FFFFFF" pointer-events="none">{button_label} →</text>
  </g>
</g>''')
    return f'''<section style="margin:20px 0;padding:0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 420" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;" font-family="sans-serif" fill="#1F2937" data-component="wechat-svg-switch" role="img" aria-label="点击按钮逐张查看内容">
<desc>每次点击底部按钮切换一张卡片，最后一张可返回第一张。</desc>
{chr(10).join(panels)}
</svg>
</section>
'''


def preview(fragment):
    return f'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>点击旋转切换卡片</title><body style="margin:0;background:#F5F3EE;font-family:system-ui,sans-serif;">
<main style="max-width:640px;margin:30px auto;padding:16px;box-sizing:border-box;">
<h1 style="font-size:24px;">点击旋转切换</h1><p style="line-height:1.7;">点击底部按钮，逐张查看。最后一张可返回开头。</p>
{fragment}</main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--color", type=color, default="#158A9A")
    parser.add_argument("--background", type=color, default="#FFFDF7")
    parser.add_argument("--duration", type=duration, default=0.36)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview-out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    if len({path.resolve() for path in targets}) != len(targets):
        parser.error("片段和预览须使用不同输出文件")
    if args.cards.resolve() in {path.resolve() for path in targets}:
        parser.error("输出文件不能覆盖输入 JSON")
    if any(path.is_dir() for path in targets):
        parser.error("输出路径指向目录，请指定文件名")
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("输出已存在，请换路径，或使用 --overwrite 明确替换")
    try:
        cards = load_cards(args.cards)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    fragment = render(cards, args.color, args.background, args.duration)
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
    print(json.dumps({"files": [str(path.resolve()) for path in targets], "cards": len(cards),
                      "canvas": [600, 420], "last_action": "return_to_first"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
