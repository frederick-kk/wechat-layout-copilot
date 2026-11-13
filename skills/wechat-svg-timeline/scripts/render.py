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


PREFIX = "timeline"
PREVIEW_TITLE = "动态时间线"
PREVIEW_HELP = "点按后，路径与阶段信息按顺序亮起。完成后可以重播。"


def read_config(path):
    c = load_base(path, {"steps", "duration"})
    steps = c.get("steps")
    if not isinstance(steps, list) or not 3 <= len(steps) <= 4:
        raise ValueError("steps 需要3到4个阶段")
    prepared = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != {"time", "label", "body"}:
            raise ValueError(f"steps[{i}] 需要time、label和body三个字段")
        prepared.append({"time": wrap(step["time"], f"steps[{i}].time", 8, 1),
                         "label": wrap(step["label"], f"steps[{i}].label", 11, 1),
                         "body": wrap(step["body"], f"steps[{i}].body", 15, 1)})
    c["steps"] = prepared
    c["duration"] = seconds(c.get("duration", 2.4), "duration", 0.9, 8)
    return c


def render(c, p):
    a, d, count = c["accent"], c["duration"], len(c["steps"])
    end_y = 145 + (count-1)*120
    length, height = (count-1)*120, count*120 + 220
    start = f"{p}_play.click"
    parts = [svg_start(c, height, "wechat-svg-timeline"),
             '<text x="30" y="98" font-size="27" fill="#586D73" font-family="sans-serif">把一次行动的几个节点串起来</text>',
             f'<path d="M70 145V{end_y}" fill="none" stroke="#D7E2DA" stroke-width="8"/>',
             f'<g id="{p}_line" data-timeline-line="true"><path d="M70 145V{end_y}" fill="none" stroke="{a}" stroke-width="8" stroke-dasharray="{length}" stroke-dashoffset="{length}"><animate attributeName="stroke-dashoffset" from="{length}" to="0" begin="{start}" dur="{d:g}s" fill="freeze"/></path></g>']
    for i, step in enumerate(c["steps"]):
        y, delay = 145 + i*120, d*i/(count-1)
        parts.append(f'''<g id="{p}_step_{i}" data-timeline-step="{i}" opacity="0.3" style="opacity:0.3;">
<rect x="110" y="{y-38}" width="455" height="104" rx="12" fill="#FFFFFF" stroke="#D2DEDA"/>
<circle cx="70" cy="{y}" r="17" fill="{a}" stroke="{c['background']}" stroke-width="5"/>
{text_nodes(step['time'], 128, y-12, 24, a, '700')}
{text_nodes(step['label'], 128, y+19, 32, '#27383F', '700')}
{text_nodes(step['body'], 128, y+51, 30, '#586D73')}
<set attributeName="opacity" to="0.3" begin="{start}" fill="freeze"/>
<animate attributeName="opacity" from="0.3" to="1" begin="{start}+{delay:g}s" dur="0.25s" fill="freeze"/>
</g>''')
    parts.append(replay_button(p, height-88, d+0.25, a, "播放时间线 / 重播"))
    return "\n".join(parts) + "</svg></section>\n", height


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
