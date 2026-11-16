"""Generate a native editable progress ring from current and target values."""
from pathlib import Path
from decimal import Decimal
import math
from component_support import art_slot, color, control, fmt, label, number, run, shell, text_nodes, wrap

COMPONENT = 'wechat-svg-progress-ring'


def render(config, prefix):
    title = config.get('title', '目标进度')
    current = number(config.get('current'), 'current', 0, 1e12)
    target = number(config.get('target'), 'target', 1e-12, 1e12)
    duration = number(config.get('duration', 1.3), 'duration', .4, 3)
    unit = label(config.get('unit', '项'), 'unit', 5)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    ratio = current / target
    percent = f'{ratio * 100:.2f}'.rstrip('0').rstrip('.')
    if len(percent) > 8:
        percent = f'{ratio * 100:.3g}'
    circumference = 2 * math.pi * 146
    offset = circumference * (1 - min(1, ratio))
    difference = Decimal(str(current)) - Decimal(str(target))
    extra = f'超出目标 {fmt(difference)}{unit}，环形按满环显示' if current > target else f'距离目标还差 {fmt(-difference)}{unit}'
    content = f'<circle cx="300" cy="298" r="146" fill="none" stroke="#E7DAC6" stroke-width="26"/>'
    content += f'<circle id="{prefix}_ring" cx="300" cy="298" r="146" fill="none" stroke="{accent}" stroke-width="26" stroke-linecap="round" stroke-dasharray="{circumference:g}" stroke-dashoffset="{offset:g}" transform="rotate(-90 300 298)"><animate attributeName="stroke-dashoffset" values="{circumference:g};{offset:g}" dur="{duration}s" begin="{prefix}_play.click" fill="freeze"/><set attributeName="stroke-dashoffset" to="{offset:g}" begin="{prefix}_reset.click" fill="freeze"/></circle>'
    content += f'<text x="300" y="273" text-anchor="middle" font-size="21" fill="#765B45">实际完成率</text><text x="300" y="331" text-anchor="middle" font-size="56" font-weight="700" fill="{accent}">{percent}%</text>'
    content += f'<text x="300" y="472" text-anchor="middle" font-size="23" fill="#30271F">完成 {fmt(current)}{unit}</text><text x="300" y="506" text-anchor="middle" font-size="23" fill="#30271F">目标 {fmt(target)}{unit}</text>'
    extra_lines = wrap(extra, '进度差值', 28, 2)
    content += text_nodes(extra_lines, 32, 541, 19, '#765B45', spacing=27)
    controls_y = 565 + (len(extra_lines)-1)*27
    content += control(prefix, 'play', '播放进度', 24, controls_y)
    content += control(prefix, 'reset', '恢复静态', 312, controls_y)
    content += art_slot('launch', 30, controls_y+77, 540, 102)
    return shell(COMPONENT, title, '数值来自配置，静态终值始终可读', content, controls_y+205, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '环形指标', render, Path(__file__))
