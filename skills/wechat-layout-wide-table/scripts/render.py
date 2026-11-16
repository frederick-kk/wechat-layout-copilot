#!/usr/bin/env python3
"""Render a portable, editable article component using the Python standard library."""
import argparse
import base64
import html
import shutil
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]

def text(value, name, limit=180):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name}需要1至{limit}字的文字。')
    return html.escape(value, quote=True)

def items(value, name, minimum=1, maximum=12):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'{name}需要{minimum}至{maximum}项。')
    return value

def asset(value, config, image=True):
    if not isinstance(value, str) or not value:
        raise ValueError('需要本地素材文件路径。')
    path = (config.parent / value).resolve()
    allowed = {'.png', '.jpg', '.jpeg', '.webp'} if image else {'.mp4'}
    if path.suffix.lower() not in allowed or not path.is_file():
        raise ValueError('素材缺失或类型不支持。' + str(path))
    if image:
        mime = mimetypes.guess_type(path.name)[0] or 'image/webp'
        return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    return path

def render(spec, config, output):
    if not isinstance(spec, dict):
        raise ValueError('配置根节点应为对象。')
    title = text(spec.get('title'), 'title', 35)
    subtitle = text(spec.get('subtitle'), 'subtitle', 100)
    instance = 'fred-' + uuid.uuid4().hex[:12]
    content = render_body(spec, config, output)
    return f'<section id="{instance}" data-component="wechat-layout-wide-table" data-demo-height="900" style="box-sizing:border-box;max-width:600px;margin:0 auto;padding:28px 22px;background:#fbf7ef;color:#30291f;font-family:Arial,\'Microsoft YaHei\',sans-serif;line-height:1.75;overflow-wrap:anywhere;"><h2 style="margin:0 0 8px;font-size:25px;line-height:1.4;">{title}</h2><p style="margin:0 0 24px;font-size:14px;color:#796650;">{subtitle}</p>{content}</section>'

def render_body(spec, config, output):
    headers = [text(value, 'headers', 20) for value in items(spec.get('headers'), 'headers', 4, 10)]
    rows = items(spec.get('rows'), 'rows', 1, 20)
    rendered = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(headers):
            raise ValueError('每行列数必须与表头一致。')
        cells = ''.join('<td style="padding:16px 14px;border-bottom:1px solid #e5d6bf;vertical-align:top;">' + text(value, '单元格', 80) + '</td>' for value in row)
        rendered.append('<tr>' + cells + '</tr>')
    head = ''.join('<th scope="col" style="padding:16px 14px;background:#ac4d1d;color:#fff;text-align:left;">' + value + '</th>' for value in headers)
    return '<p style="color:#a74817;font-size:13px;font-weight:bold;">向右滑动，完整查看每一列 →</p><section data-action="scroll-table" tabindex="0" aria-label="可横向滚动的完整表格" style="width:100%;overflow-x:auto;border:1px solid #d8bea0;border-radius:12px;-webkit-overflow-scrolling:touch;"><table style="width:100%;min-width:820px;border-collapse:collapse;font-size:16px;line-height:1.6;"><caption style="text-align:left;padding:12px 14px;background:#f2e6d2;">' + text(spec.get('caption'), 'caption', 60) + '</caption><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(rendered) + '</tbody></table></section><p style="font-size:12px;color:#796650;">固定完整字号，重点信息逐列核对。</p>'


def write_outputs(targets, payloads, overwrite, config, config_digest):
    staged, backups, committed, locks = [], {}, [], []
    preserve = set()
    problems = []
    failure = None
    try:
        for target in targets:
            if target.is_dir():
                raise ValueError('Output points to a directory: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
        for target in sorted(targets, key=lambda path: str(path).casefold()):
            lock = target.with_name(target.name + '.render.lock')
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            locks.append(lock)
        if hashlib.sha256(config.read_bytes()).hexdigest() != config_digest:
            raise ValueError('Configuration changed during generation')
        for target, content in zip(targets, payloads):
            if target.exists():
                if not overwrite:
                    raise ValueError('Output already exists: ' + str(target))
                if not target.is_file():
                    raise ValueError('Output is not a regular file: ' + str(target))
                descriptor, name = tempfile.mkstemp(prefix='.layout_previous_', dir=target.parent)
                os.close(descriptor)
                backup = Path(name)
                backups[target] = backup
                shutil.copy2(target, backup)
            descriptor, name = tempfile.mkstemp(prefix='.layout_staged_', dir=target.parent)
            temporary = Path(name)
            staged.append((target, temporary))
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
        if hashlib.sha256(config.read_bytes()).hexdigest() != config_digest:
            raise ValueError('Configuration changed before output commit')
        for target, temporary in staged:
            if overwrite:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)
            committed.append(target)
    except (OSError, ValueError) as error:
        failure = str(error)
        for target in reversed(committed):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink(missing_ok=True)
            except OSError as recovery_error:
                if target in backups:
                    preserve.add(backups[target])
                    problems.append('Recovery failed for ' + str(target) + '. Backup retained at ' + str(backups[target]))
                else:
                    problems.append('Partial output retained at ' + str(target))
                problems.append(str(recovery_error))
    finally:
        owned = [(path, 'staged output') for _, path in staged]
        owned += [(path, 'backup') for path in backups.values()]
        owned += [(path, 'output lock') for path in locks]
        for path, kind in owned:
            if path in preserve:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                problems.append('Retained ' + kind + ': ' + str(path) + '. ' + str(cleanup_error))
    if failure is not None or problems:
        status = failure if failure is not None else 'Outputs committed; cleanup incomplete'
        raise ValueError(status + (' | ' + ' | '.join(problems) if problems else ''))


def main():
    parser = argparse.ArgumentParser(description='横向宽表，本地HTML预览与独立素材生成。')
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--preview-out')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    config, output = Path(args.config).resolve(), Path(args.out).resolve()
    preview = Path(args.preview_out).resolve() if args.preview_out else None
    destinations = [output] + ([preview] if preview else [])
    try:
        if len(set(destinations)) != len(destinations):
            raise ValueError('片段和预览需要不同输出路径。')
        protected = {p.resolve() for p in ROOT.rglob('*') if p.is_file() and (p.suffix.lower() in {'.py','.json','.md','.webp','.png','.jpg','.mp4'} or p.name == 'LICENSE')}
        protected.add(config)
        if any(path in protected or path.suffix.lower() not in {'.html','.htm'} for path in destinations):
            raise ValueError('请输出HTML文件，并保留原始配置、说明、脚本与素材。')
        if any(path.is_dir() for path in destinations):
            raise ValueError('Output paths must name HTML files, not directories.')
        if not args.overwrite and any(path.exists() for path in destinations):
            raise ValueError('输出已存在，请换路径或使用--overwrite。')
        config_bytes = config.read_bytes()
        config_digest = hashlib.sha256(config_bytes).hexdigest()
        spec = json.loads(config_bytes.decode('utf-8-sig'))
        fragment = render(spec, config, output)
        outputs = [(output, fragment)]
        if preview:
            preview_fragment = fragment if preview.parent == output.parent else render(spec, config, preview)
            outputs.append((preview, '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>横向宽表</title><body style="margin:0;background:#eee5d7"><main>' + preview_fragment + '</main></body></html>'))
        write_outputs([path for path, _ in outputs], [content for _, content in outputs], args.overwrite, config, config_digest)
        print(json.dumps({'status':'created','files':[str(path) for path in destinations]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'status':'needs_input','issues':[str(error)]}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
