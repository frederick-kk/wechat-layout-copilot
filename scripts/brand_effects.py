"""Add Fred's image artwork to existing SVG component demonstrations.

The caller supplies theme colors, a paper surface, and image paths relative to
the resulting demonstration.  This module preserves the existing event anchors
and animation elements while replacing their presentation artwork.
"""

import copy
import re
import xml.etree.ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
INK = "#30271F"
ORANGE = "#A64C24"
PAPER = "#FFFCF5"
GOLD = "#C6AA7B"
ANIMATION_TAGS = {"animate", "animateTransform", "animateMotion", "set"}


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _element(name, **attributes):
    return ET.Element("{" + SVG + "}" + name, {key: str(value) for key, value in attributes.items()})


def _asset(art, name):
    value = art.get(name) or art.get("studio") or art.get("avatar")
    if not value:
        raise ValueError("Missing artwork asset " + name)
    return value


def _banner(art, name):
    return art.get("banner-" + name) or _asset(art, name)


def _find(root, name, value=None):
    return next((node for node in root.iter() if name in node.attrib and (value is None or node.get(name) == value)), None)


def _find_all(root, name):
    return [node for node in root.iter() if name in node.attrib]


def _image(source, x, y, width, height):
    return _element("image", href=source, x=x, y=y, width=width, height=height,
                    preserveAspectRatio="xMidYMid slice", style="pointer-events:none;")


def _clipped_image(parent, source, frame, identifier, image_frame=None, radius=0, circle=False):
    x, y, width, height = frame
    definitions = _element("defs")
    clip = _element("clipPath", id=identifier, clipPathUnits="userSpaceOnUse")
    if circle:
        clip.append(_element("circle", cx=x + width / 2, cy=y + height / 2, r=min(width, height) / 2))
    else:
        clip.append(_element("rect", x=x, y=y, width=width, height=height, rx=radius))
    definitions.append(clip)
    parent.append(definitions)
    image = _image(source, *(image_frame or frame))
    image.set("clip-path", "url(#" + identifier + ")")
    parent.append(image)
    return image


def _position_text(node, x, y, size, fill=INK):
    node.set("x", str(x))
    node.set("y", str(y))
    node.set("font-size", str(size))
    node.set("fill", fill)


def _insert_before(parent, anchor, node):
    parent.insert(list(parent).index(anchor), node)


def _blinds(svg, art, uid):
    slats = _find_all(svg, "data-slat")
    if not slats:
        return False
    first_cover = next(child for child in svg if slats[0] in list(child))
    direct_text = [child for child in svg if _tag(child) == "text"]
    revealed = _element("g", **{"data-brand-art": "blinds-revealed"})
    _clipped_image(revealed, _banner(art, "studio"), (32, 100, 536, 190), uid + "_revealed", radius=10)
    revealed.append(_element("rect", x=33, y=290, width=534, height=157, fill=PAPER))
    _insert_before(svg, first_cover, revealed)
    # The existing body remains native and is brought above the image surface.
    for index, node in enumerate(direct_text[1:]):
        svg.remove(node)
        _position_text(node, 58, 326 if index == 0 else 340 + index * 30,
                       28 if index == 0 else 25, ORANGE if index == 0 else INK)
        _insert_before(svg, first_cover, node)
    for index, slat in enumerate(slats):
        strip = _element("g", **{"data-brand-art": "blind-strip"})
        _clipped_image(strip, _asset(art, "idea"), (0, 0, 536, 58), uid + "_slat_" + str(index),
                       (0, -index * 58, 536, 348))
        # The strip stays in the existing scale-animated group.
        slat.append(strip)
        slat.append(_element("path", d="M0 57H536", stroke=PAPER, **{"stroke-width": 2}))
    return True


