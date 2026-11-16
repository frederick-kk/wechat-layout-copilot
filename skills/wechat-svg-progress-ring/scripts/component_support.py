"""Portable SVG validation and file output shared inside this Skill package."""
import argparse
from decimal import Decimal
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import uuid

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

def number(value, field, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError(f"{field} 需要{low}到{high}之间的有限数字")
    return value

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


def fmt(value):
    decimal = Decimal(str(value))
    if decimal == 0:
        return '0'
    value_text = format(decimal, 'f')
    return value_text.rstrip('0').rstrip('.') if '.' in value_text else value_text


def label(value, field, limit=12):
    xml_text(value, field)
    if '\n' in value or len(value) > limit:
        raise ValueError(f'{field}需要一行且最多{limit}字')
    return html.escape(value)


def items(value, field, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'{field}需要{minimum}至{maximum}项')
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f'{field}每项需要对象')
    return value


def control(prefix, action, caption, x, y, width=264):
    return f'<g id="{prefix}_{action}" data-action="{action}" style="cursor:pointer"><rect x="{x}" y="{y}" width="{width}" height="52" rx="10" fill="#A94B21"/><text x="{x+width/2}" y="{y+35}" text-anchor="middle" font-family="sans-serif" font-size="23" fill="white" pointer-events="none">{html.escape(caption)}</text></g>'


def art_slot(kind, x, y, width, height):
    return f'<g data-artwork-slot="{kind}" data-x="{x}" data-y="{y}" data-width="{width}" data-height="{height}"><rect data-artwork-placeholder="true" x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="#F4EBDD" stroke="#E4D3BA"/></g>'


def shell(component, title, description, content, height, accent='#A94B21', background='#FAF6ED'):
    title = label(title, 'title', 16)
    description = label(description, 'description', 30)
    return f'<section style="line-height:0;margin:20px 0"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 600 {height}" data-component="{component}" style="display:block;width:100%;height:auto;overflow:hidden;font-family:sans-serif"><rect x="1" y="1" width="598" height="{height-2}" rx="18" fill="{background}"/><text x="30" y="48" font-size="31" font-weight="700" fill="#30271F">{title}</text><text x="30" y="84" font-size="20" fill="#765B45">{description}</text>{content}</svg></section>'


def preview(fragment, title):
    return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><body style="margin:0;background:#F5F0E7"><main style="max-width:600px;margin:auto">{fragment}</main></body></html>'


def run(component, title, render, script_path):
    parser = argparse.ArgumentParser(description=title)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--preview-out', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        if not isinstance(config, dict):
            raise ValueError('配置需要JSON对象')
        paths = [args.out] + ([args.preview_out] if args.preview_out else [])
        resolved = [path.resolve() for path in paths]
        protected = {args.config.resolve(), Path(script_path).resolve(), Path(__file__).resolve(), Path(script_path).resolve().parents[1] / 'SKILL.md'}
        if len(set(resolved)) != len(resolved) or protected.intersection(resolved):
            raise ValueError('输出需互不相同，并且不能覆盖输入配置或Skill源文件')
        if any(path.suffix.lower() not in {'.html', '.htm'} for path in paths):
            raise ValueError('输出需要.html或.htm文件')
        if any(path.is_dir() for path in paths):
            raise ValueError('输出目标需要文件名')
        if not args.overwrite and any(path.exists() for path in paths):
            raise ValueError('输出已存在，请换路径或使用--overwrite')
        prefix = component.replace('-', '_') + '_' + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(paths, [fragment] + ([preview(fragment, title)] if args.preview_out else []), args.overwrite)
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({'component': component, 'files': [str(path.resolve()) for path in paths], 'instance': prefix, 'verification': 'generated; browser, editor and phone checks pending'}, ensure_ascii=False))
