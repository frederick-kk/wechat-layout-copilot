"""从本次原生公众号名片生成有界的头像跳转组件。"""

from __future__ import annotations

import argparse
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit


class CardReader(HTMLParser):
    def __init__(self, markup: str):
        super().__init__(convert_charrefs=True)
        self.cards: list[dict] = []
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "mp-common-profile":
            names = [name for name, _ in attrs]
            self.cards.append({
                "attrs": dict(attrs),
                "opening": self.get_starttag_text(),
                "duplicate_fields": len(names) != len(set(names)),
            })

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def positive_size(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("头像尺寸需要为正整数")
    return number


def needs_input(missing: list[str], issues: list[str]) -> int:
    print(json.dumps({"status": "needs_input", "missing": missing, "issues": issues}, ensure_ascii=False, indent=2))
    return 2


def choose_card(cards: list[dict], account_id: str | None) -> tuple[dict | None, list[str]]:
    if account_id:
        cards = [card for card in cards if card["attrs"].get("data-id") == account_id]
        if not cards:
            return None, ["当前材料中未找到指定账号的原生名片，请核对选择或补充名片。"]
    if not cards:
        return None, []
    identities = {
        tuple(card["attrs"].get(field) for field in ("data-id", "data-nickname", "data-headimg", "data-signature"))
        for card in cards
    }
    if len(identities) != 1:
        return None, ["材料中有多个账号或不一致的账号资料，请保留一份正确名片，或用 --account-id 选择目标。"]
    return cards[0], []


def avatar_url(value: str) -> str | None:
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if any(character.isspace() or character in '<>"\'\\' for character in value):
        return None
    return value


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card-html", type=Path, help="本次提供的真实原生公众号名片 HTML")
    parser.add_argument("--out", type=Path, required=True, help="生成的组件 HTML 文件")
    parser.add_argument("--account-id", help="源文件有多个账号时选择已有真实 data-id")
    parser.add_argument("--size", type=positive_size, default=120, help="头像边长，单位 px，默认 120")
    parser.add_argument("--caption", default="点击头像查看公众号", help="头像下方提示文字，空字符串可隐藏")
    args = parser.parse_args()

    source = args.card_html.expanduser().resolve() if args.card_html else None
    if source is None or not source.is_file():
        return needs_input(["原生公众号名片 HTML 文件"], ["请从目标账号的实际名片取得 mp-common-profile 组件。"])
    output = args.out.expanduser().resolve()
    if source == output:
        return needs_input([], ["组件输出文件需要使用另一个路径，以保留原生名片材料。"])
    try:
        cards = CardReader(source.read_text(encoding="utf-8-sig")).cards
    except (OSError, UnicodeError, ValueError):
        return needs_input(["可读取的 UTF-8 名片 HTML"], ["当前文件读取失败，请重新导出名片。"])
    card, issues = choose_card(cards, args.account_id)
    if card is None:
        missing = ["目标账号的原生 mp-common-profile 名片"] if not cards else ["目标账号选择或一致的账号资料"]
        return needs_input(missing, issues)

    attrs = card["attrs"]
    labels = {
        "data-id": "公众号身份 data-id",
        "data-nickname": "公众号名称 data-nickname",
        "data-headimg": "头像地址 data-headimg",
        "data-pluginname": "原生组件标识 data-pluginname",
    }
    missing = [label for field, label in labels.items() if not (attrs.get(field) or "").strip()]
    if card["duplicate_fields"]:
        issues.append("名片含重复字段，请重新取得完整的原生名片。")
    if attrs.get("data-pluginname") and attrs["data-pluginname"] != "mpprofile":
        issues.append("名片组件标识与 mpprofile 不一致，请核对来源。")
    if any(name.startswith("on") for name in attrs):
        issues.append("名片带有事件处理属性，请从编辑器重新取得原生组件。")
    try:
        image = avatar_url(attrs.get("data-headimg") or "")
    except ValueError:
        image = None
    if attrs.get("data-headimg") and image is None:
        issues.append("头像需要使用当前可用的 HTTP 或 HTTPS 地址，请核对原生名片头像。")
    if missing or issues:
        return needs_input(missing, issues)

    opening = card["opening"].rstrip()
    if opening.endswith("/>"):
        opening = opening[:-2] + ">"
    native_card = opening + "</mp-common-profile>"
    label = escape(attrs["data-nickname"].strip())
    image_attribute = escape(image, quote=True)
    caption = escape(args.caption)
    caption_html = f'<p style="margin:6px 0 0;font-size:13px;line-height:1.7;">{caption}</p>' if caption else ""
    markup = (
        '<section style="margin:12px 0;text-align:center;">\n'
        f'<section style="display:inline-block;width:{args.size}px;height:{args.size}px;overflow:hidden;font-size:0;line-height:0;'
        'vertical-align:middle;background-position:center;background-repeat:no-repeat;background-size:cover;'
        f'background-image:url(&quot;{image_attribute}&quot;);">\n'
        '<section style="overflow:hidden;opacity:0;transform:scale(80);-webkit-transform:scale(80);'
        'transform-origin:center center;-webkit-transform-origin:center center;width:100%;height:100%;">\n'
        f'{native_card}\n</section>\n</section>\n'
        f'<p style="margin:8px 0 0;font-size:15px;font-weight:700;line-height:1.7;">{label}</p>\n'
        f'{caption_html}\n</section>\n'
    )
    try:
        atomic_write(output, markup)
    except OSError:
        print(json.dumps({"status": "write_failed", "issues": ["组件文件保存失败，请检查目标路径和写入权限。"]}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "status": "rendered",
        "output": str(output),
        "nickname": attrs["data-nickname"].strip(),
        "avatar_size_px": args.size,
        "native_attributes_preserved": True,
        "avatar_matches_native_card": True,
        "verification": "已从输入名片读取字段并生成组件，编辑器保存和手机跳转待本次实际核对。",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

