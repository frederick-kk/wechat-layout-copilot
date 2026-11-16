"""Generate a waterfall with exact start, signed contributions and end value."""
from decimal import Decimal
from pathlib import Path
from component_support import color, control, fmt, items, label, number, run, shell

COMPONENT = 'wechat-svg-waterfall'


def render(config, prefix):
    start = number(config.get('start'), 'start', -1e12, 1e12)
    changes = items(config.get('changes'), 'changes', 2, 6)
    duration = number(config.get('duration', 1.1), 'duration', .4, 3)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    unit = label(config.get('unit', '项'), 'unit', 4)
    accumulated = Decimal(str(start))
    bars = [('起点', Decimal(0), accumulated, accumulated)]
    levels = [Decimal(0), accumulated]
    for index, change in enumerate(changes):
        name = label(change.get('label'), f'changes[{index}].label', 5)
        delta = Decimal(str(number(change.get('value'), f'changes[{index}].value', -1e12, 1e12)))
        before = accumulated
        accumulated += delta
        bars.append((name, before, accumulated, delta))
        levels.append(accumulated)
    bars.append(('终值', Decimal(0), accumulated, accumulated))
    low, high = float(min(levels)), float(max(levels))
    spread = high - low or 1
    low -= spread * .15
    high += spread * .15
    def y(value):
        return 477 - (float(value)-low)/(high-low)*325
    width = 540 / len(bars)
    content = f'<path d="M30 {y(0):g}H570" stroke="#BBA889" stroke-width="1"/><text x="30" y="128" font-size="19" fill="#765B45">单位 {unit} · 下方保留完整数值</text>'
    for index, (name, before, after, value) in enumerate(bars):
        x = 30 + index * width + 6
        top = min(y(before), y(after))
        height = max(abs(y(before)-y(after)), .7)
        fill = '#79543A' if index in {0, len(bars)-1} else accent if value >= 0 else '#669A9E'
        content += f'<rect x="{x:g}" y="{top:g}" width="{width-12:g}" height="{height:g}" rx="4" fill="{fill}"><animate attributeName="y" values="{y(before):g};{top:g}" dur="{duration}s" begin="{prefix}_play.click" fill="freeze"/><animate attributeName="height" values="0;{height:g}" dur="{duration}s" begin="{prefix}_play.click" fill="freeze"/><set attributeName="y" to="{top:g}" begin="{prefix}_reset.click" fill="freeze"/><set attributeName="height" to="{height:g}" begin="{prefix}_reset.click" fill="freeze"/></rect>'
        compact = f'{float(value):.3g}'
        if index not in {0, len(bars)-1} and value > 0:
            compact = '+' + compact
        content += f'<text x="{x+(width-12)/2:g}" y="{top-10:g}" text-anchor="middle" font-size="17" fill="#30271F">{compact}</text><text x="{x+(width-12)/2:g}" y="514" text-anchor="middle" font-size="17" fill="#765B45">{name}</text>'
        if index < len(bars)-1:
            content += f'<path d="M{x+width-12:g} {y(after):g}H{x+width:g}" stroke="#A48F74" stroke-dasharray="4 3"/>'
        sign = '+' if index not in {0, len(bars)-1} and value > 0 else ''
        content += f'<text x="32" y="{555+index*27}" font-size="21" fill="{fill}">{index+1}. {name}  {sign}{fmt(value)}{unit}</text>'
    controls_y = 568 + len(bars)*27
    content += control(prefix, 'play', '播放变化', 24, controls_y)
    content += control(prefix, 'reset', '恢复静态', 312, controls_y)
    return shell(COMPONENT, config.get('title', '增减贡献瀑布图'), '起点＋逐项贡献＝终值，点击重播变化', content, controls_y+80, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '增减贡献瀑布图', render, Path(__file__))
