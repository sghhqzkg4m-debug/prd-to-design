# -*- coding: utf-8 -*-
"""Render all Case journeys with the analysis template's shared component.
Usage: python3 render-journeys.py journeys.json fragment.html
Input: list of journeys (id,title,context[4],phases[{title,result,count}],
roles[{name,note}],actions[{id,title,detail,role,thinking,pain,need,idea,evidence}],
links[{from,to,label,kind?}],handoffs[{title,text}]). Text is escaped, not HTML.
"""
import sys,json,html
from pathlib import Path

def e(x): return html.escape(str(x),quote=True)
def render(j):
    acts=j['actions']; n=len(acts); prefix=j['id']; ids=[a['id'] for a in acts]
    assert len(set(ids))==n and sum(p['count'] for p in j['phases'])==n
    assert len(j['context'])==4 and all(0<=a['role']<len(j['roles']) for a in acts)
    assert all(l['from'] in ids and l['to'] in ids for l in j['links'])
    tones=[]; starts=set(); offset=0
    for i,p in enumerate(j['phases']):
        if i:starts.add(offset)
        tones.extend([i%6+1]*p['count']);offset+=p['count']
    links=[dict(l,**{'from':prefix+'-'+l['from'],'to':prefix+'-'+l['to']}) for l in j['links']]
    out=[f'<h4>{e(j["title"])}</h4><div class="journey-context">']
    labels=['产品 / 模块 · 核心用户','其他目标用户 · 场景 / 覆盖范围','起止边界 · 地图性质 / 证据状态','参与角色 / 阅读规则']
    out += [f'<div><strong>{labels[i]}</strong>{e(t)}</div>' for i,t in enumerate(j['context'])]
    out += ['</div><div class="journey-legend"><span><i></i>交接 / 依赖 →</span><span><i class="return"></i>异常返回</span></div>',f'<div class="journey-viewer" data-journey-viewer data-journey-component="1" role="region" aria-label="{e(j["title"])}旅程"><div class="journey-layer-toolbar" data-journey-controls data-target="{e(prefix)}-board" role="group" aria-label="选择旅程内容层"><button type="button" class="journey-fullscreen-button" data-journey-fullscreen aria-pressed="false">全屏查看</button><strong>显示内容</strong>']
    layers=[('doing','所做'),('thinking','所说 / 所想'),('pain','痛点'),('need','需求'),('idea','点子')]
    out += [f'<label><input type="checkbox" data-layer-toggle="{k}" checked>{v}</label>' for k,v in layers]
    out += [f'</div><div class="journey-map"><div class="journey-scroll" tabindex="0" role="region" aria-label="阶段与动作横向排列，角色和体验维度纵向排列"><div class="journey-board" id="{e(prefix)}-board" data-action-count="{n}" style="--journey-cols:{n}"><div class="journey-row head phase"><div class="journey-cell">阶段 →<small>阶段宽度取决于动作数量</small></div>']
    out += [f'<div class="journey-cell stage-tone-{i%6+1}" style="grid-column:span {p["count"]}">{e(p["title"])}<small>{e(p["result"])}</small></div>' for i,p in enumerate(j['phases'])]
    out += ['</div><div class="journey-row head substage"><div class="journey-cell">动作列 →<small>动作、体验与证据逐列对齐</small></div>']
    out += [f'<div class="journey-cell stage-tone-{tones[i]} {"phase-start" if i in starts else ""}">{e(a["id"])} · {e(a["title"])}</div>' for i,a in enumerate(acts)]
    out += [f'</div><div class="journey-band" data-journey-layer="doing"><strong>多角色协作泳道 / 用户所做</strong><span>目标方案草案；现状证据见下方断点与证据行</span></div><div class="journey-flow" data-journey-layer="doing" data-journey-links="{e(json.dumps(links,ensure_ascii=False))}"><svg class="journey-edges" aria-hidden="true"></svg>']
    for r,role in enumerate(j['roles']):
        out += [f'<div class="journey-row journey-role {["user","role-a","role-b"][r%3]}"><div class="journey-role-label"><strong>{e(role["name"])}</strong><small>{e(role["note"])}</small></div>']
        for i,a in enumerate(acts):
            content=f'<div class="journey-node" id="{e(prefix)}-{e(a["id"])}"><strong><span class="action-id">{e(a["id"])}</span>{e(a["title"])}</strong>{e(a["detail"])}</div>' if a['role']==r else '<span class="journey-empty">—</span>'
            out += [f'<div class="{"phase-start" if i in starts else ""}">{content}</div>']
        out += ['</div>']
    out += ['<div class="journey-flow-note">实线为任务依赖与交接；虚线为失败返回。具体交接条件见图下说明。</div></div>']
    for k,label,cls in [('thinking','所说所想 / 疑问（推断）','thought'),('pain','现状断点 / 关键时刻','pain'),('need','用户需求','need'),('idea','设计点子 / 优先级与责任','idea'),('evidence','衡量与证据','evidence')]:
        out += [f'<div class="journey-row {cls}" data-journey-layer="{k}"><div class="journey-cell">{label}</div>']
        out += [f'<div class="journey-cell {"phase-start" if i in starts else ""}"><strong>{e(a["id"])}</strong>{e(a[k])}</div>' for i,a in enumerate(acts)]
        out += ['</div>']
    out += ['</div></div><div class="journey-handoffs">']
    out += [f'<div><strong>{e(h["title"])}</strong>{e(h["text"])}</div>' for h in j['handoffs']]
    out += ['</div></div></div>']
    return '\n'.join(out)

if __name__=='__main__':
    journeys=json.loads(Path(sys.argv[1]).read_text())
    assert len({j['id'] for j in journeys})==len(journeys), 'Journey IDs must be unique'
    Path(sys.argv[2]).write_text('\n'.join(render(j) for j in journeys))
