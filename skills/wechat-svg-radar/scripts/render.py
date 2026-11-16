"""Generate a two-series radar with per-axis normalization and full values."""
from pathlib import Path
import math
from component_support import color, control, fmt, items, label, number, run, shell

COMPONENT = 'wechat-svg-radar'


def render(config, prefix):
    axes = items(config.get('axes'), 'axes', 3, 6)
    series = items(config.get('series'), 'series', 2, 2)
    duration = number(config.get('duration', 1.2), 'duration', .4, 3)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    limits = []
    names = []
    for index, axis in enumerate(axes):
        names.append(label(axis.get('label'), f'axes[{index}].label', 6))
        limits.append(number(axis.get('max'), f'axes[{index}].max', 1e-12, 1e12))
    values = []
    series_names = []
    for series_index, item in enumerate(series):
        series_names.append(label(item.get('name'), f'series[{series_index}].name', 6))
        raw = item.get('values')
        if not isinstance(raw, list) or len(raw) != len(axes):
            raise ValueError('两系列values数量需要与axes一致')
        values.append([number(value, f'series[{series_index}].values[{index}]', 0, limits[index]) for index, value in enumerate(raw)])
    center_x, center_y, radius = 300, 355, 164
    def point(index, proportion, own_radius=radius):
        angle = index * 2 * math.pi / len(axes)
        return center_x + math.sin(angle)*own_radius*proportion, center_y-math.cos(angle)*own_radius*proportion
    def points(proportions):
        return ' '.join(f'{x:g},{y:g}' for x,y in [point(index, value) for index,value in enumerate(proportions)])
    content = ''
    for level in range(1, 5):
        content += f'<polygon points="{points([level/4]*len(axes))}" fill="none" stroke="#D8C7AE"/><text x="306" y="{center_y-radius*level/4+15:g}" font-size="14" fill="#9A846A">{level*25}%</text>'
    for index, name in enumerate(names):
        x,y = point(index, 1)
        lx,ly = point(index, 1, 210)
        content += f'<path d="M300 355L{x:g} {y:g}" stroke="#D8C7AE"/><text x="{lx:g}" y="{ly:g}" text-anchor="middle" font-size="20" fill="#30271F">{name}</text><text x="{lx:g}" y="{ly+21:g}" text-anchor="middle" font-size="15" fill="#765B45">上限 {limits[index]:.3g}</text>'
    palette = [accent, '#397B83']
    collapsed = points([0]*len(axes))
    for index, row in enumerate(values):
        own_points = points([value/limit for value,limit in zip(row,limits)])
        content += f'<polygon points="{own_points}" fill="{palette[index]}" fill-opacity=".16" stroke="{palette[index]}" stroke-width="3"><animate attributeName="points" values="{collapsed};{own_points}" dur="{duration}s" begin="{prefix}_play.click" fill="freeze"/><set attributeName="points" to="{own_points}" begin="{prefix}_reset.click" fill="freeze"/></polygon>'
        content += f'<circle cx="{35+index*260}" cy="122" r="6" fill="{palette[index]}"/><text x="{50+index*260}" y="129" font-size="21" fill="{palette[index]}">{series_names[index]}</text>'
    details_y = 620
    content += f'<text x="30" y="593" font-size="18" fill="#765B45">维度</text><text x="200" y="593" font-size="18" fill="{palette[0]}">{series_names[0]}</text><text x="330" y="593" font-size="18" fill="{palette[1]}">{series_names[1]}</text><text x="460" y="593" font-size="18" fill="#765B45">上限</text>'
    for index, name in enumerate(names):
        row_y = details_y+index*28
        content += f'<text x="30" y="{row_y}" font-size="18" fill="#30271F">{name}</text><text x="200" y="{row_y}" font-size="17" fill="{palette[0]}">{fmt(values[0][index])}</text><text x="330" y="{row_y}" font-size="17" fill="{palette[1]}">{fmt(values[1][index])}</text><text x="460" y="{row_y}" font-size="17" fill="#30271F">{fmt(limits[index])}</text>'
    controls_y = details_y + len(axes)*28 + 9
    content += control(prefix, 'play', '播放展开', 24, controls_y)
    content += control(prefix, 'reset', '恢复静态', 312, controls_y)
    return shell(COMPONENT, config.get('title', '双系列雷达'), '按各轴上限归一，原始数值在下方逐项保留', content, controls_y+80, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '双系列雷达', render, Path(__file__))
