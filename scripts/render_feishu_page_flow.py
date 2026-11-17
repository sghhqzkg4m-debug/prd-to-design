# -*- coding: utf-8 -*-
"""Render a Case's page flow as an editable Feishu whiteboard SVG.

Usage: python3 render_feishu_page_flow.py flows.json 0 output.svg
Input is a JSON object or array; schema is in references/feishu-page-flow-template.md.
The template fixes visual semantics, not roles, pages, step count, or phase count.
"""
import json
import re
import sys
from html import escape
from pathlib import Path

INK = '#28475f'
BODY = '#537087'
MUTED = '#7790a3'
EDGE = '#d8e6ef'
BLUE = '#5f89ab'
GOLD = '#b17a27'
ROLE = ('#3675bc', '#159b80', '#6682aa', '#ad8145')
LANE = ('#f1f7fc', '#f2faf7', '#f6f8fc', '#fbf8f1')
PHASE = ('#e8f1ff', '#e7f7f2', '#f0f5e9', '#f4f0fa')


def e(value):
    return escape(str(value), quote=True)


def rect(x, y, w, h, fill, stroke='none', radius=9, sw=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def text(x, y, value, size=16, color=BODY, weight='normal'):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}">{e(value)}</text>'


def width_units(value):
    return sum(1 if ord(ch) > 255 else .58 for ch in str(value))


def wrap(value, limit=19, max_lines=2):
    value = re.sub(r'\s+', ' ', str(value)).strip()
    lines = []
    while value and len(lines) < max_lines:
        if width_units(value) <= limit:
            lines.append(value)
            value = ''
            break
        used = 0
        cut = 0
        for i, ch in enumerate(value):
            used += 1 if ord(ch) > 255 else .58
            if used > limit:
                break
            cut = i + 1
        cut = max(1, cut)
        lines.append(value[:cut])
        value = value[cut:].lstrip()
    if value and lines:
        lines[-1] = lines[-1].rstrip('，；、 ') + '…'
    return lines


def validate(flow):
    roles = flow['roles']
    steps = flow['steps']
    if not 1 <= len(roles) <= 5:
        raise ValueError('Use 1–5 role lanes; split larger tasks into related flows')
    if not 2 <= len(steps) <= 8:
        raise ValueError('Use 2–8 steps per board; split larger tasks into related flows')
    ids = [step['id'] for step in steps]
    if len(set(ids)) != len(ids):
        raise ValueError('Step IDs must be unique')
    for step in steps:
        if not 0 <= int(step['role']) < len(roles):
            raise ValueError(f'Invalid role for {step["id"]}')
        if not step.get('page') or not step.get('title'):
            raise ValueError(f'{step["id"]} requires page and title')
        if '－' not in step['page'] and '-' not in step['page']:
            raise ValueError(f'{step["id"]} page must name platform and page: 平台－页面')
    phases = flow.get('phases', [])
    if phases and sum(int(p['count']) for p in phases) != len(steps):
        raise ValueError('Phase spans must equal the number of steps')
    for link in flow.get('links', []):
        if link['from'] not in ids or link['to'] not in ids:
            raise ValueError('Link endpoint is missing')
        kind = link.get('kind', 'main')
        if kind not in ('main', 'return'):
            raise ValueError('Link kind must be main or return')
        source, target = ids.index(link['from']), ids.index(link['to'])
        if kind == 'main' and target != source + 1:
            raise ValueError('Main links must connect adjacent steps; arrange branches separately')
        if kind == 'return' and target >= source:
            raise ValueError('Return links must lead to an earlier step')


