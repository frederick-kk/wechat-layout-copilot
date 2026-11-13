"""Generate an original SVG and SMIL article component using Python standard library."""
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

COMPONENT = 'wechat-svg-envelope'
TITLE = '信封拆信与收回'
PREFIX = 'envelope'
FIELDS = {'title': (14, 1), 'letter_title': (12, 1), 'letter_body': (12, 3)}

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


def button(prefix, action, label, x, y, accent, duration):
    own = f"{prefix}_{action}"
    forward, reverse = f"{prefix}_forward", f"{prefix}_reverse"
    enabled = action == "forward"
    opposite = reverse if enabled else forward
    opacity = '1' if enabled else '0.45'
    pointer = 'auto' if enabled else 'none'
    return f'''<g id="{own}" data-action="{action}" opacity="{opacity}" style="cursor:pointer;pointer-events:{pointer};opacity:{opacity};">
<set attributeName="pointer-events" to="none" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="pointer-events" to="auto" begin="{opposite}.click+{duration:g}s" fill="freeze"/>
<set attributeName="opacity" to="0.45" begin="{forward}.click;{reverse}.click" fill="freeze"/>
<set attributeName="opacity" to="1" begin="{opposite}.click+{duration:g}s" fill="freeze"/>
<rect x="{x}" y="{y}" width="264" height="60" rx="13" fill="{accent}"/>
<text x="{x + 132}" y="{y + 40}" text-anchor="middle" font-size="30" fill="#FFFFFF" style="pointer-events:none;">{html.escape(label)}</text>
</g>'''


def shell(content, height, background):
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" width="100%" style="display:block;width:100%;height:auto;overflow:hidden;" font-family="sans-serif" data-component="{COMPONENT}">
<rect x="1" y="1" width="598" height="{height-2}" rx="20" fill="{background}"/>
{content}
</svg></section>'''


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title><body style="margin:0;background:#F5F3ED;font-family:system-ui,sans-serif;color:#27383F;">
<main style="box-sizing:border-box;max-width:632px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">{TITLE}</h1><p style="line-height:1.8;">点击亮起的按钮，动画完成后再切回。</p>{fragment}</main></body></html>'''


def read_config(path):
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict):
        raise ValueError('配置需要JSON对象')
    unknown = set(config) - set(FIELDS) - {'accent', 'background', 'duration'}
    if unknown:
        raise ValueError('未知配置字段 ' + ', '.join(sorted(unknown)))
    prepared = {field: wrap(config.get(field), field, width, count) for field, (width, count) in FIELDS.items()}
    prepared['accent'] = color(config.get('accent', '#167E99'), 'accent')
    prepared['background'] = color(config.get('background', '#FFF9EE'), 'background')
    prepared['duration'] = number(config.get('duration', 1), 'duration', 0.4, 3)
    return prepared



def render(c, prefix):
    accent, background, duration = c['accent'], c['background'], c['duration']
    flap_time, paper_time = duration * 0.2, duration * 0.8
    forward, reverse = f'{prefix}_forward', f'{prefix}_reverse'
    content = text_nodes(c['title'], 30, 52, 36, '#27383F', '700')
    content += f'''<rect x="40" y="300" width="520" height="300" rx="14" fill="#E9DBBF" stroke="#B59A6A" stroke-width="2"/>
<g id="{prefix}_paper" data-paper="true" transform="translate(0 0)">
<animateTransform attributeName="transform" type="translate" from="0 0" to="0 -190" begin="{forward}.click+{flap_time:g}s" dur="{paper_time:g}s" fill="freeze"/>
<animateTransform attributeName="transform" type="translate" from="0 -190" to="0 0" begin="{reverse}.click" dur="{paper_time:g}s" fill="freeze"/>
<rect x="64" y="300" width="472" height="300" rx="8" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>
{text_nodes(c['letter_title'], 88, 342, 36, accent, '700')}
{text_nodes(c['letter_body'], 88, 404, 34, '#27383F', spacing=42)}
</g>
<rect x="40" y="320" width="520" height="300" rx="12" fill="#EBD4AD" stroke="#B59A6A" stroke-width="2"/>
<path d="M42 322L300 495L558 322 M42 618L220 458 M558 618L380 458" fill="none" stroke="#B59A6A" stroke-width="3"/>
<g transform="translate(300 300)"><g id="{prefix}_flap" data-flap="true" transform="scale(1 1)" visibility="visible" style="visibility:visible;">
<animateTransform attributeName="transform" type="scale" from="1 1" to="1 -0.8" begin="{forward}.click" dur="{flap_time:g}s" fill="freeze"/>
<set attributeName="visibility" to="hidden" begin="{forward}.click+{flap_time:g}s" fill="freeze"/>
<set attributeName="visibility" to="visible" begin="{reverse}.click+{paper_time:g}s" fill="freeze"/>
<animateTransform attributeName="transform" type="scale" from="1 -0.8" to="1 1" begin="{reverse}.click+{paper_time:g}s" dur="{flap_time:g}s" fill="freeze"/>
<path d="M-260 0L0 175L260 0Z" fill="#F3E4C9" stroke="#B59A6A" stroke-width="2"/>
</g></g>
<circle cx="300" cy="495" r="26" fill="{accent}"/>
<path d="M287 495L297 505L314 484" fill="none" stroke="#FFFFFF" stroke-width="4"/>
'''
    content += button(prefix, 'reverse', '收好这封信', 24, 650, accent, duration)
    content += button(prefix, 'forward', '拆开来看看', 312, 650, accent, duration)
    return shell(content, 740, background)
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



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--preview-out', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    try:
        config = read_config(args.config)
        resolved = [p.resolve() for p in targets]
        if len(set(resolved)) != len(resolved):
            raise ValueError('片段和预览需要不同路径')
        script_path = Path(__file__).resolve()
        protected = {args.config.resolve(), script_path, (script_path.parents[1] / 'SKILL.md').resolve()}
        if protected.intersection(resolved):
            raise ValueError('输出不能覆盖输入配置、Skill说明或生成器')
        if any(path.suffix.lower() not in {'.html', '.htm'} for path in targets):
            raise ValueError('片段和预览输出需要使用.html或.htm文件')
        if any(path.is_dir() for path in targets):
            raise ValueError('输出需要文件名')
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError('输出已存在，请换路径或使用 --overwrite')
        prefix = PREFIX + '_' + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({'files': [str(p.resolve()) for p in targets], 'component': COMPONENT, 'instance': prefix,
                      'verification': 'generated; browser/editor/phone checks pending'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
