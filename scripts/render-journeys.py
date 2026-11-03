# -*- coding: utf-8 -*-
"""Render shared journey components. Text is escaped; rich cells use structured data.
Usage: python3 render-journeys.py journeys.json fragment.html
Journey: id,title,context[4],phases[{title,result,count}],roles[{name,note}],
actions[{id,title,detail,role,thinking,pain,need,idea,evidence}],links,handoffs.
Cell strings remain supported. Rich cells: thinking{text,status};
pain{text,status,critical}; need{text}; idea{title,priority,detail,owner};
evidence{metric,status,detail}. type is current or target. Target actions use
experience{text}, design{text,detail}, metrics{metric,status,detail}; target maps
show these three rows and never relabel current pain as future experience.
"""
import sys,json,html
from pathlib import Path

def e(x): return html.escape(str(x),quote=True)
def badge(text,kind='pending'):
    return f'<span class="journey-badge {e(kind)}">{e(text)}</span>' if text else ''
def cell(a,key):
    v=a.get(key,''); v={'text':v} if isinstance(v,str) else v
    text=v.get('text','')
    if key=='thinking':
        status=v.get('status','推断' if text.startswith('推断') else '')
        if status=='推断': text=text.removeprefix('推断：').removeprefix('推断:')
        return badge(status,'inferred' if status=='推断' else 'material')+e(text)
    if key=='pain':return badge(v.get('status',''),'material' if v.get('status')=='材料' else ('low' if v.get('status')=='方案假设' else 'pending'))+e(text)
    if key=='need':return f'<span class="journey-inline-id">{e(a["id"])}</span> '+e(text)
    if key=='idea':
        priority=v.get('priority',''); kind={'高':'high','中':'medium','低':'low'}.get(priority,'pending')
        title=v.get('title',text)
        detail=v.get('detail','')
        owner=v.get('owner','责任待确认')
        return f'<div class="journey-idea-title">{badge(priority,kind)}{e(title)}</div><small>{e(detail)}{("；" if detail else "")}对应 {e(a["id"])} · {e(owner)}</small>'
    if key in ('evidence','metrics'):
        return e(v.get('metric',text))+' '+badge(v.get('status',''),'material' if v.get('status')=='材料' else ('inferred' if v.get('status')=='推断' else 'pending'))+(f'<small>{e(v["detail"])}</small>' if v.get('detail') else '')
    return e(text)+(f'<small>{e(v["detail"])}</small>' if v.get('detail') else '')