def _window(svg, art, uid):
    panels = _find_all(svg, "data-window-panel")
    if len(panels) != 2:
        return False
    revealed = _element("g", **{"data-brand-art": "open-window-scene"})
    _clipped_image(revealed, _banner(art, "studio"), (0, 0, 600, 218), uid + "_window_inside")
    revealed.append(_element("rect", x=0, y=218, width=600, height=132, fill=PAPER))
    _insert_before(svg, panels[0], revealed)
    direct_text = [child for child in svg if _tag(child) == "text"]
    for index, node in enumerate(direct_text):
        svg.remove(node)
        _position_text(node, 36, 249 if index == 0 else 257 + index * 29,
                       28 if index == 0 else 25, ORANGE if index == 0 else INK)
        _insert_before(svg, panels[0], node)
    for index, panel in enumerate(panels):
        picture = _element("g", **{"data-brand-art": "window-half"})
        _clipped_image(picture, _asset(art, "launch"), (index * 300, 0, 300, 350),
                       uid + "_window_half_" + str(index), (0, 0, 600, 350))
        panel.insert(3, picture)
        for path in panel:
            if _tag(path) == "path":
                path.set("stroke", GOLD)
                path.set("opacity", "0.8")
    cover = _find(svg, "data-window-cover-label")
    if cover is not None:
        cover.insert(2, _element("rect", x=130, y=105, width=340, height=62, rx=10,
                                 fill=PAPER, **{"fill-opacity": ".94"}))
        for node in cover:
            if _tag(node) == "text":
                node.set("fill", ORANGE)
    return True


def _wipe_scene(original, source, uid):
    scene = _element("g", **{"data-brand-art": "wipe-scene"})
    _clipped_image(scene, source, (0, 80, 600, 270), uid + "_photo")
    scene.append(_element("rect", x=0, y=350, width=600, height=120, fill=PAPER))
    texts = [copy.deepcopy(node) for node in original if _tag(node) == "text"]
    label = next((node for node in texts if float(node.get("y", "0")) < 140), None)
    body = [node for node in texts if node is not label]
    for index, node in enumerate(body):
        body_step = min(32, 48 / max(1, len(body) - 2))
        _position_text(node, 32, 378 if index == 0 else 416 + (index - 1) * body_step,
                       28 if index == 0 else 25, ORANGE if index == 0 else INK)
        scene.append(node)
    if label is not None:
        scene.append(_element("rect", x=20, y=92, width=200, height=44, rx=9, fill=ORANGE))
        _position_text(label, 34, 123, 26, "#FFFFFF")
        scene.append(label)
    return scene


def _wipe(svg, art, uid):
    viewport = _find(svg, "data-wipe-layer", "after")
    after = _find(svg, "data-wipe-content", "after")
    if viewport is None or after is None:
        return False
    children = list(svg)
    start = next(index for index, node in enumerate(children)
                 if _tag(node) == "rect" and node.get("y") == "80")
    before = children[start:children.index(viewport)]
    for node in before:
        svg.remove(node)
    svg.insert(start, _wipe_scene(before, _asset(art, "before"), uid + "_before"))
    after_visuals = [node for node in after if _tag(node) not in ANIMATION_TAGS]
    for node in after_visuals:
        after.remove(node)
    after.append(_wipe_scene(after_visuals, _asset(art, "studio"), uid + "_after"))
    return True


def _hotspots(svg, art, uid):
    hotspots = _find_all(svg, "data-hotspot")
    if not hotspots:
        return False
    stage = _element("g", **{"data-brand-art": "hotspot-overview"})
    _clipped_image(stage, _asset(art, "studio"), (24, 164, 552, 400), uid + "_overview", radius=12)
    _insert_before(svg, hotspots[0], stage)
    scenes = ["idea", "studio", "launch"]
    for index, detail in enumerate(_find_all(svg, "data-hotspot-fade")):
        native = [node for node in detail if _tag(node) == "text"]
        body_end = max((float(node.get("y", "0")) for node in native), default=290)
        y = max(330, body_end + 26)
        height = max(48, min(150, 480 - y))
        image = _element("g", **{"data-brand-art": "hotspot-detail"})
        _clipped_image(image, _banner(art, scenes[index % 3]), (40, y, 520, height),
                       uid + "_detail_" + str(index), radius=10)
        back = next((node for node in detail if "data-hotspot-back" in node.attrib), None)
        if back is None:
            detail.append(image)
        else:
            _insert_before(detail, back, image)
    return True


