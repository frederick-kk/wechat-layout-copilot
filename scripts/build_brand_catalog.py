"""Build the thirty-component Fred gallery from finished branded demos and GIFs."""

import argparse
import html
import json
import os
from pathlib import Path
import struct
import tempfile
from urllib.parse import quote, unquote, urlsplit

from build_preview import CatalogCheck, ENTRIES


PUBLISHED_DOWNLOADS = (
    "https://github.com/frederick-kk/wechat-layout-copilot/"
    "releases/download/v0.5.3/"
)

STYLE = """
:root{color-scheme:light;--paper:#f5f2eb;--ink:#30271f;--accent:#a64c24;--muted:#6a5141;--line:#cbb89c}
*{box-sizing:border-box}
html{scroll-padding-top:24px}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",sans-serif;line-height:1.75}
main{max-width:1440px;margin:auto;padding:48px 28px 56px}
header{padding-bottom:24px;border-bottom:1px solid var(--line)}
.identity{display:flex;align-items:center;gap:20px}
.avatar{display:block;width:88px;height:88px;object-fit:cover;border-radius:50%;flex:none}
h1{font-size:clamp(28px,4.2vw,42px);line-height:1.3;margin:0 0 12px;font-weight:700}
header p{margin:0;color:var(--muted);max-width:65ch}
h2{font-size:23px;line-height:1.45;margin:0 0 8px;font-weight:700}
p{margin:0}
a{color:#963f1b;text-underline-offset:5px;text-decoration-thickness:1px}
a:hover{color:#63280e;text-decoration-thickness:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:5px}
::selection{background:#e9c695;color:var(--ink)}
.directory{margin:24px 0 0;border-bottom:1px solid var(--line);padding:0 0 20px}
summary{width:fit-content;cursor:pointer;color:#963f1b;font-size:17px;font-weight:700}
.directory ol{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px 24px;list-style:none;padding:20px 0 0;margin:0}
.directory li{min-width:0;font-size:14px;line-height:1.7}
.directory a{overflow-wrap:anywhere}
.gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-items:start;column-gap:32px;row-gap:56px;margin-top:40px}
article{min-width:0;scroll-margin-top:24px}
.purpose{color:var(--muted);font-size:15px;line-height:1.75;min-height:3.5em;margin-bottom:18px}
figure{margin:0}
.demo{display:block;width:100%;height:auto;background:#fffaf1}
.real-demo-video{display:block;width:100%;height:auto;object-fit:contain;background:#111}
.operation-gif{margin-top:16px}
.operation-gif summary{font-size:14px;margin-bottom:12px}
figcaption{font-size:13px;line-height:1.7;margin-top:10px;color:var(--muted)}
.links{display:flex;flex-wrap:wrap;gap:8px 20px;border-top:1px solid var(--line);margin-top:16px;padding-top:12px;font-size:14px}
.links a:first-child{font-weight:700}
.pending{display:flex;align-items:center;justify-content:center;min-height:280px;background:#f0e7d8;color:#6a5141;padding:24px}
footer{border-top:1px solid var(--line);padding-top:20px;margin-top:56px;color:var(--muted);font-size:14px}
footer a{display:inline-block;margin-top:12px}
@media(max-width:1100px){.gallery{grid-template-columns:repeat(2,minmax(0,1fr))}.directory ol{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){main{max-width:664px;padding:32px 20px 48px}.gallery{grid-template-columns:1fr;row-gap:44px}.directory ol{grid-template-columns:repeat(2,minmax(0,1fr))}.purpose{min-height:0}.identity{gap:16px}.avatar{width:68px;height:68px}h2{font-size:22px}}
@media(max-width:380px){main{padding-inline:16px}.identity{align-items:flex-start}.avatar{width:56px;height:56px}h1{font-size:27px}.directory ol{column-gap:16px}}
"""


def relative_url(source, destination):
    """Keep preview and download references portable alongside the repository."""
    relative = os.path.relpath(source, destination.parent)
    return quote(Path(relative).as_posix(), safe="/")


def skip_blocks(data, position, source):
    while position < len(data):
        count = data[position]
        position += 1
        if count == 0:
            return position
        position += count
        if position > len(data):
            break
    raise ValueError(f"GIF 数据块不完整 {source}")


