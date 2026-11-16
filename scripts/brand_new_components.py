"""Apply shared artwork to explicitly marked SVG and native HTML slots."""

import html
from html.parser import HTMLParser
import math
import re
import xml.etree.ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
LABELS = {
    "avatar": "Fred 橙帽头像",
    "paper": "白色折痕纸纹",
    "studio": "创作工作台",
    "idea": "灵感与起步",
    "launch": "作品完成",
}


def slot_number(element, name, positive=False):
    value = float(element.get("data-" + name, "0"))
    if not math.isfinite(value) or positive and value <= 0:
        raise ValueError(f"插画槽的{name}需要有效数字")
    return value


def augment_svg(svg, artwork):
    """Fill marked illustration slots while retaining interaction children."""
    for group in svg.iter():
        key = group.get("data-artwork-slot")
        if key is None:
            continue
        if key not in LABELS or key not in artwork:
            raise ValueError("插画槽素材不可用 " + key)
        x, y = slot_number(group, "x"), slot_number(group, "y")
        width = slot_number(group, "width", positive=True)
        height = slot_number(group, "height", positive=True)
        for child in list(group):
            if child.get("data-artwork-placeholder") is not None:
                group.remove(child)
        image = ET.Element("{" + SVG + "}image", {
            "href": artwork[key], "x": str(x), "y": str(y),
            "width": str(width), "height": str(height),
            "preserveAspectRatio": "xMidYMid slice", "pointer-events": "none",
            "data-brand-image": key, "aria-label": LABELS[key],
        })
        group.insert(0, image)
        group.set("data-artwork-rendered", key)
    return svg


class ArtworkHTML(HTMLParser):
    def __init__(self, artwork):
        super().__init__(convert_charrefs=False)
        self.artwork = artwork
        self.parts = []

    def start(self, tag, attributes, closed=False):
        values = dict(attributes)
        key = values.get("data-brand-artwork")
        after = ""
        if key is not None:
            if key not in LABELS or key not in self.artwork:
                raise ValueError("HTML插画槽素材不可用 " + key)
            source = self.artwork[key]
            if tag in {"img", "image"}:
                values["src" if tag == "img" else "href"] = source
                values.setdefault("alt" if tag == "img" else "aria-label", LABELS[key])
            elif key == "paper":
                style = values.get("style", "").rstrip().rstrip(";")
                values["style"] = style + f";background-image:url('{source}');background-repeat:repeat"
            else:
                after = (f'<img src="{html.escape(source, quote=True)}" '
                         f'alt="{html.escape(LABELS[key], quote=True)}" '
                         'style="display:block;width:100%;height:auto;">')
        rendered = []
        for name, value in values.items():
            rendered.append(name if value is None else f'{name}="{html.escape(value, quote=True)}"')
        self.parts.append("<" + tag + (" " + " ".join(rendered) if rendered else "") + (" />" if closed else ">"))
        if after:
            self.parts.append(after)

    def handle_starttag(self, tag, attrs):
        self.start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self.start(tag, attrs, closed=True)

    def handle_endtag(self, tag):
        self.parts.append("</" + tag + ">")

    def handle_data(self, value):
        self.parts.append(value)

    def handle_entityref(self, name):
        self.parts.append("&" + name + ";")

    def handle_charref(self, name):
        self.parts.append("&#" + name + ";")

    def handle_comment(self, value):
        self.parts.append("<!--" + value + "-->")


def html_demo(fragment, artwork):
    if re.search(r"<\s*(?:script|html|head|body)\b", fragment, re.I):
        raise ValueError("原生HTML组件需要可独立嵌入的无脚本正文片段")
    parser = ArtworkHTML(artwork)
    parser.feed(fragment)
    parser.close()
    heading = (
        '<header class="brand-heading"><img src="' + html.escape(artwork["avatar"], quote=True) +
        '" alt="Fred 橙帽头像"><div><b>小鱼 Fred</b><small>把想法，做成自己的作品。</small></div></header>'
    )
    paper = html.escape(artwork["paper"], quote=True)
    return (f'<div data-brand-html="true" style="background-image:url(\'{paper}\');background-repeat:repeat;">'
            + heading + '<section style="padding:12px;">' + "".join(parser.parts) + '</section></div>')
