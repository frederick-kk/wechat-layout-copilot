"""Render a small inline SVG drawline component using only Python's stdlib."""

import argparse
import json
import re
from pathlib import Path


def hex_color(value):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("颜色请使用六位十六进制值，例如 #D97706")
    return value.upper()


def positive_number(value):
    number = float(value)
    if not 0 < number < 10000:
        raise argparse.ArgumentTypeError("数值须大于0且小于10000")
    return number


def repeat_count(value):
    if value == "loop":
        return "indefinite"
    if not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError("播放次数请填写正整数，或 loop")
    return str(int(value))


def component(args):
    padding = max(16, args.stroke_width * 2)
    y = args.height / 2
    end = args.width - padding
    return f'''<section style="margin:16px 0;padding:0;line-height:0;" data-component="wechat-svg-drawline">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {args.width:g} {args.height:g}" width="100%" style="display:block;width:100%;height:auto;" role="img" aria-label="描边分隔线">
  <desc>线条从左向右描画，完成后保持完整状态。</desc>
  <path d="M {padding:g} {y:g} H {end:g}" fill="none" stroke="{args.color}" stroke-width="{args.stroke_width:g}" stroke-linecap="round" pathLength="100" stroke-dasharray="100 100" stroke-dashoffset="0">
    <animate attributeName="stroke-dashoffset" values="100;0;0" keyTimes="0;0.6;1" dur="{args.duration:g}s" begin="0s" repeatCount="{args.repeat}" fill="freeze" />
  </path>
</svg>
</section>
'''


def preview(fragment):
    return f'''<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SVG描边分隔线示例</title>
<body style="margin:0;background:#F7F5F0;color:#1F2937;font-family:system-ui,sans-serif;">
<main style="max-width:640px;margin:40px auto;padding:24px;">
  <h1 style="font-size:24px;">SVG描边分隔线</h1>
  <p style="font-size:16px;line-height:1.8;">观察线条从左向右画出。刷新页面可再次观察单次播放。</p>
  {fragment}
  <p style="font-size:16px;line-height:1.8;">这段正文保留为普通HTML文字，方便编辑和复制。</p>
</main>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="用于组装正文的HTML片段")
    parser.add_argument("--preview-out", type=Path, help="可独立打开的HTML预览")
    parser.add_argument("--color", type=hex_color, default="#D97706")
    parser.add_argument("--width", type=positive_number, default=600)
    parser.add_argument("--height", type=positive_number, default=48)
    parser.add_argument("--stroke-width", type=positive_number, default=3)
    parser.add_argument("--duration", type=positive_number, default=2.8)
    parser.add_argument("--repeat", type=repeat_count, default="1")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.width <= max(16, args.stroke_width * 2) * 2:
        parser.error("画布宽度不足，请增加 --width 或减小 --stroke-width")
    if args.height <= args.stroke_width * 2:
        parser.error("画布高度不足，请增加 --height 或减小 --stroke-width")
    targets = [args.out] + ([args.preview_out] if args.preview_out else [])
    if len({path.resolve() for path in targets}) != len(targets):
        parser.error("片段和预览须使用不同输出文件")
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error("输出已存在，请换路径，或确认替换后使用 --overwrite")
    fragment = component(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(fragment, encoding="utf-8")
    if args.preview_out:
        args.preview_out.parent.mkdir(parents=True, exist_ok=True)
        args.preview_out.write_text(preview(fragment), encoding="utf-8")
    print(json.dumps({"files": [str(path.resolve()) for path in targets],
                      "color": args.color, "duration_seconds": args.duration,
                      "repeat_count": args.repeat}, ensure_ascii=False))


if __name__ == "__main__":
    main()
