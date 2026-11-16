"""Generate a role-based swimlane with selectable handoff details."""
from pathlib import Path
from component_support import color, control, items, label, run, shell, text_nodes, wrap

COMPONENT = 'wechat-svg-swimlane'


def render(config, prefix):
    roles = items(config.get('roles'), 'roles', 2, 4)
    steps = items(config.get('steps'), 'steps', 3, 6)
    names = [role.get('name') for role in roles]
    safe_names = [label(name, f'roles[{index}].name', 6) for index,name in enumerate(names)]
    if len(set(names)) != len(names):
        raise ValueError('角色名称需要互不重复')
    checked = []
    for index, step in enumerate(steps):
        if step.get('role') not in names:
            raise ValueError(f'steps[{index}].role需要对应已有角色')
        checked.append((names.index(step['role']), label(step.get('label'), f'steps[{index}].label', 6), wrap(step.get('note'), f'steps[{index}].note', 23, 2)))
    accent = color(config.get('accent', '#A94B21'), 'accent')
    background = color(config.get('background', '#FAF6ED'), 'background')
    column_width = 552 / len(roles)
    node_font = 17 if len(roles) == 4 else 20
    graph_bottom = 180 + len(steps)*82
    content = f'<defs><marker id="{prefix}_arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="none" stroke="#A78E70" stroke-width="1.5"/></marker></defs>'
    for index, name in enumerate(safe_names):
        x = 24 + column_width*index
        content += f'<rect x="{x:g}" y="116" width="{column_width:g}" height="{graph_bottom-116:g}" fill="{accent}" fill-opacity="{.045 if index%2 else .085}"/><text x="{x+column_width/2:g}" y="150" text-anchor="middle" font-size="20" font-weight="700" fill="{accent}">{name}</text>'
    for index in range(len(checked)-1):
        current_x = 24 + column_width*(checked[index][0]+.5)
        next_x = 24 + column_width*(checked[index+1][0]+.5)
        y = 180 + index*82
        content += f'<path d="M{current_x:g} {y+51}V{y+66}H{next_x:g}V{y+78}" fill="none" stroke="#A78E70" stroke-width="1.7" marker-end="url(#{prefix}_arrow)"/>'
    for index, (role_index, name, note) in enumerate(checked):
        center_x = 24 + column_width*(role_index+.5)
        y = 180 + index*82
        other_events = ';'.join(f'{prefix}_step_{other}.click' for other in range(len(checked)) if other != index)
        fill = '#F0D2B1' if index == 0 else '#FFFDF6'
        reset_fill = fill
        content += f'<g id="{prefix}_step_{index}" data-action="step" data-step="{index}" style="cursor:pointer"><rect x="{center_x-column_width/2+8:g}" y="{y}" width="{column_width-16:g}" height="52" rx="9" fill="{fill}" stroke="#CFB89C"><set attributeName="fill" to="#F0D2B1" begin="{prefix}_step_{index}.click" fill="freeze"/><set attributeName="fill" to="#FFFDF6" begin="{other_events}" fill="freeze"/><set attributeName="fill" to="{reset_fill}" begin="{prefix}_reset.click" fill="freeze"/></rect><text x="{center_x:g}" y="{y+33}" text-anchor="middle" font-size="{node_font}" fill="#30271F" pointer-events="none">{index+1}. {name}</text></g>'
        detail_y = graph_bottom + 18
        visible = 'visible' if index == 0 else 'hidden'
        reset_visible = visible
        note_text = text_nodes(note, 42, detail_y+66, 21, '#30271F', spacing=31)
        content += f'<g data-state="step-{index}" visibility="{visible}"><set attributeName="visibility" to="visible" begin="{prefix}_step_{index}.click" fill="freeze"/><set attributeName="visibility" to="hidden" begin="{other_events}" fill="freeze"/><set attributeName="visibility" to="{reset_visible}" begin="{prefix}_reset.click" fill="freeze"/><rect x="24" y="{detail_y}" width="552" height="122" rx="10" fill="#FFF9EF" stroke="#CFB89C"/><text x="42" y="{detail_y+30}" font-size="22" font-weight="700" fill="{accent}">第{index+1}步 · {safe_names[role_index]}</text>{note_text}</g>'
    controls_y = graph_bottom + 158
    content += control(prefix, 'reset', '回到第一步', 30, controls_y, 540)
    return shell(COMPONENT, config.get('title', '角色泳道'), '按角色看交接，点击节点查看职责说明', content, controls_y+82, accent, background)


if __name__ == '__main__':
    run(COMPONENT, '角色泳道', render, Path(__file__))
