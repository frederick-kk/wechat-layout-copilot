"""Add Fred's illustration assets to stateful card demonstration SVGs.

This module decorates newly built examples. It leaves event identifiers, SMIL
timing, transparent hit areas, and the original component sources intact.
"""

import xml.etree.ElementTree as ET


SVG = "http://www.w3.org/2000/svg"


def _groups(svg, attribute):
    return [node for node in svg.iter(f"{{{SVG}}}g") if attribute in node.attrib]


def _texts(group):
    return [node for node in group if node.tag == f"{{{SVG}}}text"]


def _image(art, key, x, y, width, height, label="Fred 的创作场景"):
    source = art.get(key)
    if width / height >= 3 and key in {"idea", "studio", "launch"}:
        source = art.get("banner-" + key, source)
    if not source:
        raise ValueError(f"品牌演示缺少配图 {key}")
    image = ET.Element(f"{{{SVG}}}image", {
        "href": str(source),
        "x": str(x),
        "y": str(y),
        "width": str(width),
        "height": str(height),
        "preserveAspectRatio": "xMaxYMid slice" if key == "launch" and width / height < 1.6 else "xMidYMid slice",
        "style": "pointer-events:none;",
        "data-brand-art": key,
    })
    ET.SubElement(image, f"{{{SVG}}}title").text = label
    return image


def _insert_before(parent, reference, child):
    parent.insert(list(parent).index(reference), child)


def _flip(svg, art, uid):
    for face in _groups(svg, "data-face"):
        key = "idea" if face.get("data-face") == "front" else "launch"
        face.append(_image(art, key, -226, 40, 452, 104))


def _switch(svg, art, uid):
    keys = ["idea", "studio", "launch"]
    for panel in _groups(svg, "data-switch-panel"):
        index = int(panel.get("data-switch-panel"))
        panel.append(_image(art, keys[index % len(keys)], 36, 216, 528, 104))


def _peel(svg, art, uid):
    keys = ["idea", "studio", "launch"]
    for panel in _groups(svg, "data-peel-layer"):
        index = int(panel.get("data-peel-layer"))
        panel.append(_image(art, keys[index % len(keys)], 36, 216, 528, 104))


def _reveal(svg, art, uid):
    answer = _groups(svg, "data-reveal-layer")[0]
    _insert_before(svg, answer, _image(art, "before", 24, 178, 552, 158))
    answer.append(_image(art, "studio", 24, 188, 552, 148))


def _hold(svg, art, uid):
    keys = ["idea", "studio", "launch"]
    for card in _groups(svg, "data-hold-card"):
        index = int(card.get("data-hold-card"))
        card.append(_image(art, keys[index % len(keys)], 30, 250, 540, 100))


def _press(svg, art, uid):
    cover = next(node for node in svg
                 if node.tag == f"{{{SVG}}}rect" and node.get("y") == "100")
    position = list(svg).index(cover) + 1
    svg.insert(position, _image(art, "before", 22, 102, 556, 256))
    svg.insert(position + 1, ET.Element(f"{{{SVG}}}rect", {
        "x": "80", "y": "182", "width": "440", "height": "66",
        "rx": "12", "fill": "#56331F", "fill-opacity": "0.94",
        "style": "pointer-events:none;",
    }))
    detail = _groups(svg, "data-press-fade")[0]
    copy = ["先行动，再收集反馈", "准备一份材料", "跑通完整流程", "让真实的人看"]
    baselines = [150, 210, 250, 290]
    for index, text in enumerate(_texts(detail)):
        if index < len(copy):
            text.text = copy[index]
            text.set("x", "42")
            text.set("y", str(baselines[index]))
            text.set("font-size", "26" if index == 0 else "29")
    detail.append(_image(art, "launch", 330, 140, 230, 204))


def _quiz(svg, art, uid):
    feedbacks = _groups(svg, "data-quiz-feedback")
    _insert_before(svg, feedbacks[0], _image(art, "idea", 36, 427, 528, 100))
    for feedback in feedbacks:
        stage = next(node for node in feedback if node.tag == f"{{{SVG}}}g")
        text = _texts(stage)
        last_y = max(float(node.get("y", "0")) for node in text)
        y = max(355, last_y + 25)
        key = "launch" if any(node.text == "答对啦" for node in text) else "idea"
        stage.append(_image(art, key, 36, y, 528, 490 - y))


def _story(svg, art, uid):
    scenes = {
        "start": "idea",
        "practice": "studio",
        "task": "studio",
        "delivery": "launch",
        "materials": "idea",
    }
    for panel in _groups(svg, "data-story-node"):
        body = [node for node in _texts(panel) if float(node.get("y", "0")) >= 180]
        for index, node in enumerate(body):
            node.set("y", str(150 + index * 38))
            node.set("font-size", "30")
        terminal = any("data-story-restart" in node.attrib for node in panel)
        height = 214 if terminal else 92
        y = 266 if terminal else 250
        key = scenes.get(panel.get("data-story-node"), "studio")
        panel.append(_image(art, key, 36, y, 528, height))


def _pull(svg, art, uid):
    message = _groups(svg, "data-pull-message")[0]
    message.append(_image(art, "studio", 230, 322, 290, 70))
    cover = next(node for node in svg
                 if node.tag == f"{{{SVG}}}rect" and node.get("width") == "190")
    index = list(svg).index(cover)
    svg.insert(index + 1, _image(art, "avatar", 24, 151, 132, 150, "Fred 的橙帽头像"))
    for text in _texts(svg):
        if text.get("x") == "35" and text.get("y") == "270":
            text.set("x", "45")
            text.set("y", "365")
            text.set("font-size", "34")


def _timeline(svg, art, uid):
    keys = ["idea", "studio", "launch"]
    for step in _groups(svg, "data-timeline-step"):
        index = int(step.get("data-timeline-step"))
        y = 145 + index * 120
        text = _texts(step)
        for position, node in enumerate(text):
            node.set("font-size", "28" if position == 1 else "24")
        step.append(_image(art, keys[index % len(keys)], 450, y - 29, 100, 88))


def _accordion(svg, art, uid):
    keys = ["idea", "studio", "launch"]
    for body in _groups(svg, "data-panel-body"):
        index = int(body.get("data-panel-body"))
        text = _texts(body)
        for line, node in enumerate(text):
            node.set("y", str(226 + line * 38))
            node.set("font-size", "29")
        y = 226 + max(0, len(text) - 1) * 38 + 25
        # Body visibility is paused while panels resize. The art therefore
        # appears only inside the fully expanded, 330px-wide panel.
        body.append(_image(art, keys[index % len(keys)], 24, y, 282, 438 - y))


HANDLERS = {
    "flip-card": _flip,
    "switch": _switch,
    "layer-peel": _peel,
    "click-reveal": _reveal,
    "hold-cards": _hold,
    "press-reveal": _press,
    "quiz": _quiz,
    "story-branches": _story,
    "pull-tab": _pull,
    "timeline": _timeline,
    "accordion-panels": _accordion,
}


def augment(slug, svg, art, uid):
    """Decorate an owned demonstration SVG and report whether it was handled."""
    name = slug.removeprefix("wechat-svg-")
    handler = HANDLERS.get(name)
    if handler is None:
        return False
    handler(svg, art, uid)
    return True
