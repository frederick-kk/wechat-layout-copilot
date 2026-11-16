"""Generate a multi-page SVG book with bounded sequential navigation."""
from pathlib import Path
import html
from component_support import art_slot, color, items, label, number, run, shell, text_nodes, wrap

COMPONENT = 'wechat-svg-book'


def navigation(prefix, action, page, caption, x, enabled, accent):
    fill = accent if enabled else '#D7C1AC'
    pointer_style = '' if enabled else ';pointer-events:none'
    return f'<g id="{prefix}_{action}_{page}" data-action="{action}" data-page="{page}" style="cursor:pointer{pointer_style}"><rect x="{x}" y="646" width="160" height="52" rx="10" fill="{fill}"/><text x="{x+80}" y="681" font-size="22" text-anchor="middle" fill="#FFFFFF" pointer-events="none">{html.escape(caption)}</text></g>'


def render(config, prefix):
    pages = items(config.get('pages'), 'pages', 3, 5)
    duration = number(config.get('duration', .7), 'duration', .4, 2)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    checked = []
    for index, page in enumerate(pages):
        checked.append((label(page.get('title'), f'pages[{index}].title', 14), wrap(page.get('body'), f'pages[{index}].body',18,4)))
    content = '<rect x="28" y="127" width="31" height="480" rx="8" fill="#BA7A45"/><path d="M42 137V596" stroke="#F2D9B8" stroke-width="3"/>'
    count = len(checked)
    for index, (title, body) in enumerate(checked):
        outgoing = []
        incoming = []
        if index < count-1:
            outgoing.append(f'{prefix}_next_{index}.click')
            incoming.append(f'{prefix}_prev_{index+1}.click')
        if index > 0:
            outgoing.extend([f'{prefix}_prev_{index}.click', f'{prefix}_home_{index}.click'])
            incoming.append(f'{prefix}_next_{index-1}.click')
        else:
            incoming.extend(f'{prefix}_home_{other}.click' for other in range(1,count))
        outgoing_start = ';'.join(outgoing)
        outgoing_middle = ';'.join(event+f'+{duration/2:g}s' for event in outgoing)
        incoming_middle = ';'.join(event+f'+{duration/2:g}s' for event in incoming)
        incoming_end = ';'.join(event+f'+{duration:g}s' for event in incoming)
        visible = 'visible' if index == 0 else 'hidden'
        pointer_events = 'auto' if index == 0 else 'none'
        content += f'<g id="{prefix}_page_{index}" data-state="page-{index}" visibility="{visible}" pointer-events="{pointer_events}"><set attributeName="visibility" to="hidden" begin="{outgoing_middle}" fill="freeze"/><set attributeName="visibility" to="visible" begin="{incoming_middle}" fill="freeze"/><set attributeName="pointer-events" to="none" begin="{outgoing_start}" fill="freeze"/><set attributeName="pointer-events" to="auto" begin="{incoming_end}" fill="freeze"/>'
        content += f'<g transform="translate(48 133)"><g transform="scale(1 1)"><animateTransform attributeName="transform" type="scale" values="1 1;0 1" dur="{duration/2:g}s" begin="{outgoing_start}" fill="freeze"/><animateTransform attributeName="transform" type="scale" values="0 1;1 1" dur="{duration/2:g}s" begin="{incoming_middle}" fill="freeze"/>'
        content += f'<rect x="0" y="0" width="516" height="474" rx="8" fill="#FFFEFA" stroke="#D0B38E"/><path d="M490 0L516 26H490Z" fill="#E8D0AD"/><text x="28" y="59" font-size="28" font-weight="700" fill="{accent}">{title}</text><path d="M28 83H480" stroke="#DBC5A8"/>{text_nodes(body,28,128,23,"#30271F",spacing=37)}'
        content += art_slot(['idea','studio','launch'][index%3], 28, 280, 460, 124)
        content += f'<text x="486" y="447" text-anchor="end" font-size="18" fill="#957859">第 {index+1} / {count} 页</text></g></g>'
        content += navigation(prefix,'prev',index,'上一页',30,index>0,accent)
        content += navigation(prefix,'home',index,'回到首页',220,index>0,accent)
        content += navigation(prefix,'next',index,'下一页',410,index<count-1,accent)
        content += '</g>'
    content += '<text x="300" y="742" text-anchor="middle" font-size="19" fill="#765B45">按顺序前后翻页，最后也能回到首页</text>'
    return shell(COMPONENT, config.get('title', '多页翻书'), '三至五页连续阅读，页码与原生文字一起保留', content, 770, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '多页翻书', render, Path(__file__))
