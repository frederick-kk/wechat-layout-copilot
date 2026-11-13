"""Render a multi-step branching story with endings and restart using SVG and SMIL."""

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
    if set(config) - {"start", "nodes", "accent", "background"}:
        raise ValueError("配置含未知字段，请核对 start、nodes 与主题字段")
    prepared = {"accent": color(config.get("accent", "#177F91"), "accent"),
                "background": color(config.get("background", "#FFF9EF"), "background"),
                "inputs": {path.resolve()}}
    nodes = config.get("nodes")
    if not isinstance(nodes, list) or not 3 <= len(nodes) <= 12:
        raise ValueError("nodes 需要3到12个故事节点")
    prepared["nodes"] = []
    identifiers = set()
    for index, node in enumerate(nodes):
        field = f"nodes[{index}]"
        if not isinstance(node, dict) or set(node) - {"id", "title", "body", "choices"}:
            raise ValueError(f"{field} 需要 id、title、body、choices")
        identifier = node.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", identifier):
            raise ValueError(f"{field}.id 以英文字母开头，仅含字母、数字和下划线，最多40位")
        if identifier in identifiers:
            raise ValueError(f"故事节点 id 重复 {identifier}")
        identifiers.add(identifier)
        choices = node.get("choices")
        if not isinstance(choices, list) or len(choices) > 3:
            raise ValueError(f"{field}.choices 需要0到3个选项，空列表表示结局")
        prepared_choices = []
        for choice_index, choice in enumerate(choices):
            location = f"{field}.choices[{choice_index}]"
            if not isinstance(choice, dict) or set(choice) != {"label", "to"}:
                raise ValueError(f"{location} 需要 label 和 to")
            target = choice["to"]
            if not isinstance(target, str):
                raise ValueError(f"{location}.to 需要节点 id")
            if target == identifier:
                raise ValueError(f"{location} 不能跳回当前同一节点，请指向另一节点")
            prepared_choices.append({"label": wrap(choice["label"], f"{location}.label", 14, 1), "to": target})
        prepared["nodes"].append({"id": identifier,
                                  "title": wrap(node.get("title"), f"{field}.title", 14, 2),
                                  "body": wrap(node.get("body"), f"{field}.body", 14, 4),
                                  "choices": prepared_choices})
    start = config.get("start")
    if not isinstance(start, str) or start not in identifiers:
        raise ValueError("start 需要引用一个实际节点 id")
    prepared["start"] = start
    if any(choice["to"] not in identifiers for node in prepared["nodes"] for choice in node["choices"]):
        raise ValueError("存在指向缺失节点的 to，请逐个核对")
    indexed = {node["id"]: node for node in prepared["nodes"]}
    reachable = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current not in reachable:
            reachable.add(current)
            pending.extend(choice["to"] for choice in indexed[current]["choices"])
    if reachable != identifiers:
        raise ValueError("存在从起点无法到达的节点 " + ", ".join(sorted(identifiers - reachable)))
    endings = {node["id"] for node in prepared["nodes"] if not node["choices"]}
    if not endings:
        raise ValueError("故事至少需要一个 choices 为空的结局")
    can_finish = set(endings)
    while True:
        expanded = can_finish | {node["id"] for node in prepared["nodes"] if any(choice["to"] in can_finish for choice in node["choices"])}
        if expanded == can_finish:
            break
        can_finish = expanded
    if can_finish != identifiers:
        raise ValueError("以下节点无法走到任何结局 " + ", ".join(sorted(identifiers - can_finish)))
    if sum(bool(node["choices"]) for node in prepared["nodes"]) < 2:
        raise ValueError("多步故事至少需要两个带选项的节点")
    return prepared


def render(config, prefix):
    accent, background = config["accent"], config["background"]
    nodes = config["nodes"]
    incoming = {node["id"]: [] for node in nodes}
    restart_ids = []
    for node in nodes:
        if not node["choices"]:
            restart_ids.append(f"{prefix}_restart_{node['id']}")
        for index, choice in enumerate(node["choices"]):
            incoming[choice["to"]].append(f"{prefix}_pick_{node['id']}_{index}.click")
    incoming[config["start"]].extend(f"{identifier}.click" for identifier in restart_ids)
    panels = []
    for node in nodes:
        identifier = node["id"]
        visible = "inline" if identifier == config["start"] else "none"
        enter = ";".join(incoming[identifier])
        buttons = []
        leave = []
        for index, choice in enumerate(node["choices"]):
            trigger = f"{prefix}_pick_{identifier}_{index}"
            leave.append(trigger + ".click")
            y = 360 + index * 82
            buttons.append(f'''<g id="{trigger}" data-story-choice="{index}" style="cursor:pointer;">
<rect x="36" y="{y}" width="528" height="66" rx="12" fill="{accent}"/>
{text_nodes(choice['label'], 58, y + 44, 32, '#FFFFFF', '700')}
</g>''')
        if not node["choices"]:
            trigger = f"{prefix}_restart_{identifier}"
            leave.append(trigger + ".click")
            buttons.append(f'''<g id="{trigger}" data-story-restart="{identifier}" style="cursor:pointer;">
<rect x="36" y="510" width="528" height="66" rx="12" fill="{accent}"/>
{text_nodes(['回到起点，再走一条路'], 118, 554, 30, '#FFFFFF', '700')}
</g>''')
        enter_set = f'<set attributeName="display" to="inline" begin="{enter}" fill="freeze"/>' if enter else ""
        panels.append(f'''<g id="{prefix}_node_{identifier}" data-story-node="{identifier}" display="{visible}" style="display:{visible};">
{enter_set}
<set attributeName="display" to="none" begin="{';'.join(leave)}" fill="freeze"/>
<rect width="600" height="640" rx="20" fill="{background}"/>
<path d="M36 34H106" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>
{text_nodes(node['title'], 36, 90, 36, '#27383F', '700')}
{text_nodes(node['body'], 36, 200, 34, '#27383F', spacing=44)}
{''.join(buttons)}
</g>''')
    return f'''<section style="margin:22px 0;line-height:0;">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 640" width="100%" style="display:block;width:100%;height:auto;" data-component="wechat-svg-story-branches" role="group" aria-label="选择不同路径阅读故事">
<desc>点击选项继续下一步，在结局处可以回到起点。</desc>
{''.join(panels)}
</svg></section>'''


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>多步分支故事</title><body style="margin:0;background:#F5F3ED;font-family:system-ui,sans-serif;color:#27383F;">
<main style="max-width:600px;margin:24px auto;padding:16px;"><h1 style="font-size:24px;">多步分支故事</h1><p style="line-height:1.8;">先选一条路，再继续选择。到达结局后可以重新开始。</p>{fragment}</main></body></html>'''


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
        prefix = "story_" + uuid.uuid4().hex
        fragment = render(config, prefix)
        write_outputs(targets, [fragment] + ([preview(fragment)] if args.preview_out else []), args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"files": [str(path.resolve()) for path in targets], "canvas": [600, 640],
                      "instance": prefix, "nodes": len(config["nodes"]), "start": config["start"],
                      "verification": "generated; browser/editor/phone checks pending"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
