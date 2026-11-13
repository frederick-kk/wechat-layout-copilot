import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_THEME = {
    'accent': '#BD652E', 'text': '#352D25', 'muted': '#705D4D',
    'surface': '#FAF6EE', 'border': '#DCC7B0',
}


def escape(value):
    return html.escape(value, quote=True).replace('\n', '<br>')


def check_spec(spec):
    issues = []
    if not isinstance(spec, dict):
        return ['输入应为包含 blocks 的 JSON 对象。']
    theme = spec.get('theme', {})
    if not isinstance(theme, dict):
        issues.append('theme 应为颜色对象。')
    else:
        for name, value in theme.items():
            if name not in DEFAULT_THEME or not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                issues.append(f'theme.{name} 请使用支持的名称和六位 HEX 色值。')
    blocks = spec.get('blocks')
    if not isinstance(blocks, list) or not blocks:
        return issues + ['请提供非空的 blocks 组件列表。']
    required = {
        'heading': ['title'], 'paragraph': ['text'], 'quote': ['text'],
        'image': ['src', 'alt', 'caption'],
    }
    for index, block in enumerate(blocks, 1):
        location = f'第{index}个组件'
        if not isinstance(block, dict):
            issues.append(location + '应为对象。')
            continue
        kind = block.get('type')
        if kind in required:
            for name in required[kind]:
                if not isinstance(block.get(name), str) or not block[name].strip():
                    issues.append(f'{location}需要{name}。')
            if kind == 'heading' and 'number' in block and not isinstance(block['number'], str):
                issues.append(location + '的number应为文字。')
            if kind == 'image' and isinstance(block.get('src'), str):
                url = urlparse(block['src'])
                if url.scheme != 'https' or not url.netloc:
                    issues.append(location + '的图片需要可访问的HTTPS托管地址。')
        elif kind == 'steps':
            items = block.get('items')
            if not isinstance(items, list) or not items:
                issues.append(location + '需要非空的items步骤列表。')
                continue
            for step_index, item in enumerate(items, 1):
                if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item[key].strip() for key in ['title', 'text']):
                    issues.append(f'{location}的第{step_index}步需要title和text。')
        elif kind == 'table':
            headers, rows = block.get('headers'), block.get('rows')
            if not isinstance(headers, list) or not headers or any(not isinstance(value, str) or not value.strip() for value in headers):
                issues.append(location + '需要完整的headers表头。')
                continue
            if not isinstance(rows, list) or not rows:
                issues.append(location + '需要非空的rows数据。')
                continue
            for row_index, row in enumerate(rows, 1):
                if not isinstance(row, list) or len(row) != len(headers) or any(not isinstance(value, str) for value in row):
                    issues.append(f'{location}的第{row_index}行应与表头列数一致，各格使用文字。')
        else:
            issues.append(location + '的type可选heading、paragraph、quote、steps、table或image。')
    return issues


def render_block(block, theme):
    accent, border, surface = theme['accent'], theme['border'], theme['surface']
    kind = block['type']
    if kind == 'heading':
        number = escape(block.get('number', ''))
        return f'<section data-no-dark="" style="margin:28px 0 18px;padding:12px 0;border-bottom:1px solid {border};"><span data-no-dark="" style="display:inline-block;margin-right:10px;color:{accent};font-size:25px;font-weight:700;vertical-align:baseline;">{number}</span><strong style="font-size:21px;line-height:1.5;">{escape(block["title"])}</strong></section>'
    if kind == 'paragraph':
        return f'<p style="margin:18px 0;">{escape(block["text"])}</p>'
    if kind == 'quote':
        return f'<section data-no-dark="" style="margin:22px 0;padding:12px 16px;border-left:3px solid {accent};background-color:{surface};"><p style="margin:0;font-weight:600;">{escape(block["text"])}</p></section>'
    if kind == 'steps':
        cards = []
        for index, item in enumerate(block['items'], 1):
            cards.append(f'<section data-no-dark="" style="margin:14px 0;padding:10px 14px;border-left:2px solid {accent};border-bottom:1px solid {border};"><p style="margin:0 0 6px;font-weight:700;">{index}. {escape(item["title"])}</p><p style="margin:0;">{escape(item["text"])}</p></section>')
        return '<section>' + ''.join(cards) + '</section>'
    if kind == 'table':
        headers = ''.join(f'<th data-no-dark="" style="padding:9px;border:1px solid {border};background-color:{surface};text-align:left;">{escape(value)}</th>' for value in block['headers'])
        rows = []
        for row in block['rows']:
            cells = ''.join(f'<td data-no-dark="" style="padding:9px;border:1px solid {border};vertical-align:top;">{escape(value)}</td>' for value in row)
            rows.append('<tr>' + cells + '</tr>')
        return '<table style="width:100%;table-layout:fixed;border-collapse:collapse;font-size:14px;line-height:1.65;word-break:break-word;"><thead><tr>' + headers + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    return f'<section style="margin:22px 0;"><img src="{escape(block["src"])}" alt="{escape(block["alt"])}" style="display:block;width:100%;height:auto;"><p data-no-dark="" style="margin:8px 0 0;font-size:13px;color:{theme["muted"]};">{escape(block["caption"])}</p></section>'


def main():
    parser = argparse.ArgumentParser(description='从结构化正文生成公众号HTML组件。')
    parser.add_argument('--spec', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--preview')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        spec = json.loads(Path(args.spec).read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'needs_input', 'issues': [str(error)]}, ensure_ascii=False))
        return 2
    issues = check_spec(spec)
    destinations = [Path(args.out)] + ([Path(args.preview)] if args.preview else [])
    if len({str(path.resolve()) for path in destinations}) != len(destinations):
        issues.append('片段和预览请使用不同的输出路径。')
    if Path(args.spec).resolve() in [path.resolve() for path in destinations]:
        issues.append('输出请使用与输入JSON不同的路径，以保全原始材料。')
    if not args.overwrite:
        issues.extend(f'输出已存在，请换路径或显式使用--overwrite。{path}' for path in destinations if path.exists())
    if issues:
        print(json.dumps({'status': 'needs_input', 'issues': issues}, ensure_ascii=False, indent=2))
        return 2
    theme = dict(DEFAULT_THEME)
    theme.update(spec.get('theme', {}))
    content = ''.join(render_block(block, theme) for block in spec['blocks'])
    fragment = f'<section data-no-dark="" style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:16px;line-height:1.8;color:{theme["text"]};word-break:break-word;">{content}</section>'
    preview = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公众号组件预览</title><body style="margin:0;background:#ffffff;"><main style="box-sizing:border-box;max-width:680px;margin:0 auto;padding:20px;">' + fragment + '</main></body></html>'
    outputs = [(Path(args.out), fragment)]
    if args.preview:
        outputs.append((Path(args.preview), preview))
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    print(json.dumps({'status': 'created', 'files': [str(path.resolve()) for path, _ in outputs], 'blocks': len(spec['blocks'])}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
