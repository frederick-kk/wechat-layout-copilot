# Standalone SVG/SMIL renderer. Python standard library only.
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from pathlib import Path

INK = '#30271F'
MUTED = '#765B45'
SURFACE = '#FFFCF6'
BORDER = '#D4B797'


def require_object(value, allowed, field):
    if not isinstance(value, dict):
        raise ValueError(f'{field} needs a JSON object')
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(f'{field} has unknown fields: {", ".join(sorted(extra))}')
    return value


def require_list(value, field, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'{field} needs {minimum} to {maximum} items')
    return value


def wrap_text(value, field, width=16, maximum=1):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} needs nonempty text')
    lines = []
    for paragraph in value.split('\n'):
        line, used = '', 0.0
        for character in paragraph:
            point = ord(character)
            valid = point in {9, 10, 13} or 32 <= point <= 0xD7FF or 0xE000 <= point <= 0x10FFFF
            if not valid or 0xFDD0 <= point <= 0xFDEF or point & 0xFFFF in {0xFFFE, 0xFFFF}:
                raise ValueError(f'{field} contains an invalid XML character')
            if character == '\t':
                advance = 2.0
            elif unicodedata.combining(character) or character == '\u200d':
                advance = 0.0
            else:
                advance = 1.0 if unicodedata.east_asian_width(character) in 'WF' else 0.58
            if line and used + advance > width:
                lines.append(line)
                line, used = '', 0.0
            line += character
            used += advance
        lines.append(line)
    if len(lines) > maximum:
        raise ValueError(f'{field} needs {len(lines)} lines; limit is {maximum}')
    return lines


def checked_text(value, field, width=16, maximum=1):
    wrap_text(value, field, width, maximum)
    return value


