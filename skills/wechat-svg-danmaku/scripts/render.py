"""Generate readable looping SVG text lanes with stop and restart controls."""
from pathlib import Path
from component_support import art_slot, color, control, items, label, number, run, shell

COMPONENT = 'wechat-svg-danmaku'


def render(config, prefix):
    messages = items(config.get('messages'), 'messages', 3, 9)
    duration = number(config.get('duration', 12), 'duration', 8, 24)
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    checked = []
    counts = [0,0,0]
    for index, message in enumerate(messages):
        text = label(message.get('text'), f'messages[{index}].text', 9)
        lane = message.get('lane', index%3)
        if isinstance(lane, bool) or not isinstance(lane, int) or not 0 <= lane <= 2:
            raise ValueError('lane需要0、1、2之一')
        if counts[lane] >= 3:
            raise ValueError('每条轨道最多三条弹幕，避免遮挡')
        phase = counts[lane]/3 + lane*.45/duration
        counts[lane] += 1
        checked.append((text,lane,phase,len(message['text'])*22+38))
    content = f'<defs><clipPath id="{prefix}_clip"><rect x="24" y="120" width="552" height="290" rx="12"/></clipPath></defs><rect x="24" y="120" width="552" height="290" rx="12" fill="#F2E6D5"/>'
    content += f'<g clip-path="url(#{prefix}_clip)">{art_slot("studio",24,120,552,290)}'
    for index, (text,lane,phase,width) in enumerate(checked):
        y = 151 + lane*78
        initial_x = 600-(600+width)*phase
        if phase == 0:
            positions = f'600 0;{-width:g} 0'
            key_times = '0;1'
        else:
            positions = f'{initial_x:g} 0;{-width:g} 0;600 0;{initial_x:g} 0'
            key_times = f'0;{1-phase:g};{1-phase:g};1'
        content += f'<g data-message="{index}" transform="translate({initial_x:g} 0)"><animateTransform attributeName="transform" type="translate" values="{positions}" keyTimes="{key_times}" dur="{duration}s" begin="{prefix}_play.click" end="{prefix}_stop.click" repeatCount="indefinite" fill="freeze"/><rect x="0" y="{y}" width="{width}" height="48" rx="22" fill="#FFFCF6" stroke="{accent}" stroke-opacity=".6"/><text x="19" y="{y+32}" font-size="22" fill="#30271F">{text}</text></g>'
    content += '</g>'
    content += f'<g data-state="playing" visibility="hidden"><set attributeName="visibility" to="visible" begin="{prefix}_play.click" fill="freeze"/><set attributeName="visibility" to="hidden" begin="{prefix}_stop.click" fill="freeze"/><text x="300" y="443" text-anchor="middle" font-size="18" fill="{accent}">播放中 · 三条轨道循环</text></g>'
    content += f'<g data-state="stopped" visibility="visible"><set attributeName="visibility" to="hidden" begin="{prefix}_play.click" fill="freeze"/><set attributeName="visibility" to="visible" begin="{prefix}_stop.click" fill="freeze"/><text x="300" y="443" text-anchor="middle" font-size="18" fill="#765B45">点击开始，停止后可从头重播</text></g>'
    content += '<text x="30" y="484" font-size="21" font-weight="700" fill="#30271F">完整文字</text>'
    for index, (text,lane,phase,width) in enumerate(checked):
        content += f'<text x="{30+index%2*276}" y="{521+index//2*32}" font-size="20" fill="#765B45">{index+1}. {text}</text>'
    controls_y = 550 + ((len(checked)+1)//2)*32
    content += control(prefix, 'play', '开始／重播', 24, controls_y)
    content += control(prefix, 'stop', '停止定格', 312, controls_y)
    return shell(COMPONENT, config.get('title', '文字弹幕'), '短句循环移动，完整文字在下方保留', content, controls_y+80, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '文字弹幕', render, Path(__file__))
