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


PREFIX = "puzzle"
PREVIEW_TITLE = "点按拼图拼合"
PREVIEW_HELP = "点按让四块拼成完整画面，完成后可以重播。"


def read_config(path):
    c = load_base(path, {"labels", "caption", "duration"})
    if not isinstance(c.get("labels"), list) or len(c["labels"]) != 4:
        raise ValueError("labels 需要四个短标签")
    c["labels"] = [wrap(v, f"labels[{i}]", 3, 1) for i, v in enumerate(c["labels"])]
    c["caption"] = wrap(c.get("caption"), "caption", 18, 1)
    c["duration"] = seconds(c.get("duration", 1.2), "duration", 0.4, 4)
    return c


def render(c, p):
    a, d = c["accent"], c["duration"]
    start = f"{p}_play.click"
    parts = [svg_start(c, 570, "wechat-svg-puzzle-assemble"), '<rect x="172" y="138" width="256" height="256" rx="15" fill="#E3E8DF" stroke="#B8C7C7" stroke-width="2" stroke-dasharray="5 8"/>']
    offsets = [(-112, -38), (112, -30), (-105, 35), (110, 42)]
    colors = [a, "#E6B55B", "#A7CBC4", "#F0D3B9"]
    for i, (dx, dy) in enumerate(offsets):
        x, y = 176 + (i % 2) * 128, 142 + (i // 2) * 128
        delay = i * 0.12
        label = text_nodes(c["labels"][i], x+60, y+73, 32, "#FFFFFF" if i == 0 else "#26383E", "700").replace(f'x="{x+60}"', f'x="{x+60}" text-anchor="middle"')
        parts.append(f'''<g id="{p}_piece_{i}" data-piece-index="{i}" transform="translate({dx} {dy})">
<rect x="{x}" y="{y}" width="120" height="120" rx="13" fill="{colors[i]}"/>
<path d="M{x+16} {y+18}H{x+104} M{x+16} {y+102}H{x+104}" stroke="#FFFFFF" stroke-width="2" opacity="0.45"/>
{label}
<set attributeName="transform" to="translate({dx} {dy})" begin="{start}" fill="freeze"/>
<animateTransform attributeName="transform" type="translate" from="{dx} {dy}" to="0 0" begin="{start}+{delay:g}s" dur="{d:g}s" fill="freeze"/>
</g>''')
    parts.append(text_nodes(c["caption"], 300, 449, 28, "#586D73").replace('x="300"', 'x="300" text-anchor="middle"'))
    parts.append(replay_button(p, 492, d + 0.36, a, "点击拼合 / 重播"))
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