def checked_color(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
        raise ValueError(f'{field} needs a six-digit HEX color')
    return value.upper()


def checked_artwork(value, field):
    if not isinstance(value, str) or value not in {'idea', 'studio', 'launch'}:
        raise ValueError(f'{field} needs idea, studio, or launch')
    return value


def base_config(config):
    config['title'] = checked_text(config.get('title'), 'title', 16, 1)
    config['description'] = checked_text(config.get('description'), 'description', 24, 2)
    config['accent'] = checked_color(config.get('accent', '#B55227'), 'accent')
    config['background'] = checked_color(config.get('background', '#FAF6ED'), 'background')
    return config


def node(tag, attributes=None, content=''):
    attributes = attributes or {}
    encoded = ' '.join(f'{key}="{html.escape(str(value), quote=True)}"' for key, value in attributes.items())
    opening = f'<{tag}' + (' ' + encoded if encoded else '')
    return opening + ('>' + content + f'</{tag}>' if content else '/>')


def label(value, x, y, size=28, fill=INK, weight='400', width=16, maximum=1, spacing=None, anchor='start'):
    spacing = spacing or size + 10
    lines = wrap_text(value, 'display text', width, maximum)
    return ''.join(node('text', {
        'x': x, 'y': y + index * spacing, 'font-size': size, 'fill': fill,
        'font-weight': weight, 'font-family': 'sans-serif', 'text-anchor': anchor,
        'pointer-events': 'none', 'xml:space': 'preserve',
    }, html.escape(line)) for index, line in enumerate(lines))


def box(x, y, width, height, fill=SURFACE, stroke=BORDER, radius=14):
    return node('rect', {'x': x, 'y': y, 'width': width, 'height': height, 'rx': radius,
                         'fill': fill, 'stroke': stroke, 'stroke-width': 1.5})


def artwork_slot(name):
    return node('g', {'data-artwork-slot': name, 'data-x': 30, 'data-y': 140,
                      'data-width': 540, 'data-height': 140},
                node('rect', {'x': 30, 'y': 140, 'width': 540, 'height': 140,
                              'rx': 14, 'fill': '#F0E1CE', 'stroke': BORDER,
                              'data-artwork-placeholder': 'true'}))


def action(name, text, target, x=30, y=700, width=540, height=64, color=None):
    return {'name': name, 'text': text, 'target': target, 'x': x, 'y': y,
            'width': width, 'height': height, 'color': color}


def static_button(text, x, y, width, height, active=False, accent='#B55227'):
    fill = accent if active else '#EFE4D5'
    text_color = '#FFFFFF' if active else MUTED
    return box(x, y, width, height, fill, BORDER, 12) + label(
        text, x + width / 2, y + height / 2 + 10, 27, text_color, '700',
        width=max(4, (width - 22) / 27), anchor='middle')


def make_state(name, content, actions, artwork='studio'):
    return {'name': name, 'content': content, 'actions': actions, 'artwork': artwork}


def trigger_id(prefix, state_name, action_name):
    state_token = state_name.replace('-', '_')
    action_token = action_name.replace('-', '_')
    return f'{prefix}_{state_token}_{action_token}'


def check_graph(states):
    names = [state['name'] for state in states]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate state names')
    known = set(names)
    edges = {}
    for state in states:
        local_names = [item['name'] for item in state['actions']]
        if len(local_names) != len(set(local_names)):
            raise ValueError(f'Duplicate actions in {state["name"]}')
        if any(item['target'] not in known for item in state['actions']):
            raise ValueError(f'Unknown target in {state["name"]}')
        if any(item['target'] == state['name'] for item in state['actions']):
            raise ValueError(f'Self transitions need a separate state in {state["name"]}')
        edges[state['name']] = [item['target'] for item in state['actions']]
    visited, pending = set(), [names[0]]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(edges[current])
    if visited != known:
        raise ValueError('Unreachable states: ' + ', '.join(sorted(known - visited)))


def render(config, prefix):
    states = build_states(config)
    check_graph(states)
    incoming = {state['name']: [] for state in states}
    for state in states:
        for item in state['actions']:
            incoming[item['target']].append(trigger_id(prefix, state['name'], item['name']) + '.click')
    panels = []
    for index, state in enumerate(states):
        name = state['name']
        visible = 'inline' if index == 0 else 'none'
        enter = ';'.join(incoming[name])
        leave = ';'.join(trigger_id(prefix, name, item['name']) + '.click' for item in state['actions'])
        content = []
        if enter:
            content.append(node('set', {'attributeName': 'display', 'to': 'inline', 'begin': enter, 'fill': 'freeze'}))
        if leave:
            content.append(node('set', {'attributeName': 'display', 'to': 'none', 'begin': leave, 'fill': 'freeze'}))
        content.extend([artwork_slot(state['artwork']), state['content']])
        for item in state['actions']:
            fill = item['color'] or config['accent']
            button = box(item['x'], item['y'], item['width'], item['height'], fill, fill, 12)
            button += label(item['text'], item['x'] + item['width'] / 2,
                            item['y'] + item['height'] / 2 + 10, 27, '#FFFFFF', '700',
                            width=max(4, (item['width'] - 24) / 27), anchor='middle')
            content.append(node('g', {'id': trigger_id(prefix, name, item['name']),
                                      'data-action': item['name'], 'data-target-state': item['target'],
                                      'role': 'button', 'aria-label': item['text'],
                                      'style': 'cursor:pointer;'}, button))
        panels.append(node('g', {'id': prefix + '_state_' + name.replace('-', '_'), 'data-state': name,
                                 'display': visible, 'style': 'display:' + visible + ';'}, ''.join(content)))
    background = box(0, 0, 600, 840, config['background'], BORDER, 18)
    heading = label(config['title'], 30, 54, 34, INK, '700')
    description = label(config['description'], 30, 96, 22, MUTED, width=24, maximum=2, spacing=29)
    footer = label(FOOTER, 30, 822, 19, MUTED, width=28)
    svg = node('svg', {'xmlns': 'http://www.w3.org/2000/svg', 'viewBox': '0 0 600 840',
                       'width': '100%', 'style': 'display:block;width:100%;height:auto;',
                       'data-component': SLUG, 'data-instance': prefix, 'role': 'group',
                       'aria-label': config['title']},
               node('desc', {}, html.escape(config['description'])) + background + heading + description + ''.join(panels) + footer)
    return '<section style="margin:20px 0;line-height:0;">' + svg + '</section>', len(states)


def preview(fragment, title):
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(title) + '</title></head>'
            '<body style="margin:0;background:#F2ECE2;font-family:sans-serif;">'
            '<main id="demo-stage" style="max-width:600px;margin:0 auto;">' + fragment + '</main></body></html>')


