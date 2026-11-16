"""Generate a funnel from monotone stages and report conversion denominators."""
from pathlib import Path
from component_support import color, control, fmt, items, label, number, run, shell

COMPONENT = 'wechat-svg-funnel'


def render(config, prefix):
    stages = items(config.get('stages'), 'stages', 3, 5)
    duration = number(config.get('duration', 1.2), 'duration', .4, 3)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    unit = label(config.get('unit', '项'), 'unit', 4)
    values = []
    names = []
    for index, stage in enumerate(stages):
        names.append(label(stage.get('label'), f'stages[{index}].label', 5))
        values.append(number(stage.get('value'), f'stages[{index}].value', 0, 1e12))
    if values[0] <= 0 or any(later > earlier for earlier, later in zip(values, values[1:])):
        raise ValueError('漏斗首阶段需大于零，后续数值不能增加')
    content = '<text x="30" y="122" font-size="18" fill="#765B45">阶段</text><text x="450" y="122" font-size="18" fill="#765B45">数值 / 相邻比例</text>'
    for index, (name, value) in enumerate(zip(names, values)):
        top = 145 + index * 79
        upper_width = 330 * value / values[0]
        lower_value = values[index+1] if index+1 < len(values) else value
        lower_width = 330 * lower_value / values[0]
        points = f'{272-upper_width/2:g},{top} {272+upper_width/2:g},{top} {272+lower_width/2:g},{top+68} {272-lower_width/2:g},{top+68}'
        start = f'272,{top} 272,{top} 272,{top+68} 272,{top+68}'
        content += f'<polygon points="{points}" fill="{accent}" opacity="{1-index*.12:g}"><animate attributeName="points" values="{start};{points}" dur="{duration}s" begin="{prefix}_play.click" fill="freeze"/><set attributeName="points" to="{points}" begin="{prefix}_reset.click" fill="freeze"/></polygon>'
        adjacent = '首阶段' if index == 0 else '无基数' if values[index-1] == 0 else f'{value/values[index-1]*100:.1f}%'
        content += f'<text x="24" y="{top+39}" font-size="18" fill="#30271F">{name}</text><text x="450" y="{top+25}" font-size="21" fill="#30271F">{value:.3g}</text><text x="450" y="{top+52}" font-size="17" fill="#765B45">{adjacent}</text>'
    details_y = 165 + len(values)*79
    for index, (name, value) in enumerate(zip(names, values)):
        total = value / values[0] * 100
        content += f'<text x="30" y="{details_y+index*28}" font-size="20" fill="#30271F">{name}  {fmt(value)}{unit}  占首阶段 {total:.1f}%</text>'
    controls_y = details_y + len(values)*28 + 15
    content += control(prefix, 'play', '播放漏斗', 24, controls_y)
    content += control(prefix, 'reset', '恢复静态', 312, controls_y)
    return shell(COMPONENT, config.get('title', '转化漏斗'), '宽度对应真实数值，比例注明计算基数', content, controls_y+80, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '转化漏斗', render, Path(__file__))
