"""Build the portable, interactive catalog from existing component fragments."""

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


@dataclass(frozen=True)
class Entry:
    name: str
    title: str
    description: str
    fragments: tuple = ()
    kind: str = "interactive"


ENTRIES = (
    Entry("wechat-avatar-profile", "头像跳转公众号", "使用目标账号的真实原生名片，制作对应的头像入口。", kind="workflow"),
    Entry("wechat-svg-envelope", "拆信与收信", "打开信封抽出信纸，再收回重看。", ("component.html",)),
    Entry("wechat-svg-flip-card", "双面翻牌", "翻到背面阅读，再翻回正面。", ("component.html",)),
    Entry("wechat-svg-parallax", "多层视差", "用按钮移动远近景，观察不同位移。", ("component.html",)),
    Entry("wechat-svg-vinyl", "唱片启停", "控制唱片旋转，体验视觉播放状态。", ("component.html",)),
    Entry("wechat-svg-pull-tab", "抽拉标签", "点标签抽出信息条，再收回。", ("component.html",)),
    Entry("wechat-svg-timeline", "动态时间线", "沿时间线依次展开节点与信息。", ("component.html",)),
    Entry("wechat-svg-open-window", "双扇开窗", "点开窗户看内容，合上后可以重新打开。", ("component.html",)),
    Entry("wechat-svg-wipe-compare", "擦拭前后对比", "来回切换，在同一位置比较前后变化。", ("component.html",)),
    Entry("wechat-svg-zoom-detail", "同图局部放大与返回", "在同一幅画面中放大细节，再回到全景。", ("component.html",)),
    Entry("wechat-svg-click-reveal", "点击揭秘", "在固定画面里点开一段短答案。", ("reveal.html",)),
    Entry("wechat-svg-blinds", "百叶窗展开", "分条展开内容，再恢复遮挡。", ("component.html",)),
    Entry("wechat-svg-spotlight", "探照灯", "点选位置照亮局部，也可查看全景。", ("component.html",)),
    Entry("wechat-svg-accordion-panels", "手风琴面板", "点开一块面板，其余面板收窄。", ("component.html",)),
    Entry("wechat-svg-puzzle-assemble", "拼图拼合", "点击播放，看碎片逐块拼合。", ("component.html",)),
    Entry("wechat-svg-confetti", "点按礼花", "点燃粒子礼花，显示祝福，再次播放。", ("component.html",)),
    Entry("wechat-svg-hotspots", "多热区点击与返回", "点开不同节点查看说明，再返回总图。", ("hotspots.html",)),
    Entry("wechat-svg-switch", "点击旋转切换", "短卡片循环展示，末张可回到第一张。", ("switch.html",)),
    Entry("wechat-svg-layer-peel", "点击逐层掉落", "依次揭开内容，结尾持续保留。", ("peel.html",)),
    Entry("wechat-svg-press-reveal", "长按显影与松手复原", "按住画面查看答案，松开恢复。", ("component.html",)),
    Entry("wechat-svg-hold-cards", "长按轮播与松手定格", "按住让卡片轮播，松手停在当时的内容。", ("component.html",)),
    Entry("wechat-svg-quiz", "单题点击答题", "选择一个答案，查看反馈，再返回重选。", ("component.html",)),
    Entry("wechat-svg-story-branches", "多步分支故事", "沿着选择走到结局，再从起点尝试另一条路。", ("component.html",)),
    Entry("wechat-svg-motion-path", "点击轨迹运动", "点击播放，看图形沿路线移动。", ("component.html",)),
    Entry("wechat-svg-typewriter", "逐字打印与重播", "让短句逐字出现，结束后可以重播。", ("component.html",)),
    Entry("wechat-svg-data-chart", "数据柱形图入场", "点击播放柱形变化，示例采用演示数据。", ("component.html",)),
    Entry("wechat-svg-drawline", "SVG 描边", "线条逐渐画出，完成后保持完整。刷新页面可重看。", ("drawline.html",)),
    Entry("wechat-xiumi-gallery", "图片图集", "先试点击切图，再试左右滑动。示例色块用于检查图片顺序。", ("click.html", "scroll.html")),
    Entry("wechat-layout-blocks", "正文排版组件", "按信息关系组织标题、步骤、引用和短表。", ("preview.html",), "layout"),
    Entry("wechat-xiumi-svg-layout", "秀米原生 SVG 布局", "在秀米中配置展开、开窗、长按与局部热区等效果。", kind="workflow"),
)