def write_outputs(targets, payloads, overwrite, config_path, config_digest):
    staged, backups, committed, locks = [], {}, [], []
    preserve = set()
    try:
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
        for target in sorted(targets, key=lambda item: str(item).casefold()):
            lock = target.with_name(target.name + '.render.lock')
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            locks.append(lock)
        if hashlib.sha256(config_path.read_bytes()).hexdigest() != config_digest:
            raise ValueError('Configuration changed during generation')
        for target, content in zip(targets, payloads):
            if target.exists():
                if not overwrite:
                    raise ValueError(f'Output exists; choose a new path or use --overwrite: {target}')
                if not target.is_file():
                    raise ValueError(f'Output is not a regular file: {target}')
                descriptor, filename = tempfile.mkstemp(prefix='.svg_previous_', dir=target.parent)
                os.close(descriptor)
                backups[target] = Path(filename)
                shutil.copy2(target, filename)
            descriptor, filename = tempfile.mkstemp(prefix='.svg_staged_', dir=target.parent)
            temporary = Path(filename)
            staged.append((target, temporary))
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
        if hashlib.sha256(config_path.read_bytes()).hexdigest() != config_digest:
            raise ValueError('Configuration changed before output commit')
        for target, temporary in staged:
            if overwrite:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)
            committed.append(target)
    except (OSError, ValueError) as error:
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
                    problems.append('Preserved backup: ' + str(backups[target]))
                else:
                    problems.append('Check partial output: ' + str(target))
        message = str(error) + (' | ' + ' | '.join(problems) if problems else '')
        raise ValueError(message) from error
    finally:
        for filename in [path for _, path in staged] + list(backups.values()) + locks:
            if filename not in preserve:
                filename.unlink(missing_ok=True)


def reject_constant(value):
    raise ValueError('Nonfinite JSON number: ' + value)


def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--preview-out', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        config_path = args.config.resolve(strict=True)
        original = config_path.read_bytes()
        raw = json.loads(original.decode('utf-8-sig'), parse_constant=reject_constant)
        config = validate_config(raw)
        targets = [args.out.resolve()] + ([args.preview_out.resolve()] if args.preview_out else [])
        if len(set(targets)) != len(targets):
            raise ValueError('Component and preview need distinct output paths')
        for target in targets:
            if target == config_path or target.suffix.lower() != '.html':
                raise ValueError('Output must be an HTML file distinct from the input configuration')
            protected_parts = {part.casefold() for part in target.parts[:-1]}
            if protected_parts.intersection({'scripts', 'assets', 'brand-assets', 'references'}):
                raise ValueError('Output cannot replace scripts, source assets, or references')
            if target.is_dir():
                raise ValueError('Output path points to a directory')
        prefix = SLUG.replace('-', '_') + '_' + uuid.uuid4().hex
        fragment, state_count = render(config, prefix)
        payloads = [fragment] + ([preview(fragment, config['title'])] if args.preview_out else [])
        write_outputs(targets, payloads, args.overwrite, config_path, hashlib.sha256(original).hexdigest())
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(json.dumps({'files': [str(path) for path in targets], 'canvas': [600, 840],
                      'instance': prefix, 'states': state_count,
                      'verification': 'generated; browser/editor/phone checks pending'}, ensure_ascii=False))


SLUG = 'wechat-svg-tabs'
TITLE = '标签页联动图文'
FOOTER = '点选标签，在同一位置阅读对应内容'


def validate_config(raw):
    config = base_config(require_object(raw, {'title', 'description', 'tabs', 'accent', 'background'}, 'config'))
    tabs = require_list(config.get('tabs'), 'tabs', 3, 3)
    for index, tab in enumerate(tabs):
        field = f'tabs[{index}]'
        require_object(tab, {'label', 'heading', 'body', 'artwork'}, field)
        checked_text(tab.get('label'), field + '.label', 5, 1)
        checked_text(tab.get('heading'), field + '.heading', 16, 1)
        checked_text(tab.get('body'), field + '.body', 16, 5)
        tab['artwork'] = checked_artwork(tab.get('artwork', ('idea', 'studio', 'launch')[index]), field + '.artwork')
    if len({tab['label'] for tab in tabs}) != 3:
        raise ValueError('Tab labels need distinct names')
    return config


def build_states(config):
    states = []
    for index, tab in enumerate(config['tabs']):
        content, actions = [], []
        for other_index, other in enumerate(config['tabs']):
            x = 30 + other_index * 185
            if index == other_index:
                content.append(static_button(other['label'], x, 310, 170, 64, True, config['accent']))
            else:
                actions.append(action(f'select-{other_index}', other['label'], f'tab-{other_index}', x, 310, 170))
        content.append(label(tab['heading'], 30, 434, 32, INK, '700'))
        content.append(label(tab['body'], 30, 493, 30, INK, maximum=5, spacing=44))
        content.append(label(f'当前第 {index + 1} 项 / 共 3 项', 30, 758, 23, MUTED, width=22))
        states.append(make_state(f'tab-{index}', ''.join(content), actions, tab['artwork']))
    return states


if __name__ == '__main__':
    main()