def _zoom(svg, art, uid):
    viewport = _find(svg, "data-zoom-viewport")
    if viewport is None:
        return False
    for node in list(viewport):
        if _tag(node) not in ANIMATION_TAGS:
            viewport.remove(node)
    viewport.append(_image(_asset(art, "studio"), 0, 0, 600, 360))
    return True


def _motion(svg, art, uid):
    traveler = _find(svg, "data-motion-traveler")
    if traveler is None:
        return False
    route = next((node for node in svg if _tag(node) == "path"), None)
    if route is not None:
        background = _element("g", **{"data-brand-art": "journey-scene"})
        background.append(_element("rect", x=24, y=115, width=552, height=220, rx=12, fill=PAPER))
        _clipped_image(background, _banner(art, "launch"), (24, 115, 552, 220),
                       uid + "_journey", (24, 145, 552, 220), radius=12)
        _insert_before(svg, route, background)
        under = copy.deepcopy(route)
        under.set("stroke", PAPER)
        under.set("stroke-width", "13")
        under.set("opacity", "1")
        _insert_before(svg, route, under)
        route.set("opacity", "1")
    for node in list(traveler):
        if _tag(node) not in ANIMATION_TAGS:
            traveler.remove(node)
        elif _tag(node) == "animateMotion":
            node.set("rotate", "0")
    traveler.append(_element("circle", r=32, fill=PAPER, stroke=ORANGE, **{"stroke-width": 2}))
    _clipped_image(traveler, _asset(art, "avatar"), (-28, -28, 56, 56),
                   uid + "_traveler", circle=True)
    return True


def _typewriter(svg, art, uid):
    letters = _find_all(svg, "data-char-index")
    if not letters:
        return False
    native_text = [node for group in letters for node in group if _tag(node) == "text"]
    last_line = max(float(node.get("y", "153")) for node in native_text)
    page = _element("g", **{"data-brand-art": "letter-page"})
    page.append(_element("rect", x=28, y=116, width=544, height=min(292, last_line - 92),
                         rx=8, fill=PAPER, stroke=GOLD, **{"stroke-width": 1}))
    _insert_before(svg, letters[0], page)
    y = max(242, last_line + 32)
    if y < 362:
        image = _element("g", **{"data-brand-art": "writing-studio"})
        _clipped_image(image, _banner(art, "idea"), (36, y, 528, 408 - y),
                       uid + "_writing_scene", radius=10)
        play = _find(svg, "data-action", "play")
        _insert_before(svg, play, image)
    return True


def _chart(svg, art, uid):
    bars = _find_all(svg, "data-chart-bar")
    if not bars:
        return False
    picture = _element("g", **{"data-brand-art": "chart-author"})
    _clipped_image(picture, _asset(art, "avatar"), (486, 16, 78, 78), uid + "_chart_author", circle=True)
    _insert_before(svg, bars[0], picture)
    heading = next((node for node in svg if _tag(node) == "text"), None)
    if heading is not None:
        heading.set("font-size", "30")
    # Data stays in the original rects and labels, including their exact values.
    for index, bar in enumerate(bars):
        rect = next((node for node in bar if _tag(node) == "rect"), None)
        if rect is not None:
            rect.set("fill", [ORANGE, "#BF784C", "#D9A777"][index % 3])
            rect.set("stroke", "#9E542F")
            rect.set("stroke-width", "1")
    return True