def gif_info(source):
    """Read dimensions and count actual image frames without an image dependency."""
    data = source.read_bytes()
    if len(data) < 14 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError(f"动图需要有效的 GIF 文件 {source}")
    width, height = struct.unpack_from("<HH", data, 6)
    if width == 0 or height == 0:
        raise ValueError(f"GIF 尺寸无效 {source}")
    packed = data[10]
    position = 13 + (3 * 2 ** ((packed & 7) + 1) if packed & 128 else 0)
    frames = 0
    while position < len(data):
        marker = data[position]
        position += 1
        if marker == 0x3B:
            if frames < 2:
                raise ValueError(f"动图至少需要两帧 {source}")
            return {"width": width, "height": height, "frames": frames}
        if marker == 0x21:
            position += 1  # Extension label; the following payload uses sub-blocks.
        elif marker == 0x2C:
            if position + 9 > len(data):
                break
            packed = data[position + 8]
            position += 9
            if packed & 128:
                position += 3 * 2 ** ((packed & 7) + 1)
            position += 1  # LZW minimum code size.
            frames += 1
        else:
            raise ValueError(f"GIF 数据标记无效 {source}")
        position = skip_blocks(data, position, source)
    raise ValueError(f"GIF 结束标记缺失 {source}")


def download_link(entry, destination, downloads, download_base):
    if downloads is not None:
        archive = downloads / (entry.name + ".zip")
        return archive, relative_url(archive, destination), "下载此 Skill"
    base = download_base or PUBLISHED_DOWNLOADS
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("下载地址需要完整的 HTTPS 目录地址")
    label = "下载此 Skill" if download_base else "下载已发布 Skill"
    return None, base.rstrip("/") + "/" + quote(entry.name + ".zip"), label


