"""Generate a self-contained original SVG component with SMIL interactions."""
import argparse
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


PREFIX = "confetti"
PREVIEW_TITLE = "点按礼花"
PREVIEW_HELP = "点击绽放礼花与祝福，完成后可以再次播放。"


def read_config(path):
    c = load_base(path, {"message", "duration", "particles"})
    c["message"] = wrap(c.get("message"), "message", 14, 2)
    c["duration"] = seconds(c.get("duration", 1.6), "duration", 0.6, 4)
    number = c.get("particles", 16)
    if isinstance(number, bool) or not isinstance(number, int) or not 8 <= number <= 24:
        raise ValueError("particles 需要8到24之间的整数")
    c["particles"] = number
    return c


def render(c, p):
    a, d, count = c["accent"], c["duration"], c["particles"]
    start = f"{p}_play.click"
    parts = [svg_start(c, 570, "wechat-svg-confetti"), '<circle cx="300" cy="220" r="120" fill="#E8EFE5"/>',
             f'<path d="M260 304 L275 248 L317 282 Z" fill="{a}"/><path d="M272 273L302 294" stroke="#FFFFFF" stroke-width="7"/>']
    palette = [a, "#E6B55B", "#D78269", "#75B6A7"]
    for i in range(count):
        angle = 2*math.pi*i/count
        dx, dy = 175*math.cos(angle), 155*math.sin(angle)-25
        parts.append(f'''<g transform="translate(300 220)"><g id="{p}_particle_{i}" data-particle-index="{i}" transform="translate(0 0)" opacity="0" style="opacity:0;">
<animateTransform attributeName="transform" type="translate" from="0 0" to="{dx:.3f} {dy:.3f}" begin="{start}" dur="{d:g}s" fill="freeze"/>
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.06;0.6;1" begin="{start}" dur="{d:g}s" fill="freeze"/>
<g><rect x="-5" y="-10" width="10" height="20" rx="2" fill="{palette[i%4]}"/><animateTransform attributeName="transform" type="rotate" from="0" to="{180+i*21}" begin="{start}" dur="{d:g}s" fill="freeze"/></g>
</g></g>''')
    parts.append(f'''<g id="{p}_message" data-confetti-message="true" opacity="0" style="opacity:0;">
{text_nodes(c['message'], 300, 398, 32, '#27383F', '700').replace('x="300"', 'x="300" text-anchor="middle"')}
<set attributeName="opacity" to="0" begin="{start}" fill="freeze"/>
<animate attributeName="opacity" from="0" to="1" begin="{start}+{d*0.5:g}s" dur="{d*0.3:g}s" fill="freeze"/>
</g>''')
    parts.append(replay_button(p, 492, d, a, "点燃礼花 / 再来一次"))
    return "\n".join(parts) + "</svg></section>\n", 570


def seconds(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{field} 需要{minimum}到{maximum}之间的有限秒数")
    return float(value)


def load_base(path, allowed):
    item = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(item, dict):
        raise ValueError("配置需要JSON对象")
    unknown = set(item) - set(allowed) - {"title", "accent", "background"}
    if unknown:
        raise ValueError("未知配置字段 " + ", ".join(sorted(unknown)))
    item["title"] = wrap(item.get("title"), "title", 15, 1)
    item["accent"] = color(item.get("accent", "#167E99"), "accent")
    item["background"] = color(item.get("background", "#FFF9EF"), "background")
    item["inputs"] = {path.resolve(), Path(__file__).resolve(), Path(__file__).resolve().parents[1] / "SKILL.md"}
    return item


def svg_start(config, height, component):
    title = text_nodes(config["title"], 30, 52, 34, "#27383F", "700")
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="100%" style="display:block;width:100%;height:auto;" data-component="{component}">
<rect x="1" y="1" width="598" height="{height-2}" rx="20" fill="{config['background']}"/>
{title}'''


def replay_button(prefix, y, total, accent, label="点击播放 / 重播"):
    return f'''<g id="{prefix}_play" data-action="play" style="cursor:pointer;pointer-events:auto;">
<set attributeName="pointer-events" to="none" begin="{prefix}_play.click" fill="freeze"/>
<set attributeName="pointer-events" to="auto" begin="{prefix}_play.click+{total:g}s" fill="freeze"/>
<rect x="32" y="{y}" width="536" height="60" rx="13" fill="{accent}"/>
<text x="300" y="{y+40}" text-anchor="middle" font-size="30" fill="#FFFFFF" font-family="sans-serif" style="pointer-events:none;">{html.escape(label)}</text>
</g>'''


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{PREVIEW_TITLE}</title><body style="margin:0;background:#F5F3ED;font-family:system-ui,sans-serif;color:#27383F;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">{PREVIEW_TITLE}</h1><p style="line-height:1.8;">{PREVIEW_HELP}</p>{fragment}</main></body></html>'''


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
        if config["inputs"].intersection(resolved):
            raise ValueError("输出不能覆盖配置或脚本源文件")
        if any(path.is_dir() for path in targets):
            raise ValueError("输出路径指向目录，请指定文件名")
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError("输出已存在，请换路径或使用 --overwrite")
        prefix = PREFIX + "_" + uuid.uuid4().hex
        fragment, height = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"files": [str(p.resolve()) for p in targets], "canvas": [600, height], "instance": prefix,
                      "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