def _vinyl(svg, art, uid):
    rotor = _find(svg, "data-vinyl-rotor")
    if rotor is None:
        return False
    # Only the isolated disc and author label share the rotating group.
    for node in list(rotor):
        if _tag(node) not in ANIMATION_TAGS:
            rotor.remove(node)
    if art.get("record-disc"):
        _clipped_image(rotor, art["record-disc"], (-150, -150, 300, 300),
                       uid + "_record", circle=True)
    else:
        rotor.append(_element("circle", r=150, fill="#BC612F", stroke="#8F421E", **{"stroke-width": 2}))
        for radius in range(138, 65, -9):
            rotor.append(_element("circle", r=radius, fill="none", stroke="#E7B67E",
                                  **{"stroke-width": 1, "stroke-opacity": ".55"}))
    for ring in svg:
        if _tag(ring) == "circle" and ring.get("r") == "165":
            ring.set("fill", "#EBDCC3")
    rotor.append(_element("circle", r=52, fill=PAPER, stroke=GOLD, **{"stroke-width": 2}))
    _clipped_image(rotor, _asset(art, "avatar"), (-46, -46, 92, 92),
                   uid + "_record_author", circle=True)
    return True


def _puzzle(svg, art, uid):
    pieces = _find_all(svg, "data-piece-index")
    if not pieces:
        return False
    for index, piece in enumerate(pieces):
        label = next((node for node in piece if _tag(node) == "text"), None)
        native_label = copy.deepcopy(label) if label is not None else None
        for node in list(piece):
            if _tag(node) not in ANIMATION_TAGS:
                piece.remove(node)
        x, y = 176 + index % 2 * 128, 142 + index // 2 * 128
        _clipped_image(piece, _asset(art, "avatar"), (x, y, 120, 120),
                       uid + "_piece_" + str(index), (176, 142, 256, 256), radius=8)
        if native_label is not None:
            piece.append(_element("rect", x=x + 6, y=y + 86, width=108, height=29,
                                  rx=5, fill=PAPER, **{"fill-opacity": ".94"}))
            _position_text(native_label, x + 60, y + 108, 22, ORANGE)
            piece.append(native_label)
    for caption in svg:
        if _tag(caption) == "text" and caption.get("y") == "449":
            caption.set("y", "470")
            caption.set("font-size", "25")
    return True


def _confetti(svg, art, uid):
    particles = _find_all(svg, "data-particle-index")
    if not particles:
        return False
    static_art = [node for node in svg if _tag(node) in {"circle", "path"}]
    for node in static_art:
        svg.remove(node)
    stage = _element("g", **{"data-brand-art": "celebration-scene"})
    _clipped_image(stage, _asset(art, "launch"), (75, 104, 450, 242),
                   uid + "_celebration", radius=14)
    first_particle = next(node for node in svg if particles[0] in list(node))
    _insert_before(svg, first_particle, stage)
    return True


def _gallery(svg, art, uid):
    slides = _find_all(svg, "data-gallery-slide")
    if not slides:
        return False
    scenes = ["idea", "studio", "launch"]
    names = ["想法探索", "创作工作台", "带着作品出发"]
    for slide in slides:
        index = int(slide.get("data-gallery-slide", "1")) - 1
        image = next((node for node in slide if _tag(node) == "image"), None)
        if image is not None:
            image.set("href", _asset(art, scenes[index % 3]))
            image.attrib.pop("{http://www.w3.org/1999/xlink}href", None)
            image.set("preserveAspectRatio", "xMidYMid slice")
            for title in image:
                if _tag(title) == "title":
                    title.text = names[index % 3]
    return True


EFFECTS = {
    "blinds": _blinds,
    "open-window": _window,
    "wipe-compare": _wipe,
    "hotspots": _hotspots,
    "zoom-detail": _zoom,
    "motion-path": _motion,
    "typewriter": _typewriter,
    "data-chart": _chart,
    "vinyl": _vinyl,
    "puzzle-assemble": _puzzle,
    "confetti": _confetti,
    "xiumi-gallery": _gallery,
}


def augment(slug, svg, art, uid):
    """Augment a known component SVG, returning whether its artwork was handled."""
    name = slug.removeprefix("wechat-").removeprefix("svg-")
    effect = EFFECTS.get(name)
    if effect is None:
        return False
    prefix = re.sub(r"[^A-Za-z0-9_]", "_", uid)
    return effect(svg, art, prefix)
