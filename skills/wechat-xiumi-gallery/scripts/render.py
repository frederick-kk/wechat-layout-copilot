"""Render an ordered image gallery as responsive HTML or a click-through SVG."""

import argparse
import base64
import html
import json
import math
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


THEME = {
    "accent": "#BD652E",
    "text": "#352D25",
    "muted": "#826B54",
    "surface": "#FFF8EE",
    "border": "#DCC7B0",
}
INVALID_XML_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def raster_data_uri(path):
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("图片须为 PNG、JPEG、GIF 或 WebP 栅格文件")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def character_width(character):
    if unicodedata.category(character) in {"Mn", "Me"} or character == "\u200d":
        return 0
    if unicodedata.east_asian_width(character) in {"F", "W"}:
        return 1
    if character in "ilI.,;:!'| `":
        return 0.4
    if character in "WM@#%&":
        return 1
    if character.isascii():
        return 0.8
    return 1


def caption_lines(value):
    lines = []
    for paragraph in value.split("\n"):
        line = ""
        width = 0
        for character in paragraph:
            advance = character_width(character)
            if line and width + advance > 15:
                lines.append(line)
                line = ""
                width = 0
            line += character
            width += advance
        lines.append(line)
    return lines if value else []


def load_spec(path, requested_mode):
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict):
        raise ValueError("输入应为包含 images 的 JSON 对象")
    mode = requested_mode or spec.get("mode", "scroll")
    if not isinstance(mode, str) or mode not in {"scroll", "click"}:
        raise ValueError("mode 可选 scroll 或 click")
    fit = spec.get("fit", "contain")
    if not isinstance(fit, str) or fit not in {"contain", "cover"}:
        raise ValueError("fit 可选 contain（完整留边）或 cover（裁切铺满）")
    ratio = spec.get("aspect_ratio", [16, 9])
    try:
        valid_ratio = (isinstance(ratio, list) and len(ratio) == 2
                       and all(not isinstance(value, bool)
                               and isinstance(value, (int, float))
                               and math.isfinite(value) and value > 0
                               for value in ratio)
                       and 0 < 600 * ratio[1] / ratio[0] < math.inf
                       and 0 < 100 * ratio[1] / ratio[0] < math.inf)
    except (OverflowError, ZeroDivisionError):
        valid_ratio = False
    if not valid_ratio:
        raise ValueError("aspect_ratio 应为两个大于0的数字，例如 [16, 9]")
    theme = dict(THEME)
    provided_theme = spec.get("theme", {})
    if not isinstance(provided_theme, dict):
        raise ValueError("theme 应为颜色对象")
    for name, value in provided_theme.items():
        if name not in theme or not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"theme.{name} 请使用支持的名称和六位 HEX 色值")
        theme[name] = value.upper()
    items = spec.get("images")
    if not isinstance(items, list) or not items:
        raise ValueError("请按顺序提供非空 images 列表")
    images = []
    local_inputs = []
    missing_hosted = []
    remote_preview = []
    issues = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            issues.append(f"第{index}张图片应为对象")
            continue
        if not isinstance(item.get("src"), str) or not item["src"].strip():
            issues.append(f"第{index}张图片需要 src")
            continue
        if not isinstance(item.get("alt"), str) or not item["alt"].strip():
            issues.append(f"第{index}张图片需要简短 alt 说明")
            continue
        caption = item.get("caption", "")
        if not isinstance(caption, str):
            issues.append(f"第{index}张图片的 caption 应为文字")
            continue
        invalid_text = False
        for field in ("src", "alt", "caption", "hosted_src"):
            value = item.get(field, "")
            invalid = INVALID_XML_CHARACTER.search(value) if isinstance(value, str) else None
            if invalid:
                codepoint = f"U+{ord(invalid.group()):04X}"
                issues.append(f"第{index}张图片的 {field} 含 XML 不支持的字符 {codepoint}，请移除后重试")
                invalid_text = True
        if invalid_text:
            continue
        lines = caption_lines(caption)
        if mode == "click" and len(lines) > 3:
            issues.append(f"第{index}张图注排成{len(lines)}行，点击图集最多容纳3行，请提供精简图注或改用 scroll")
            continue
        hosted = item.get("hosted_src")
        if hosted is not None and not https_url(hosted):
            issues.append(f"第{index}张图片的 hosted_src 需要完整 HTTPS 地址")
            continue
        source = item["src"]
        if https_url(source):
            preview_source = source
            output_source = hosted or source
            remote_preview.append(index)
        else:
            parsed = urlparse(source)
            if parsed.scheme and not re.match(r"^[a-zA-Z]:[\\/]", source):
                issues.append(f"第{index}张图片的 src 需要本地路径或完整 HTTPS 地址")
                continue
            local = Path(source)
            if not local.is_absolute():
                local = path.parent / local
            local = local.resolve()
            try:
                preview_source = raster_data_uri(local)
            except (OSError, ValueError) as error:
                issues.append(f"第{index}张图片无法读取。{error}")
                continue
            local_inputs.append(local)
            output_source = hosted or preview_source
            if not hosted:
                missing_hosted.append(index)
        images.append({"src": output_source, "preview_src": preview_source,
                       "alt": item["alt"], "caption": caption, "lines": lines})
    if issues:
        raise ValueError("\n".join(issues))
    return {"mode": mode, "fit": fit, "ratio": ratio, "theme": theme,
            "images": images, "local_inputs": local_inputs,
            "missing_hosted": missing_hosted, "remote_preview": remote_preview}


