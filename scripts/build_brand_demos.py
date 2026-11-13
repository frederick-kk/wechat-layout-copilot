"""Build thirty Fred-branded demonstrations from the existing component logic."""

import argparse
import base64
import colorsys
import html
import json
from pathlib import Path
import re
import shutil
import uuid
import xml.etree.ElementTree as ET

from build_preview import ENTRIES
import brand_cards
import brand_effects

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def node(name, attrs=None, text=None):
    result = ET.Element(f'{{{NS}}}{name}', {key: str(value) for key, value in (attrs or {}).items()})
    result.text = text
    return result


def image(href, x, y, width, height, fit='xMidYMid slice', opacity=1):
    return node('image', {'href': href, 'x': x, 'y': y, 'width': width, 'height': height,
                          'preserveAspectRatio': fit, 'opacity': opacity, 'pointer-events': 'none'})


def text(value, x, y, size=30, fill='#30271F', weight=400):
    return node('text', {'x': x, 'y': y, 'font-size': size, 'fill': fill,
                         'font-weight': weight, 'font-family': 'sans-serif'}, value)


def themed_color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return value
    exact = {'#27383F': '#30271F', '#1F2937': '#30271F', '#68777E': '#765B45',
             '#586D73': '#765B45', '#FFFFFF': '#FFFCF6', '#22343B': '#30251D'}
    if value.upper() in exact:
        return exact[value.upper()]
    rgb = tuple(int(value[index:index+2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    if .36 < hue < .74 and saturation > .1:
        return '#A95026' if lightness < .5 else '#CC9668' if lightness < .75 else '#E8D9BD'
    return value


def apply_palette(svg):
    for item in svg.iter():
        for attr in ['fill', 'stroke', 'color']:
            if attr in item.attrib:
                item.set(attr, themed_color(item.get(attr)))
        if 'style' in item.attrib:
            item.set('style', re.sub(r'#[0-9A-Fa-f]{6}', lambda m: themed_color(m.group()), item.get('style')))


def source_svg(path):
    content = path.read_text(encoding='utf-8')
    content = re.sub(r'<!doctype[^>]*>', '', content, flags=re.I)
    container = ET.fromstring('<brand-source>' + content + '</brand-source>')
    result = container.find('.//{' + NS + '}svg')
    if result is None:
        raise ValueError(f'No SVG in {path}')
    return result


def add_paper(svg, art):
    viewbox = [float(value) for value in svg.get('viewBox').split()]
    width, height = viewbox[2:]
    insertion = 0
    for index, child in enumerate(svg):
        if child.tag == '{' + NS + '}rect' and float(child.get('width', '0')) >= width * .9 and float(child.get('height', '0')) >= height * .9:
            insertion = index + 1
            break
    svg.insert(insertion, image(art['paper'], 0, 0, width, height, opacity=.6))


def wrap_svg(svg, art, uid):
    box = [float(value) for value in svg.get('viewBox').split()]
    original_width, original_height = box[2:]
    scaled_height = original_height * 600 / original_width
    total = scaled_height + 100
    outer = node('svg', {'viewBox': f'0 0 600 {total:g}', 'width': '100%', 'style': 'display:block;width:100%;height:auto;', 'data-brand-frame': 'true'})
    outer.append(node('rect', {'width':600,'height':total,'fill':'#FAF6ED'}))
    outer.append(image(art['paper'], 0, 0, 600, total, opacity=.75))
    defs = node('defs')
    clip = ET.SubElement(defs, '{' + NS + '}clipPath', {'id':uid + '_avatar'})
    clip.append(node('rect', {'x':24,'y':18,'width':62,'height':62,'rx':14}))
    outer.append(defs)
    portrait = image(art['avatar'], 24, 18, 62, 62)
    portrait.set('clip-path', 'url(#' + uid + '_avatar)')
    outer.append(portrait)
    outer.append(text('小鱼FRED', 104, 47, 27, '#A94B21', 700))
    outer.append(text('AI · 商业 · 成长', 104, 76, 19, '#765B45'))
    outer.append(node('path', {'d':'M24 96H576','stroke':'#C6AA7B','stroke-width':1}))
    svg.set('x', '0')
    svg.set('y', '100')
    svg.set('width', '600')
    svg.set('height', f'{scaled_height:g}')
    svg.set('style', 'overflow:hidden;max-width:none;')
    outer.append(svg)
    return ET.tostring(outer, encoding='unicode'), total


def workflow_svg(name, art, uid):
    avatar = name == 'wechat-avatar-profile'
    title = '头像入口流程示意' if avatar else '秀米原生布局操作示意'
    headings = ['找到自己的公众号', '把头像接到原生名片', '保存后检查真实跳转'] if avatar else ['准备前景与内容层', '设置触发与转场', '保存重开，手机检查']
    copies = [('核对公众号名称、微信号与头像。','本例账号为 小鱼FRED。'), ('读取真实 mp-common-profile。','让可见头像与原生点击层对齐。'), ('核对点击范围与目标账号。','在手机微信里检查最终表现。')] if avatar else [('一张前景图，一张内容图。','先让各层尺寸与位置保持一致。'), ('配置点击、长按与打开方向。','逐层检查遮挡和热区位置。'), ('保存草稿后重新打开。','再核对公众号同步与手机效果。')]
    root = node('svg', {'viewBox':'0 0 600 720','data-component':name,'width':'100%'})
    for index in range(3):
        visible = index == 0
        group = node('g', {'data-workflow-panel':index, 'visibility':'visible' if visible else 'hidden', 'style':'visibility:' + ('visible' if visible else 'hidden')})
        group.append(node('set', {'attributeName':'visibility','to':'visible','begin':f'{uid}_next_{(index-1)%3}.click','fill':'freeze'}))
        group.append(node('set', {'attributeName':'visibility','to':'hidden','begin':f'{uid}_next_{index}.click','fill':'freeze'}))
        group.append(node('rect', {'width':600,'height':720,'fill':'#FAF6ED'}))
        group.append(image(art['paper'], 0, 0, 600, 720, opacity=.75))
        group.append(text(title, 30, 56, 34, '#30271F', 700))
        group.append(text(headings[index], 30, 126, 32, '#A94B21', 700))
        for line, value in enumerate(copies[index]):
            group.append(text(value, 30, 183 + line * 44, 28))
        if avatar and index == 0:
            group.append(image(art['avatar'], 210, 270, 180, 180, 'xMidYMid meet'))
            group.append(text('小鱼FRED', 213, 505, 30, '#A94B21', 700))
        else:
            group.append(image(art[['idea','studio','launch'][index]], 30, 260, 540, 300))
        action = node('g', {'id':f'{uid}_next_{index}','data-workflow-next':index,'style':'cursor:pointer;'})
        action.append(node('rect', {'x':30,'y':594,'width':540,'height':64,'rx':12,'fill':'#A94B21'}))
        label = '下一步' if index < 2 else '返回第一步'
        action.append(text(label, 230 if index < 2 else 208, 637, 30, '#FFFFFF', 700))
        group.append(action)
        group.append(text('操作示意 · 实际效果按平台保存与手机检查', 30, 701, 22, '#765B45'))
        root.append(group)
    return root


def drawline_svg(source, art):
    root = node('svg', {'viewBox':'0 0 600 690','data-component':'wechat-svg-drawline'})
    root.append(node('rect', {'width':600,'height':690,'fill':'#FAF6ED'}))
    root.append(text('把一个想法，慢慢画出来。', 30, 62, 34, '#30271F', 700))
    root.append(image(art['idea'], 30, 104, 540, 335))
    root.append(text('让细线替正文留一点呼吸。', 30, 491, 28, '#765B45'))
    source.set('x','30');source.set('y','527');source.set('width','540');source.set('height','110')
    root.append(source)
    return root


def body_demo(art):
    return f'''<div class="brand-heading"><img src="{art['avatar']}" alt="Fred橙帽头像"><div><b>小鱼FRED</b><small>AI · 商业 · 成长</small></div></div>
<div id="reading-scroll"><h1>把想法，做成第一份作品。</h1><p>如果你也想用 AI 做点真实的事情，先找一个能动手的小需求。跑通之后，再一点点往前，嘻嘻。</p><img class="scene" src="{art['studio']}" alt="创作工作台"><h2>先让读者看懂流程</h2><ol><li><strong>准备素材</strong><p>收齐需求与原始资料。</p></li><li><strong>做出样稿</strong><p>把风格和每页内容讲清楚。</p></li><li><strong>确认后交付</strong><p>检查文字与可编辑效果。</p></li></ol><blockquote>每一步都说清楚给什么、拿到什么、检查什么。</blockquote><h2>用一张表，抓住确认节点</h2><table><thead><tr><th>阶段</th><th>产出</th><th>确认</th></tr></thead><tbody><tr><td>样稿</td><td>3–5页示例</td><td>视觉方向</td></tr><tr><td>内容</td><td>每页具体文字</td><td>信息是否到位</td></tr><tr><td>终稿</td><td>可编辑文件</td><td>内容与排版</td></tr></tbody></table><img class="scene" src="{art['launch']}" alt="作品完成"><p>先迈出一步，让真实的反馈告诉你下一步怎么走。</p></div>'''


STYLE = '''*{box-sizing:border-box}body{margin:0;background:#F5F2EB;color:#30271F;font-family:"Microsoft YaHei",sans-serif}#demo-stage{width:100%;max-width:600px;margin:0 auto;background:#FAF6ED}svg{max-width:100%}.links{max-width:600px;padding:16px 20px;margin:auto;line-height:1.8;font-size:14px}.links a{color:#963F1B;margin-right:16px;text-underline-offset:4px}.brand-heading{height:100px;display:flex;gap:18px;align-items:center;padding:18px 24px;border-bottom:1px solid #C6AA7B}.brand-heading img{width:62px;height:62px;border-radius:14px}.brand-heading b{display:block;color:#A94B21;font-size:27px}.brand-heading small{font-size:19px;color:#765B45}#reading-scroll{height:760px;overflow:auto;padding:20px 28px;line-height:1.8;background:rgba(255,255,255,.35)}#reading-scroll h1{font-size:30px;line-height:1.5}#reading-scroll h2{font-size:26px;color:#A94B21;margin-top:32px}#reading-scroll p,#reading-scroll li{font-size:23px}#reading-scroll .scene{width:100%;display:block}#reading-scroll blockquote{margin:24px 0;padding:20px;background:#EFE2CE;font-size:23px}#reading-scroll table{width:100%;border-collapse:collapse;font-size:21px}th,td{text-align:left;border:1px solid #C6AA7B;padding:12px 8px}th{background:#EBD6B4}#gallery-scroll{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding:20px 24px;background:#FAF6ED}#gallery-scroll img{width:78%;height:180px;object-fit:cover;flex:none;scroll-snap-align:start;border-radius:6px}::selection{background:#E9C695}'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--only', nargs='+', choices=[entry.name for entry in ENTRIES])
    args = parser.parse_args()
    root = args.root.resolve()
    assets = {p.stem:p for p in (root / 'assets/brand').glob('*.webp')}
    expected = {'avatar','paper','studio','envelope','far','middle','near','idea','launch','record','before'}
    if not expected.issubset(assets):
        raise ValueError('Brand assets incomplete ' + ','.join(sorted(expected-set(assets))))
    records = []
    manifest_path = root / 'assets/brand/demo-manifest.json'
    previous = {row['slug']:row for row in json.loads(manifest_path.read_text(encoding='utf-8'))} if args.only and manifest_path.exists() else {}
    pilots = {'wechat-svg-envelope','wechat-svg-spotlight','wechat-svg-parallax'}
    for entry in ENTRIES:
        if args.only and entry.name not in args.only:
            if entry.name not in previous:
                raise ValueError('Build all demonstrations before a partial rebuild')
            records.append(previous[entry.name])
            continue
        examples = root / 'skills' / entry.name / 'examples'
        examples.mkdir(exist_ok=True)
        outputs = [examples / 'brand-component.html', examples / 'brand-preview.html']
        if any(p.exists() for p in outputs) and not args.overwrite:
            raise ValueError('Output exists ' + entry.name)
        art = {key:'brand-assets/' + path.name for key,path in assets.items()}
        uid = 'brand_' + uuid.uuid4().hex
        if entry.kind == 'workflow':
            svg = workflow_svg(entry.name, art, uid)
        elif entry.kind == 'layout':
            svg = None
        else:
            source = examples / ('artwork-component.html' if entry.name in pilots else entry.fragments[0])
            svg = source_svg(source)
            if entry.name in pilots:
                mapping = {'envelope-pocket-v1.png':'envelope','paper-white-folds.png':'paper','studio-exploration-v1.png':'studio','journey-far-v1.png':'far','journey-middle-v1.png':'middle','journey-near-v1.png':'near'}
                for img in svg.iter('{' + NS + '}image'):
                    uri = img.get('href','')
                    for original, key in mapping.items():
                        matches = list((root / 'skills' / entry.name / 'assets').glob(original))
                        if matches and uri == 'data:image/png;base64,' + base64.b64encode(matches[0].read_bytes()).decode('ascii'):
                            img.set('href',art[key])
                            break
            else:
                apply_palette(svg)
                add_paper(svg, art)
                if entry.name == 'wechat-svg-drawline':
                    svg = drawline_svg(svg, art)
                elif not (brand_cards.augment(entry.name,svg,art,uid) or brand_effects.augment(entry.name,svg,art,uid)):
                    raise ValueError('No brand treatment ' + entry.name)
        height = 860
        content = body_demo(art) if svg is None else wrap_svg(svg,art,uid)[0]
        if svg is not None:
            height = float(svg.get('viewBox').split()[3]) + 100
        if entry.name == 'wechat-xiumi-gallery':
            content += '<div id="gallery-scroll" aria-label="横向图片图集">' + ''.join(f'<img src="{art[key]}" alt="{caption}">' for key,caption in [('idea','灵感'),('studio','制作'),('launch','完成')]) + '</div>'
            height += 220
        referenced = set(re.findall(r'brand-assets/([a-z-]+\.webp)', content))
        local_assets = examples / 'brand-assets'
        local_assets.mkdir(exist_ok=True)
        for filename in referenced:
            shutil.copy2(root / 'assets/brand' / filename, local_assets / filename)
        page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(entry.title)} · Fred品牌演示</title><style>{STYLE}</style></head><body><main id="demo-stage" data-demo-kind="{entry.kind}">{content}</main><nav class="links"><a href="https://frederick-kk.github.io/wechat-layout-copilot/examples/brand-gallery.html">全部30款</a><a href="../SKILL.md">读取Skill</a><a href="demo.gif">查看GIF</a></nav></body></html>'''
        outputs[0].write_text(content, encoding='utf-8', newline='\n')
        outputs[1].write_text(page, encoding='utf-8', newline='\n')
        records.append({'slug':entry.name,'title':entry.title,'kind':entry.kind,'canvas':[600,height],'assets':sorted(referenced),'preview':str(outputs[1].relative_to(root)).replace('\\','/'),'gif':str((examples/'demo.gif').relative_to(root)).replace('\\','/'),'status':'demo-built; GIF capture pending'})
    (root / 'assets/brand/demo-manifest.json').write_text(json.dumps(records, ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'components':len(records),'assets':len(assets),'manifest':'assets/brand/demo-manifest.json'},ensure_ascii=False))


if __name__ == '__main__':
    main()
