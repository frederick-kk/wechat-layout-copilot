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


PREFIX = "vinyl"
PREVIEW_TITLE = "唱片启停"
PREVIEW_HELP = "点击开始旋转，再停止并复位。这里展示唱片视觉。"


def read_config(path):
    c = load_base(path, {"caption", "center_label", "period"})
    c["caption"] = wrap(c.get("caption"), "caption", 18, 1)
    c["center_label"] = wrap(c.get("center_label"), "center_label", 4, 1)
    c["period"] = seconds(c.get("period", 4), "period", 0.8, 30)
    return c


def render(c, p):
    a = c["accent"]
    start, stop = f"{p}_play", f"{p}_stop"
    parts = [svg_start(c, 600, "wechat-svg-vinyl"), text_nodes(c["caption"], 30, 98, 27, "#586D73")]
    parts.append(f'''<circle cx="300" cy="290" r="165" fill="#E2DDD3"/>
<g transform="translate(300 290)"><g id="{p}_rotor" data-vinyl-rotor="true" transform="rotate(0)">
<circle r="150" fill="#26383E"/>
<circle r="122" fill="none" stroke="#67777A" stroke-width="2"/>
<circle r="108" fill="none" stroke="#67777A" stroke-width="2"/>
<circle r="94" fill="none" stroke="#67777A" stroke-width="2"/>
<path d="M-120 -67 A138 138 0 0 1 -65 -120 M85 100 A130 130 0 0 1 120 50" fill="none" stroke="#D7DBD5" stroke-width="11" opacity="0.6"/>
<circle r="58" fill="{a}"/>
<circle cx="23" cy="-20" r="8" fill="#F0B95A"/>
<circle r="8" fill="{c['background']}"/>
<animateTransform attributeName="transform" type="rotate" from="0 0 0" to="360 0 0" begin="{start}.click" end="{stop}.click" dur="{c['period']:g}s" repeatCount="indefinite" fill="remove"/>
</g></g>''')
    parts.append(text_nodes(c["center_label"], 300, 483, 30, a, "700").replace('x="300"', 'x="300" text-anchor="middle"'))
    for action, label, x, enabled in [("play", "开始旋转", 32, True), ("stop", "停止并复位", 312, False)]:
        trigger = f"{p}_{action}"
        initial = "auto" if enabled else "none"
        opacity = "1" if enabled else "0.45"
        activate, deactivate = (stop, start) if enabled else (start, stop)
        parts.append(f'''<g id="{trigger}" data-action="{action}" opacity="{opacity}" style="cursor:pointer;pointer-events:{initial};opacity:{opacity};">
<set attributeName="pointer-events" to="auto" begin="{activate}.click" fill="freeze"/>
<set attributeName="pointer-events" to="none" begin="{deactivate}.click" fill="freeze"/>
<set attributeName="opacity" to="1" begin="{activate}.click" fill="freeze"/>
<set attributeName="opacity" to="0.45" begin="{deactivate}.click" fill="freeze"/>
<rect x="{x}" y="520" width="256" height="60" rx="13" fill="{a}"/>
<text x="{x+128}" y="560" text-anchor="middle" font-size="29" fill="#FFFFFF" font-family="sans-serif" style="pointer-events:none;">{label}</text>
</g>''')
    return "\n".join(parts) + "</svg></section>\n", 600


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