def render(j):
    kind=j.get('type', 'target' if '目标' in j.get('nature','') else 'current')
    assert kind in ('current','target'), 'Journey type must be current or target'
    target=kind=='target'
    acts=j['actions']; n=len(acts); prefix=j['id']; ids=[a['id'] for a in acts]
    assert n and len(set(ids))==n and sum(p['count'] for p in j['phases'])==n
    if target: assert all(all(key in a for key in ('experience','design','metrics')) for a in acts), 'Target actions require experience, design and metrics'
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
    out += ['</div><div class="journey-legend"><span><i></i>交接 / 依赖 →</span><span><i class="return"></i>异常返回</span></div>',f'<div class="journey-viewer" data-journey-viewer data-journey-component="1" data-journey-type="{kind}" role="region" aria-label="{e(j["title"])}旅程"><div class="journey-layer-toolbar" data-journey-controls data-target="{e(prefix)}-board" role="group" aria-label="选择旅程内容层"><button type="button" class="journey-fullscreen-button" data-journey-fullscreen aria-pressed="false">全屏查看</button><strong>显示内容</strong>']
    layers=([('doing','所做'),('experience','目标体验'),('design','支持设计'),('metrics','验证指标')] if target else [('doing','所做'),('thinking','所说 / 所想'),('pain','痛点'),('need','需求'),('idea','点子')])
    out += [f'<label><input type="checkbox" data-layer-toggle="{k}" checked>{v}</label>' for k,v in layers]
    out += [f'</div><div class="journey-map"><div class="journey-scroll" tabindex="0" role="region" aria-label="阶段与动作横向排列，角色和体验维度纵向排列"><div class="journey-board" id="{e(prefix)}-board" data-action-count="{n}" style="--journey-cols:{n}"><div class="journey-row head phase"><div class="journey-cell">阶段 →<small>业务阶段 / 关键结果</small></div>']
    out += [f'<div class="journey-cell stage-tone-{i%6+1}" style="grid-column:span {p["count"]}">{e(p["title"])}<small>{e(p["result"])}</small></div>' for i,p in enumerate(j['phases'])]
    out += ['</div><div class="journey-row head substage"><div class="journey-cell">动作列 →<small>动作、体验与证据逐列对齐</small></div>']
    out += [f'<div class="journey-cell stage-tone-{tones[i]} {"phase-start" if i in starts else ""}">{e(a["id"])} · {e(a["title"])}</div>' for i,a in enumerate(acts)]
    out += [f'</div><div class="journey-band" data-journey-layer="doing"><strong>多角色协作泳道 / 用户所做</strong><span>{e(j.get("nature","目标方案草案；现状证据见断点与证据行"))}</span></div><div class="journey-flow" data-journey-layer="doing" data-journey-links="{e(json.dumps(links,ensure_ascii=False))}"><svg class="journey-edges" aria-hidden="true"></svg>']
    for r,role in enumerate(j['roles']):
        out += [f'<div class="journey-row journey-role {["user","role-a","role-b"][r%3]}"><div class="journey-role-label"><strong>{e(role["name"])}</strong><small>{e(role["note"])}</small></div>']
        for i,a in enumerate(acts):
            content=f'<div class="journey-node" id="{e(prefix)}-{e(a["id"])}"><strong><span class="action-id">{e(a["id"])}</span>{e(a["title"])}</strong>{e(a["detail"])}</div>' if a['role']==r else '<span class="journey-empty">—</span>'
            out += [f'<div class="{"phase-start" if i in starts else ""}">{content}</div>']
        out += ['</div>']
    out += ['<div class="journey-flow-note">实线为任务依赖与交接；虚线为失败返回。交接条件见图下说明。</div></div>']
    rows=[('thinking','所说 / 所想','无访谈证据处标「推断」','thought'),('pain','现状断点','阻碍 / 负担 / 不确定性','pain'),('need','用户需求','期望能力，不写控件','need'),('idea','设计点子','方案假设，非本期承诺','idea'),('evidence','衡量与证据','无基线不填目标数字','evidence')]
    if target:
        rows=[('experience','目标体验','业务改善，非界面描述','target-experience'),('design','支持设计','对应现状需求与点子','target-design'),('metrics','验证指标','口径与验证方式','target-metrics')]
    for k,label,hint,cls in rows:
        out += [f'<div class="journey-row {cls}" data-journey-layer="{k}"><div class="journey-cell">{label}<small>{hint}</small></div>']
        for i,a in enumerate(acts):
            value=a.get(k,{})
            critical=k=='pain' and isinstance(value,dict) and value.get('critical')
            out += [f'<div class="journey-cell {"phase-start" if i in starts else ""} {"is-critical" if critical else ""}" data-action-ref="{e(a["id"])}">{cell(a,k)}</div>']
        out += ['</div>']
    out += ['</div></div><div class="journey-handoffs">']
    out += [f'<div><strong>{e(h["title"])}</strong>{e(h["text"])}</div>' for h in j['handoffs']]
    out += ['</div></div></div>']
    return '\n'.join(out)
if __name__=='__main__':
    journeys=json.loads(Path(sys.argv[1]).read_text())
    assert len({j['id'] for j in journeys})==len(journeys), 'Journey IDs must be unique'
    Path(sys.argv[2]).write_text('\n'.join(render(j) for j in journeys))