def scroll_gallery(spec, source_field):
    theme = spec["theme"]
    padding = 100 * spec["ratio"][1] / spec["ratio"][0]
    card_width = "88%" if len(spec["images"]) > 1 else "100%"
    card_margin = "12px" if len(spec["images"]) > 1 else "0"
    cards = []
    for index, image in enumerate(spec["images"], 1):
        caption = html.escape(image["caption"]).replace("\n", "<br>")
        caption_html = ""
        if caption:
            caption_html = (
                '<p style="margin:9px 0 0;white-space:normal;font-size:16px;'
                f'line-height:1.65;color:{theme["text"]};">{caption}</p>'
            )
        cards.append(f'''<section data-gallery-slide="{index}" style="display:inline-block;vertical-align:top;width:{card_width};margin-right:{card_margin};white-space:normal;scroll-snap-align:start;box-sizing:border-box;">
  <section style="position:relative;height:0;padding-top:{padding:g}%;overflow:hidden;background-color:{theme['surface']};border:1px solid {theme['border']};box-sizing:border-box;">
    <img src="{html.escape(image[source_field], quote=True)}" alt="{html.escape(image['alt'], quote=True)}" style="position:absolute;inset:0;display:block;width:100%;height:100%;object-fit:{spec['fit']};" />
  </section>
  {caption_html}
</section>''')
    hint = f"左右滑动查看，共 {len(cards)} 张" if len(cards) > 1 else "共 1 张图片"
    return f'''<section data-component="wechat-html-scroll-gallery" style="margin:22px 0;font-family:system-ui,sans-serif;">
<p style="margin:0 0 8px;font-size:13px;line-height:1.65;color:{theme['muted']};">{hint}</p>
<section role="region" aria-label="左右滑动查看图片" tabindex="0" style="overflow-x:auto;white-space:nowrap;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:8px;">{''.join(cards)}</section>
</section>'''


def click_gallery(spec, source_field):
    theme = spec["theme"]
    image_height = 600 * spec["ratio"][1] / spec["ratio"][0]
    maximum_lines = max(len(image["lines"]) for image in spec["images"])
    caption_height = 30 + maximum_lines * 44 if maximum_lines else 0
    height = image_height + caption_height
    preserve = "xMidYMid meet" if spec["fit"] == "contain" else "xMidYMid slice"
    slides = []
    for index in range(len(spec["images"]) - 1, -1, -1):
        image = spec["images"][index]
        text_nodes = []
        for line_index, line in enumerate(image["lines"]):
            y = image_height + 48 + line_index * 44
            text_nodes.append(f'<text x="24" y="{y:g}" fill="{theme["text"]}" font-size="36" font-family="sans-serif" xml:space="preserve" pointer-events="none">{html.escape(line)}</text>')
        transition = ""
        if index < len(spec["images"]) - 1:
            transition = f'''<animateTransform attributeName="transform" type="translate" values="0 0;-600 0" begin="click" dur="0.35s" fill="freeze" restart="never" />
<rect width="600" height="{height:g}" fill="#000000" fill-opacity="0" pointer-events="all" data-gallery-trigger="tap">
  <animate attributeName="width" begin="click" from="600" to="0" dur="0.001s" fill="freeze" restart="never" />
</rect>'''
        slides.append(f'''<g data-gallery-slide="{index + 1}">
<rect width="600" height="{height:g}" fill="{theme['surface']}" pointer-events="none" />
<image href="{html.escape(image[source_field], quote=True)}" x="0" y="0" width="600" height="{image_height:g}" preserveAspectRatio="{preserve}" pointer-events="none"><title>{html.escape(image['alt'])}</title></image>
{''.join(text_nodes)}
{transition}
</g>''')
    hint = f"点击图片切换，共 {len(slides)} 张，最后一张停留显示" if len(slides) > 1 else "共 1 张图片"
    return f'''<section data-component="wechat-svg-click-gallery" style="margin:22px 0;font-family:system-ui,sans-serif;">
<p style="margin:0 0 8px;font-size:13px;line-height:1.65;color:{theme['muted']};">{hint}</p>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height:g}" width="100%" role="img" aria-label="按顺序点击查看图片" style="display:block;width:100%;height:auto;overflow:hidden;pointer-events:none;">
{''.join(slides)}
</svg>
</section>'''


