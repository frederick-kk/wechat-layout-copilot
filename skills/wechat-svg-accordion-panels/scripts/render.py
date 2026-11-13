"""Render accordion-panels as an original SVG/SMIL component."""

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

def common_config(path, allowed):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置需要JSON对象")
    extra = set(config) - allowed - {"title", "accent", "background", "duration"}
    if extra:
        raise ValueError("未知配置字段 " + ", ".join(sorted(extra)))
    prepared = {
        "title": wrap(config.get("title"), "title", 14, 1),
        "accent": color(config.get("accent", "#167E99"), "accent"),
        "background": color(config.get("background", "#FFF9EF"), "background"),
        "inputs": {path.resolve()},
    }
    duration = config.get("duration", 0.7)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0.2 <= duration <= 3:
        raise ValueError("duration需要0.2到3之间的秒数")
    prepared["duration"] = duration
    return config, prepared


def svg_start(config, component, height):
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;" data-component="{component}" role="group">
<rect width="600" height="{height}" rx="20" fill="{config['background']}"/>
{text_nodes(config['title'], 28, 53, 36, '#27383F', '700')}
'''








TITLE = '横向手风琴卡片'
INSTRUCTION = '点击任意收窄的卡片，它会展开，另外两张收窄。'
PREFIX = 'accordion_'
HEIGHT = 540


def read_config(path):
    config, prepared = common_config(path, {"panels"})
    panels = config.get("panels")
    if not isinstance(panels, list) or len(panels) != 3:
        raise ValueError("panels需要三张卡片")
    prepared["panels"] = []
    for index, item in enumerate(panels):
        if not isinstance(item, dict) or set(item) != {"label", "body"}:
            raise ValueError(f"panels[{index}]需要label与body")
        prepared["panels"].append({"label": wrap(item["label"], f"panels[{index}].label", 2, 1),
                                   "body": wrap(item["body"], f"panels[{index}].body", 8, 4)})
    return prepared


def geometry(selected):
    widths = [330 if index == selected else 105 for index in range(3)]
    positions = [20, 30+widths[0], 40+widths[0]+widths[1]]
    return positions, widths


def render(config, prefix):
    accent, duration = config["accent"], config["duration"]
    transitions = [(origin, target) for origin in range(3) for target in range(3) if origin != target]
    event = lambda origin, target: f'{prefix}_pick_{origin}_{target}.click'
    every = ';'.join(event(origin, target) for origin, target in transitions)
    nodes = [svg_start(config, 'wechat-svg-accordion-panels', HEIGHT)]
    for index, item in enumerate(config['panels']):
        x, width = geometry(0)[0][index], geometry(0)[1][index]
        nodes.append(f'<g id="{prefix}_panel_{index}" data-accordion-panel="{index}" transform="translate({x} 0)">')
        for origin, target in transitions:
            old, new = geometry(origin)[0][index], geometry(target)[0][index]
            nodes.append(f'<animateTransform attributeName="transform" type="translate" from="{old} 0" to="{new} 0" begin="{event(origin,target)}" dur="{duration}s" fill="freeze"/>')
        nodes.append(f'<rect data-panel-background="{index}" x="0" y="110" width="{width}" height="350" rx="16" fill="{accent if index==0 else ["#167E99","#458D97","#68777E"][index]}">')
        for origin, target in transitions:
            old, new = geometry(origin)[1][index], geometry(target)[1][index]
            nodes.append(f'<animate attributeName="width" from="{old}" to="{new}" begin="{event(origin,target)}" dur="{duration}s" fill="freeze"/>')
        nodes.append('</rect>')
        nodes.append(text_nodes(item['label'], 20, 168, 32, '#FFFFFF', '700'))
        initial = 'visible' if index==0 else 'hidden'
        nodes.append(f'<g id="{prefix}_body_{index}" data-panel-body="{index}" visibility="{initial}" style="visibility:{initial};"><set attributeName="visibility" to="hidden" begin="{every}" fill="freeze"/>')
        begins = ';'.join(event(origin,index)+f'+{duration}s' for origin in range(3) if origin!=index)
        nodes.append(f'<set attributeName="visibility" to="visible" begin="{begins}" fill="freeze"/>')
        nodes.append(text_nodes(item['body'],20,245,32,'#FFFFFF',spacing=46))
        nodes.append('</g></g>')
    for selected in range(3):
        initial = 'visible' if selected==0 else 'hidden'
        nodes.append(f'<g id="{prefix}_controls_{selected}" data-accordion-controls="{selected}" visibility="{initial}" style="visibility:{initial};"><set attributeName="visibility" to="hidden" begin="{every}" fill="freeze"/>')
        begins = ';'.join(event(origin,selected)+f'+{duration}s' for origin in range(3) if origin!=selected)
        nodes.append(f'<set attributeName="visibility" to="visible" begin="{begins}" fill="freeze"/>')
        for target in range(3):
            if target != selected:
                x, width = geometry(selected)[0][target], geometry(selected)[1][target]
                nodes.append(f'<g id="{prefix}_pick_{selected}_{target}" data-action="pick-{selected}-{target}" style="cursor:pointer;"><rect x="{x}" y="110" width="{width}" height="350" fill="#FFFFFF" fill-opacity="0" style="pointer-events:visiblePainted;"/></g>')
        nodes.append('</g>')
    nodes.append(text_nodes(['点开另一张卡片，查看它的内容'], 28, 511, 28, '#68777E'))
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
                      "canvas": [600, HEIGHT], "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
