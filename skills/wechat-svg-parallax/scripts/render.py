"""Render parallax as an original SVG/SMIL component."""

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




def text_button(identifier, action, label, x, y, width, accent):
    return f'''<g id="{identifier}" data-action="{action}" style="cursor:pointer;">
<rect x="{x}" y="{y}" width="{width}" height="60" rx="12" fill="{accent}"/>
<text x="{x+width/2:g}" y="{y+40}" text-anchor="middle" font-size="30" fill="#FFFFFF" font-family="sans-serif" style="pointer-events:none;">{html.escape(label)}</text>
</g>'''


def gate(identifier, action, label, x, y, width, accent, forward, reverse, duration, initial):
    available = 'auto' if initial else 'none'
    opacity = '1' if initial else '0.45'
    enabling = reverse if initial else forward
    content = text_button(identifier, action, label, x, y, width, accent)
    content = content.replace('style="cursor:pointer;"', f'opacity="{opacity}" style="cursor:pointer;pointer-events:{available};opacity:{opacity};"', 1)
    commands = f'''<set attributeName="pointer-events" to="none" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="pointer-events" to="auto" begin="{enabling}.click+{duration}s" fill="freeze"/>
<set attributeName="opacity" to="0.45" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="opacity" to="1" begin="{enabling}.click+{duration}s" fill="freeze"/>'''
    return content.replace('</g>', commands+'</g>')


TITLE = '三层视差场景'
INSTRUCTION = '点击向前看看，再点击返回起点，观察三个景层的速度差。'
PREFIX = 'parallax_'
HEIGHT = 580


def read_config(path):
    config, prepared = common_config(path, {"labels"})
    labels = config.get("labels")
    if not isinstance(labels, list) or len(labels) != 3:
        raise ValueError("labels需要远景、中景、近景三段文字")
    prepared["labels"] = [wrap(value, f"labels[{index}]", 6, 1) for index, value in enumerate(labels)]
    return prepared


def render(config, prefix):
    accent, duration = config["accent"], config["duration"]
    forward, reverse = f'{prefix}_forward', f'{prefix}_back'
    nodes = [svg_start(config, 'wechat-svg-parallax', HEIGHT), '<rect x="0" y="92" width="600" height="310" fill="#DCEEF0"/>']
    artwork = [
        '<path d="M-100 300 L70 132 L210 284 L400 112 L580 286 L770 140 L1000 320 V410 H-100Z" fill="#A7CFD0"/>',
        '<path d="M-100 404V300H60V260H150V340H240V230H350V320H450V268H540V340H680V255H800V320H1000V410Z" fill="#60A6B1"/>',
        f'<path d="M-100 404V356Q50 320 180 355T470 350T760 350T1040 350V410Z" fill="{accent}"/><path d="M-100 380H1040" stroke="#FFFFFF" stroke-width="3" stroke-dasharray="25 18"/>'
    ]
    for index, (name, displacement) in enumerate([('far',-40),('middle',-100),('near',-180)]):
        nodes.append(f'<g id="{prefix}_{name}" data-parallax-layer="{name}" transform="translate(0 0)"><animateTransform attributeName="transform" type="translate" from="0 0" to="{displacement} 0" begin="{forward}.click" dur="{duration}s" fill="freeze"/><animateTransform attributeName="transform" type="translate" from="{displacement} 0" to="0 0" begin="{reverse}.click" dur="{duration}s" fill="freeze"/>{artwork[index]}{text_nodes(config["labels"][index], [230,240,240][index], [165,275,365][index], 30, ["#27383F","#FFFFFF","#FFFFFF"][index], "700")}</g>')
    nodes.append(gate(reverse, 'back', '返回起点', 24, 438, 264, '#68777E', forward, reverse, duration, False))
    nodes.append(gate(forward, 'forward', '向前看看', 312, 438, 264, accent, forward, reverse, duration, True))
    nodes.append(text_nodes(['远景慢，中景居中，近景更快'], 31, 547, 28, '#68777E'))
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