STYLE = """
:root{color-scheme:light;--paper:#f5f3ed;--ink:#26383e;--accent:#167e99;--muted:#586d73;--line:#d8e1db}
*{box-sizing:border-box}
html{scroll-padding-top:20px}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",system-ui,sans-serif}
main{max-width:640px;margin:auto;padding:30px 16px 64px}
header{border-bottom:2px solid var(--accent);padding-bottom:12px;margin-bottom:20px}
h1{font-size:28px;line-height:1.5;margin:0 0 10px;font-weight:700;letter-spacing:.01em}
h2{font-size:21px;line-height:1.5;margin:0 0 8px}
h3{font-size:16px;line-height:1.6;margin:20px 0 8px}
p{font-size:16px;line-height:1.8;margin:10px 0}
a{color:var(--accent);text-underline-offset:3px}
a:hover{text-decoration-thickness:2px}
a:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:3px}
.intro{color:var(--muted);font-size:15px}
.toc{border:1px solid var(--line);border-radius:12px;background:#fffdf7;padding:12px 14px;margin:0 0 32px}
.toc ol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 18px;margin:0;padding:0;list-style-position:inside}
.toc li{font-size:14px;line-height:1.7;padding:5px 0;min-width:0}
.toc a{overflow-wrap:anywhere;text-decoration:none}
.toc a:hover{text-decoration:underline}
article{margin:34px 0 48px;scroll-margin-top:20px;min-width:0}
.entry-links{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:14px;font-size:14px;line-height:1.8}
.entry-links a:last-child{color:var(--muted)}
.workflow{margin:18px 0;padding:16px 18px;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;background:#fffdf7}
.workflow ol{margin:0;padding-left:1.3em}
.workflow li{font-size:16px;line-height:1.8;margin:9px 0}
.workflow strong{font-weight:700}
.layout-example{background:#fffdf7;border:1px solid var(--line);border-radius:10px;padding:0 16px 18px;overflow-wrap:anywhere}
svg,img{max-width:100%}
footer{border-top:1px solid var(--line);padding-top:14px;color:var(--muted)}
footer p{font-size:14px}
@media(max-width:380px){main{padding:24px 12px 48px}h1{font-size:25px}.toc{padding:10px 12px}.toc ol{column-gap:12px}.toc li{font-size:13px}h2{font-size:20px}.layout-example{padding:0 12px 14px}}
"""


class CatalogCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.svg_count = 0
        self.article_count = 0
        self.has_script = False
        self.remote_assets = []

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "svg":
            self.svg_count += 1
        if tag == "article":
            self.article_count += 1
        if tag == "script":
            self.has_script = True
        if tag in {"img", "image", "iframe", "source", "video", "audio"}:
            for field in ("src", "href", "xlink:href"):
                target = values.get(field, "")
                if target.startswith(("http:", "https:", "//", "file:")):
                    self.remote_assets.append(target)


def workflow_content(name):
    if name == "wechat-avatar-profile":
        return '''<section class="workflow" aria-label="头像入口所需材料">
<ol><li><strong>提供账号线索</strong><br>目标公众号名称、微信号或已发表文章链接。</li>
<li><strong>取得真实原生名片</strong><br>AI在已登录的编辑器中核对账号，再读取对应名片。</li>
<li><strong>生成头像入口</strong><br>使用本次头像与名片，保存后检查实际跳转。</li></ol>
</section>'''
    return '''<section class="workflow" aria-label="秀米原生布局操作">
<ol><li><strong>准备分层素材</strong><br>给出前景、内容层，以及点击前后的目标画面。</li>
<li><strong>配置触发与转场</strong><br>在秀米中设置动画方向、时长、热区和松手行为。</li>
<li><strong>保存重开并预览</strong><br>检查层级、返回和连续操作，再核对公众号与手机表现。</li></ol>
</section>'''