def render(flow):
    validate(flow)
    roles, steps = flow['roles'], flow['steps']
    n = len(steps)
    left, col, card_w = 230, 350, 292
    width = left + col*n + 25
    phase_y = 115
    phase_h = 78 if flow.get('phases') else 0
    lane_top = phase_y + phase_h + 16
    lane_h, card_h = 244, 180
    lane_bottom = lane_top + len(roles)*lane_h
    links = flow.get('links', [])
    returns = [link for link in links if link.get('kind') == 'return']
    return_top = lane_bottom + 38
    route_bottom = return_top + max(1, len(returns))*40
    notes = [link for link in links if link.get('label')]
    note_top = route_bottom + 22
    note_rows = (len(notes)+1)//2
    height = note_top + 48 + note_rows*75 + 32
    out = [rect(12, 12, width-24, height-24, '#f8fbfd', '#e8f0f5', 20),
           text(42, 55, flow['title'], 30, INK, 'bold'),
           text(42, 85, flow.get('boundary', ''), 16, MUTED)]
    if flow.get('phases'):
        out.extend((rect(28, phase_y, left-42, phase_h, '#e8f2fa', EDGE, 5),
                    text(46, phase_y+38, '流程阶段', 19, INK, 'bold')))
        offset = 0
        for i, phase in enumerate(flow['phases']):
            x, w = left + offset*col, col*int(phase['count'])-3
            out.extend((rect(x, phase_y, w, phase_h, PHASE[i % len(PHASE)], EDGE, 5),
                        text(x+16, phase_y+32, phase['title'], 19, INK, 'bold'),
                        text(x+16, phase_y+60, phase.get('result', ''), 14, MUTED)))
            offset += int(phase['count'])
    for i, role in enumerate(roles):
        y = lane_top+i*lane_h
        out.extend((rect(28, y, width-56, lane_h-3, LANE[i % len(LANE)], EDGE, 9),
                    text(46, y+38, role['name'], 19, ROLE[i % len(ROLE)], 'bold')))
        if role.get('note'):
            out.append(text(46, y+65, role['note'], 13, MUTED))
        for j in range(1, n):
            x = left+j*col-12
            out.append(f'<line x1="{x}" y1="{y+3}" x2="{x}" y2="{y+lane_h-6}" stroke="#dce7ee" stroke-width="1"/>')
    nodes = {}
    for i, step in enumerate(steps):
        x = left+i*col+16
        y = lane_top+int(step['role'])*lane_h+40
        nodes[step['id']] = (x, y, card_w, card_h)
    # Draw dependencies first, so cards always remain on top.
    for link in links:
        if link.get('kind', 'main') != 'main':
            continue
        sx, sy, sw, sh = nodes[link['from']]
        tx, ty, tw, th = nodes[link['to']]
        y1, y2 = sy+sh/2, ty+th/2
        gutter = (sx+sw+tx)/2
        path = f'M{sx+sw} {y1}H{gutter}V{y2}H{tx-3}' if y1 != y2 else f'M{sx+sw} {y1}H{tx-3}'
        out.append(f'<path d="{path}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
        out.append(f'<path d="M{tx-12} {y2-7}L{tx-2} {y2}L{tx-12} {y2+7}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
    for i, link in enumerate(returns):
        sx, sy, sw, sh = nodes[link['from']]
        tx, ty, tw, th = nodes[link['to']]
        x1, x2 = sx+sw/2, tx+tw/2
        channel = return_top+i*40
        out.append(f'<path d="M{x1} {sy+sh}V{channel}H{x2}V{ty+sh+6}" fill="none" stroke="{GOLD}" stroke-width="2.5" stroke-dasharray="8 6"/>')
        out.append(f'<path d="M{x2-7} {ty+sh+16}L{x2} {ty+sh+5}L{x2+7} {ty+sh+16}" fill="none" stroke="{GOLD}" stroke-width="2.5"/>')
    for i, step in enumerate(steps):
        x, y, w, h = nodes[step['id']]
        accent = ROLE[int(step['role']) % len(ROLE)]
        out.extend((rect(x, y, w, h, '#ffffff', '#c9dce9', 12, 1.7),
                    rect(x, y, 7, h, accent, accent, 0, 0)))
        page_lines = wrap(step['page'], 24, 2)
        for k, line in enumerate(page_lines):
            out.append(text(x+18, y+28+k*19, line, 13, MUTED))
        title_y = y+77 if len(page_lines) > 1 else y+65
        out.append(text(x+18, title_y, f'{step["id"]}  {step["title"]}', 17, INK, 'bold'))
        details = step.get('detail', [])
        if isinstance(details, str):
            details = [details]
        detail_lines = []
        for detail in details:
            detail_lines.extend(wrap(detail, 20, 2))
        for k, line in enumerate(detail_lines[:3]):
            out.append(text(x+18, title_y+27+k*20, line, 13, BODY))
        if step.get('feedback'):
            out.append(text(x+18, y+h-13, wrap(step['feedback'], 23, 1)[0], 12, GOLD))
    if notes:
        out.append(text(42, note_top+21, '交接与异常返回', 18, INK, 'bold'))
        for i, link in enumerate(notes):
            row, side = divmod(i, 2)
            w = (width-95)/2
            x, y = 28+side*(w+15), note_top+38+row*75
            is_return = link.get('kind') == 'return'
            out.append(rect(x, y, w, 63, '#fff7ec' if is_return else '#eef6fb', '#ead3ae' if is_return else EDGE, 8))
            label = f'{link["from"]} → {link["to"]}  {link["label"]}'
            for k, line in enumerate(wrap(label, 45, 2)):
                out.append(text(x+14, y+25+k*22, line, 14, GOLD if is_return else BODY))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n' + '\n'.join(out) + '\n</svg>'


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    flow = data[int(sys.argv[2])] if isinstance(data, list) else data
    Path(sys.argv[3]).write_text(render(flow), encoding='utf-8')
