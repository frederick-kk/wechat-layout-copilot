"""Render a single-choice quiz with answer-specific feedback using SVG and SMIL."""

import argparse
import html
import json
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



def read_config(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("配置需要 JSON 对象")
    if set(config) - {"question", "choices", "accent", "background"}:
        raise ValueError("配置含未知字段，请核对 question、choices 与主题字段")
    prepared = {"question": wrap(config.get("question"), "question", 14, 2),
                "accent": color(config.get("accent", "#177F91"), "accent"),
                "background": color(config.get("background", "#FFF9EF"), "background"),
                "inputs": {path.resolve()}}
    choices = config.get("choices")
    if not isinstance(choices, list) or not 2 <= len(choices) <= 4:
        raise ValueError("choices 需要2到4个选项")
    prepared["choices"] = []
    for index, choice in enumerate(choices):
        field = f"choices[{index}]"
        if not isinstance(choice, dict) or set(choice) - {"label", "feedback", "correct"}:
            raise ValueError(f"{field} 需要 label、feedback、correct")
        if not isinstance(choice.get("correct"), bool):
            raise ValueError(f"{field}.correct 需要 true 或 false")
        prepared["choices"].append({
            "label": wrap(choice.get("label"), f"{field}.label", 14, 1),
            "feedback": wrap(choice.get("feedback"), f"{field}.feedback", 14, 5),
            "correct": choice["correct"],
        })
    if sum(choice["correct"] for choice in prepared["choices"]) != 1:
        raise ValueError("单选题需要恰好一个 correct 为 true 的选项")
    return prepared


def render(config, prefix):
    accent, background = config["accent"], config["background"]
    choices, feedbacks = [], []
    for index, choice in enumerate(config["choices"]):
        trigger = f"{prefix}_choose_{index}"
        retry = f"{prefix}_retry_{index}"
        y = 160 + index * 90
        letter = chr(65 + index)
        choices.append(f'''<g id="{trigger}" data-quiz-choice="{index}" style="cursor:pointer;">
<rect x="36" y="{y}" width="528" height="70" rx="14" fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>
<circle cx="68" cy="{y + 35}" r="21" fill="{accent}"/>
{text_nodes([letter], 57, y + 46, 29, '#FFFFFF', '700')}
{text_nodes(choice['label'], 104, y + 46, 32, '#27383F', '700')}
</g>''')
        result_color = "#19785A" if choice["correct"] else "#B75D27"
        heading = "答对啦" if choice["correct"] else "再想一想"
        feedbacks.append(f'''<g visibility="hidden" style="visibility:hidden;" data-quiz-feedback="{index}">
<set attributeName="visibility" to="visible" begin="{trigger}.click" end="{retry}.click" restart="always"/>
<g opacity="0">
<animate attributeName="opacity" from="0" to="1" begin="{trigger}.click" dur="0.24s" fill="freeze" restart="always"/>
<rect width="600" height="600" rx="20" fill="{background}" pointer-events="visiblePainted"/>
{text_nodes([heading], 36, 72, 38, result_color, '700')}
{text_nodes([f'你选了 {letter}'], 36, 130, 27, '#68777E')}
{text_nodes(choice['label'], 36, 174, 32, '#27383F', '700')}
{text_nodes(choice['feedback'], 36, 244, 34, '#27383F', spacing=44)}
<g id="{retry}" data-quiz-retry="{index}" style="cursor:pointer;">
<rect x="36" y="510" width="528" height="62" rx="12" fill="{accent}" pointer-events="visiblePainted"/>
{text_nodes(['返回题目，再选一次'], 145, 552, 30, '#FFFFFF', '700')}
</g></g></g>''')
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" width="100%" style="display:block;width:100%;height:auto;" data-component="wechat-svg-quiz" role="group" aria-label="单题点击答题">
<desc>点击选项查看反馈，返回后可重新作答。</desc>
<rect width="600" height="600" rx="20" fill="{background}"/>
{text_nodes(config['question'], 36, 63, 36, '#27383F', '700')}
{''.join(choices)}
{text_nodes(['点一个选项，看看你的判断'], 36, 564, 26, '#68777E')}
{''.join(feedbacks)}
</svg></section>'''


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>单题点击答题</title><body style="margin:0;background:#F5F3ED;font-family:system-ui,sans-serif;color:#27383F;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">单题点击答题</h1><p style="line-height:1.8;">每个答案都有对应反馈，返回后可以重选。</p>{fragment}</main></body></html>'''


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
        if len(set(resolved)) != len(resolved):
            raise ValueError("片段和预览需要不同路径")
        if config["inputs"].intersection(resolved):
            raise ValueError("输出不能覆盖输入配置")
        if any(path.is_dir() for path in targets):
            raise ValueError("输出路径指向目录，请指定文件名")
        if not args.overwrite and any(path.exists() for path in targets):
            raise ValueError("输出已存在，请换路径或使用 --overwrite")
        prefix = "quiz_" + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"files": [str(path.resolve()) for path in targets], "canvas": [600, 600],
                      "instance": prefix, "choices": len(config["choices"]),
                      "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