def build(root, destination, repository="frederick-kk/wechat-layout-copilot"):
    root = root.resolve()
    destination = destination.resolve()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("仓库需要采用owner/name格式")
    repository_url = "https://github.com/" + repository
    release_url = repository_url + "/releases/latest/download/"
    if destination.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("预览输出需要使用.html或.htm文件")
    protected_inputs = {
        Path(__file__).resolve(),
        (root / "index.html").resolve(),
        (root / "SKILL.md").resolve(),
        (root / "README.md").resolve(),
    }
    protected_inputs.update(path.resolve() for path in (root / "skills").rglob("*.html"))
    for entry in ENTRIES:
        folder = root / "skills" / entry.name
        protected_inputs.add((folder / "SKILL.md").resolve())
        protected_inputs.update((folder / "examples" / name).resolve() for name in entry.fragments)
    if destination in protected_inputs:
        raise ValueError("输出路径与组件输入文件冲突，请另选HTML文件")
    read_sources = []
    fragments = []
    toc_links = []
    for entry in ENTRIES:
        skill_folder = root / "skills" / entry.name
        instruction = skill_folder / "SKILL.md"
        if not instruction.is_file():
            raise ValueError(f"缺少组件说明 {instruction}")
        relative = os.path.relpath(instruction, destination.parent).replace(os.sep, "/")
        instruction_url = quote(relative, safe="/.-_")
        anchor = "component-" + entry.name
        toc_links.append(f'<li><a href="#{anchor}">{html.escape(entry.title)}</a></li>')
        if entry.kind == "workflow":
            content = workflow_content(entry.name)
        else:
            parts = []
            for index, filename in enumerate(entry.fragments):
                source_path = skill_folder / "examples" / filename
                source = source_path.read_text(encoding="utf-8")
                read_sources.append((source_path.relative_to(root).as_posix(), source))
                if entry.kind == "layout":
                    match = re.search(r"<main\b[^>]*>(.*?)</main\s*>", source, re.I | re.S)
                    if match is None:
                        raise ValueError(f"正文示例缺少main区域 {source_path}")
                    source = '<section class="layout-example">' + match.group(1) + '</section>'
                if entry.name == "wechat-xiumi-gallery":
                    parts.append('<h3>' + ("点击切图" if index == 0 else "横向滑动") + '</h3>')
                parts.append(source)
            content = "\n".join(parts)
        fragments.append(f'''<article id="{anchor}" data-skill="{entry.name}" data-preview-kind="{entry.kind}">
<h2>{html.escape(entry.title)}</h2>
<p>{html.escape(entry.description)}</p>
{content}
<p class="entry-links"><a href="{instruction_url}">读取使用说明</a><a href="{release_url}{entry.name}.zip">下载此Skill</a><a href="#top">返回目录</a></p>
</article>''')

    page = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="公众号组件Skill库的{len(ENTRIES)}个入口与交互示例，包含点击、长按、SVG动效、图集及原生组件操作指引。">
<title>公众号排版外挂 · {len(ENTRIES)}项交互预览</title>
<style>{STYLE}</style>
</head>
<body><main>
<header id="top"><h1>公众号排版外挂</h1>
<p>点一点，滑一滑，选择适合本篇内容的效果。</p>
<p class="entry-links"><a href="{release_url}wechat-layout-copilot.zip">下载完整组件库</a><a href="{repository_url}">查看GitHub仓库</a></p>
<p class="intro">{len(ENTRIES)}个Skill入口。交互组件可直接体验，头像与秀米原生布局列出接入材料和操作指引。</p></header>
<nav class="toc" aria-label="组件目录"><ol>{''.join(toc_links)}</ol></nav>
{chr(10).join(fragments)}
<footer><p>本页展示浏览器效果。秀米保存、公众号同步和手机表现请查对应Skill的实际记录。</p></footer>
</main></body></html>
'''
    check = CatalogCheck()
    check.feed(page)
    duplicate_ids = sorted(identifier for identifier in set(check.ids) if check.ids.count(identifier) > 1)
    if duplicate_ids:
        raise ValueError("组件事件或目录ID重复 " + ", ".join(duplicate_ids))
    if check.has_script or check.remote_assets:
        raise ValueError("预览应采用本地片段和素材，请检查脚本或外部资源")
    if check.article_count != len(ENTRIES):
        raise ValueError("组件章节数量与入口列表不一致")
    for target in check.links:
        parsed = urlsplit(target)
        if parsed.scheme == "file" or re.match(r"^[A-Za-z]:[/\\]", target):
            raise ValueError("预览链接需要使用相对路径")
        if target.startswith("#"):
            if target[1:] not in check.ids:
                raise ValueError("目录锚点缺失 " + target)
        elif not parsed.scheme and not target.startswith("//"):
            if not (destination.parent / unquote(parsed.path)).is_file():
                raise ValueError("本地使用说明链接缺失 " + target)
    source_digest = hashlib.sha256()
    for name, source in read_sources:
        source_digest.update(name.encode("utf-8") + b"\0" + source.encode("utf-8") + b"\0")
    return page, {
        "skill_entries": len(ENTRIES),
        "interactive_entries": sum(entry.kind == "interactive" for entry in ENTRIES),
        "layout_entries": sum(entry.kind == "layout" for entry in ENTRIES),
        "workflow_entries": sum(entry.kind == "workflow" for entry in ENTRIES),
        "svg_elements": check.svg_count,
        "source_files": len(read_sources),
        "source_sha256": source_digest.hexdigest(),
        "local_links_checked": True,
        "unique_ids_checked": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="组件库根目录，默认采用本脚本的上级项目目录")
    parser.add_argument("--out", type=Path, help="预览HTML输出路径，默认采用组件库examples/preview.html")
    parser.add_argument("--repository", default="frederick-kk/wechat-layout-copilot", help="预览页中使用的GitHub仓库，格式owner/name")
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    destination = (args.out or root / "examples/preview.html").resolve()
    temporary = None
    try:
        if destination.is_dir():
            raise ValueError("输出路径指向目录，请指定HTML文件")
        page, result = build(root, destination, args.repository)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(page)
        os.replace(temporary, destination)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    result.update({"status": "created", "output": str(destination),
                   "size_bytes": destination.stat().st_size,
                   "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