def build(root, destination, downloads=None, download_base=None, avatar=None, allow_missing=False, overwrite=False):
    root, destination = root.resolve(), destination.resolve()
    if len(ENTRIES) != 30 or len({entry.name for entry in ENTRIES}) != 30:
        raise ValueError("本轮目录需要恰好30个独立组件入口")
    if destination.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("预览输出需要使用.html或.htm文件")
    if downloads is not None and download_base:
        raise ValueError("本地下载目录与在线下载地址二选一")
    downloads = downloads.resolve() if downloads is not None else None
    avatar = avatar.resolve() if avatar is not None else None
    required, records, articles, directory = [], [], [], []
    if avatar is not None:
        if not avatar.is_relative_to(root):
            raise ValueError("请把头像放到组件库内，再生成可携带的目录预览")
        if not avatar.is_file() and not allow_missing:
            raise ValueError("头像文件不存在 " + str(avatar))
        required.append(avatar)
    for entry in ENTRIES:
        folder = root / "skills" / entry.name
        skill = folder / "SKILL.md"
        preview, gif = folder / "examples/brand-preview.html", folder / "examples/demo.gif"
        archive, download_url, download_label = download_link(entry, destination, downloads, download_base)
        required.extend([skill, preview, gif] + ([archive] if archive is not None else []))
        missing = [path for path in [skill, preview, gif, archive] if path is not None and not path.is_file()]
        if missing and not allow_missing:
            raise ValueError("组件材料未齐全 " + ", ".join(str(path) for path in missing))
        anchor = "component-" + entry.name
        title = html.escape(entry.title)
        directory.append(f'<li><a href="#{anchor}">{title}</a></li>')
        info = gif_info(gif) if gif.is_file() else None
        if info is None:
            image = '<p class="pending">动图制作中</p>'
        else:
            image = (
                f'<img class="demo" src="{html.escape(relative_url(gif, destination), quote=True)}" '
                f'width="{info["width"]}" height="{info["height"]}" loading="lazy" decoding="async" '
                f'alt="{title}动态演示">'
            )
        links = []
        recording = folder / "examples/account-jump-real.mp4"
        recording_page = folder / "examples/real-demo.html"
        has_recording = entry.name == "wechat-avatar-profile" and recording.is_file()
        if has_recording:
            required.extend([recording, recording_page, folder / "examples/account-jump-poster.jpg"])
            links.append(f'<a href="{html.escape(relative_url(recording_page, destination), quote=True)}">打开真实演示</a>')
        if preview.is_file():
            preview_label = "打开操作示意" if entry.kind == "workflow" else "打开可操作演示"
            links.append(f'<a href="{html.escape(relative_url(preview, destination), quote=True)}">{preview_label}</a>')
        if skill.is_file():
            links.append(f'<a href="{html.escape(relative_url(skill, destination), quote=True)}">读取 Skill</a>')
        if archive is None or archive.is_file():
            links.append(f'<a href="{html.escape(download_url, quote=True)}">{download_label}</a>')
        description = entry.description
        if entry.name == "wechat-xiumi-gallery":
            description = "切换或横向浏览配图，把几张作品放在同一个位置。"
        caption = '<figcaption>操作示意</figcaption>' if entry.kind == "workflow" else ""
        media = f'<figure>{image}{caption}</figure>'
        if has_recording:
            video_url = html.escape(relative_url(recording, destination), quote=True)
            poster_url = html.escape(relative_url(folder / "examples/account-jump-poster.jpg", destination), quote=True)
            media = (
                f'<figure><video class="real-demo-video" controls playsinline preload="metadata" '
                f'poster="{poster_url}" width="592" height="1280" aria-label="公众号头像跳转完整实录">'
                f'<source src="{video_url}" type="video/mp4"><a href="{video_url}">打开完整录像</a></video>'
                '<figcaption>手机微信真实跳转 · 4.13秒完整原片</figcaption></figure>'
                f'<details class="operation-gif"><summary>查看操作示意GIF</summary>{media}</details>'
            )
        articles.append(
            f'<article id="{anchor}"><h2>{title}</h2>'
            f'<p class="purpose">{html.escape(description)}</p>{media}'
            f'<div class="links">{"".join(links)}</div></article>'
        )
        records.append({"component": entry.name, "kind": entry.kind, "gif": info, "missing": [str(path) for path in missing]})
    protected = {path.resolve() for path in required}
    protected.update({Path(__file__).resolve(), root / "README.md", root / "SKILL.md", root / "index.html"})
    if destination in protected:
        raise ValueError("目录输出不能覆盖组件输入文件")
    if destination.exists() and not overwrite:
        raise ValueError("目录已存在，请另选路径或使用--overwrite")
    avatar_html = f'<img class="avatar" src="{html.escape(relative_url(avatar, destination), quote=True)}" width="88" height="88" alt="Fred 橙帽头像">' if avatar is not None and avatar.is_file() else ""
    page = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>公众号排版外挂 · 30款组件与GIF演示</title><style>{STYLE}</style></head>'
        '<body><main id="top"><header><div class="identity">' + avatar_html +
        '<div><h1>公众号排版外挂</h1><p>小鱼FRED · 30个组件，先看动图，再挑一个交给 AI。纸纹、暖橙和橙帽 Fred，贯穿每一段演示。</p></div>'
        '</div><p class="header-links"><a href="' + html.escape((download_base or PUBLISHED_DOWNLOADS).rstrip('/') + '/wechat-layout-copilot.zip', quote=True) + '">下载全部组件</a> · <a href="https://github.com/frederick-kk/wechat-layout-copilot">查看GitHub仓库</a></p></header><details class="directory"><summary>按名称查找30个组件</summary>'
        '<nav aria-label="全部组件目录"><ol>' + "".join(directory) + '</ol></nav></details>'
        '<section class="gallery" aria-label="30款组件GIF演示">' + "".join(articles) + '</section>'
        '<footer><p>头像跳转附有用户提供的手机微信实录，秀米原生布局提供操作示意。按对应 Skill 替换正文和配图后，在目标账号中核对保存、同步和手机效果。</p>'
        '<a href="#top">返回目录</a></footer></main></body></html>'
    )
    check = CatalogCheck()
    check.feed(page)
    if check.article_count != 30 or len(check.ids) != len(set(check.ids)) or check.has_script:
        raise ValueError("目录数量、实例标识或页面脚本检查失败")
    for target in check.links:
        parsed = urlsplit(target)
        if not parsed.path and parsed.fragment:
            if unquote(parsed.fragment) not in check.ids:
                raise ValueError("目录锚点缺失 " + target)
    if not allow_missing and any(not path.is_file() for path in required):
        raise ValueError("构建期间材料发生变化，请重新构建")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(page)
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"output": str(destination), "components": len(records), "animated_gifs": sum(row["gif"] is not None for row in records), "allow_missing": allow_missing, "entries": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--downloads-dir", type=Path, help="本地独立ZIP目录，文件名为组件目录名.zip")
    parser.add_argument("--download-base", help="已经发布的HTTPS下载目录地址")
    parser.add_argument("--avatar", type=Path, help="可选的本地头像文件")
    parser.add_argument("--allow-missing", action="store_true", help="开发预览允许缺少演示文件")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    try:
        result = build(root, args.out or root / "examples/brand-gallery.html", args.downloads_dir, args.download_base, args.avatar, args.allow_missing, args.overwrite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