def render(spec, source_field):
    if spec["mode"] == "scroll":
        return scroll_gallery(spec, source_field)
    return click_gallery(spec, source_field)


def preview(fragment):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>图片图集预览</title><body style="margin:0;background:#F7F5F0;color:#352D25;font-family:system-ui,sans-serif;">
<main style="box-sizing:border-box;max-width:680px;margin:24px auto;padding:24px;">
<h1 style="font-size:24px;">图片图集预览</h1>{fragment}
<p style="font-size:14px;line-height:1.7;">本页用于浏览器检查。编辑器保存和手机微信显示按实际导入结果继续核对。</p>
</main></body></html>'''


def write_outputs(outputs, overwrite, written):
    """Stage every file before committing, then restore prior files on failure."""
    staged = []
    cleanup_issues = []
    failure = None
    try:
        for path, content in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                raise IsADirectoryError(f"输出路径是文件夹，请使用文件路径。{path}")
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            record = {"path": path, "stage": Path(temporary), "backup": None,
                      "reserved": False, "installed": False, "retain_backup": False}
            staged.append(record)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)

        for record in staged:
            path = record["path"]
            if overwrite:
                if path.is_dir():
                    raise IsADirectoryError(f"输出路径已变为文件夹。{path}")
                descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".bak", dir=path.parent)
                os.close(descriptor)
                backup = Path(temporary)
                try:
                    os.replace(path, backup)
                except FileNotFoundError:
                    backup.unlink()
                except OSError:
                    backup.unlink()
                    raise
                else:
                    record["backup"] = backup
            else:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
                record["reserved"] = True
                os.close(descriptor)
            os.replace(record["stage"], path)
            record["installed"] = True
            written.append(str(path))
    except (OSError, ValueError) as error:
        failure = error
        for record in reversed(staged):
            path = record["path"]
            try:
                if record["backup"]:
                    os.replace(record["backup"], path)
                elif record["reserved"] or record["installed"]:
                    path.unlink(missing_ok=True)
                if str(path) in written:
                    written.remove(str(path))
            except OSError as rollback_error:
                record["retain_backup"] = bool(record["backup"])
                if (record["reserved"] or record["installed"]) and str(path) not in written:
                    written.append(str(path))
                recovery = f"，原文件备份保留在 {record['backup']}" if record["backup"] else ""
                cleanup_issues.append(f"恢复 {path} 时失败{recovery}。{rollback_error}")
    finally:
        for record in staged:
            temporary_files = [record["stage"]]
            if record["backup"] and not record["retain_backup"]:
                temporary_files.append(record["backup"])
            for path in temporary_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    cleanup_issues.append(f"临时文件保留在 {path}。{cleanup_error}")
    if failure:
        details = "\n".join([str(failure), *cleanup_issues])
        raise OSError(details) from failure
    return cleanup_issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--mode", choices=["scroll", "click"])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    written = []
    try:
        spec = load_spec(args.spec, args.mode)
        destinations = [args.out] + ([args.preview] if args.preview else [])
        resolved = [path.resolve() for path in destinations]
        if len(set(resolved)) != len(resolved):
            raise ValueError("片段和预览请使用不同输出文件")
        inputs = {args.spec.resolve(), *spec["local_inputs"]}
        if inputs.intersection(resolved):
            raise ValueError("输出请使用与输入 JSON、原始图片不同的路径")
        if not args.overwrite and any(path.exists() for path in destinations):
            raise ValueError("输出已存在，请换路径，或确认替换后使用 --overwrite")
        outputs = [(resolved[0], render(spec, "src"))]
        if args.preview:
            outputs.append((resolved[1], preview(render(spec, "preview_src"))))
        warnings = write_outputs(outputs, args.overwrite, written)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "needs_input", "issues": str(error).splitlines(),
                          "files_written": written}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"status": "created", "files": written, "mode": spec["mode"],
                      "images": len(spec["images"]), "fit": spec["fit"],
                      "aspect_ratio": spec["ratio"],
                      "hosted_image_urls_provided": not spec["missing_hosted"],
                      "deployment_verified": False,
                      "missing_hosted_src_for_images": spec["missing_hosted"],
                      "preview_remote_images": spec["remote_preview"],
                      "warnings": warnings,
                      "verification": "local generation; verify browser, editor save and WeChat phone behavior separately"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
