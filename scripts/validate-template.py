# -*- coding: utf-8 -*-
"""Compare a generated analysis document with its template and validate every journey.
Usage: python3 validate-template.py document.html [template.html]
"""
from html.parser import HTMLParser
from pathlib import Path
import re,json,sys
class Node:
    def __init__(self,tag='',attrs=(),parent=None):self.tag=tag;self.attrs=dict(attrs);self.parent=parent;self.children=[];self.text=''
    def has(self,c):return c in self.attrs.get('class','').split()
    def all(self,p):return [x for ch in self.children for x in ([ch] if p(ch) else [])+ch.all(p)]
    def content(self):return self.text+''.join(c.content() for c in self.children)
class Parser(HTMLParser):
    def __init__(self,s):super().__init__(convert_charrefs=True);self.root=Node();self.cur=self.root;self.feed(s)
    def handle_starttag(self,t,a):
        n=Node(t,a,self.cur);self.cur.children.append(n)
        if t not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:self.cur=n
    def handle_startendtag(self,t,a):self.cur.children.append(Node(t,a,self.cur))
    def handle_endtag(self,t):
        n=self.cur
        while n.parent and n.tag!=t:n=n.parent
        if n.parent:self.cur=n.parent
    def handle_data(self,d):self.cur.text+=d

def validate(file,template):
    src=file.read_text();ref=template.read_text();root=Parser(src).root;tr=Parser(ref).root;errors=[]
    def check(ok,msg):
        if not ok:errors.append(msg)
    def find(n,c):return n.all(lambda x:x.has(c))
    sections=find(root,'chapter');ts=find(tr,'chapter')
    check([n.attrs.get('id') for n in sections]==[n.attrs.get('id') for n in ts],'章节 ID 或顺序偏离模板')
    def heading_text(n):
        return re.sub(r'\s+','',n.text+''.join(c.content() for c in n.children if not c.has('chip')))
    for n,t in zip(sections,ts):
        h=n.all(lambda x:x.tag=='h2');th=t.all(lambda x:x.tag=='h2')
        check(bool(h and th) and heading_text(h[0])==heading_text(th[0]),f'{n.attrs.get("id")}: 章节标题偏离模板')
        check(bool(find(n,'chapter-head')),f'{n.attrs.get("id")}: 缺少 chapter-head')
    check(not find(root,'chip'),'成品 HTML 保留了模板的必需/可选等编辑标签')
    editorial_desc=('交代需求产生','明确谁在什么场景','有重要未知项或明确研究要求','先给出方案结论','旅程讲协作','说明用户看到什么','读者理解方案之后','把关联业务结果')
    for desc in find(root,'chapter-desc'):
        check(not desc.content().strip().startswith(editorial_desc),'成品 HTML 的章节导语仍是模板写作指令')
    for tag in ['style','script']:
        check(re.findall(fr'<{tag}>(.*?)</{tag}>',src,re.S)==re.findall(fr'<{tag}>(.*?)</{tag}>',ref,re.S),f'{tag} 与所用模板不一致；先更新模板，再同步产物')
    def toc(n):
        nav=n.all(lambda x:x.attrs.get('id')=='toc')
        return [x.attrs.get('href') for x in nav[0].all(lambda x:x.tag=='a')] if nav else []
    check(toc(root)==toc(tr),'目录锚点或顺序偏离模板')
    check(not find(root,'sidebar-note'),'成品 HTML 不应显示模板侧栏说明')
    check(not find(root,'hero-decoration'),'首页不应显示右下角装饰底图')
    check(bool(find(root,'hero-subtitle')) and '业务背景 → 用户任务 → 设计方案 → 可验证结果' not in src,'首页副标题仍是固定文案')
    core={'jobs':['job-box','case-block','case-facts','goal-chain'],'solution':['scope-row'],'pages':['process-map','wireframe-grid']}
    for n in sections:
        for c in core.get(n.attrs.get('id'),[]):check(bool(find(n,c)),f'{n.attrs.get("id")}: 缺少模板主要组件 {c}')
    benchmark=next((n for n in sections if n.attrs.get('id')=='benchmark'),None)
    if benchmark:
        tables=benchmark.all(lambda x:x.tag=='table')
        expected=['设计议题','具体竞品、参考功能与功能亮点','可参考的点']
        headers=[re.sub(r'\s+','',h.content()) for h in tables[0].all(lambda x:x.tag=='th')] if tables else []
        check(headers==expected,'benchmark: 竞品分析表须沿用模板的三列议题框架')
        details=benchmark.all(lambda x:x.tag=='details' and x.has('benchmark-detail'))
        check(len(details)==1 and 'open' not in details[0].attrs,'benchmark: 研究依据与本轮判断须合并并默认折叠')
        if tables:
            body_rows=tables[0].all(lambda x:x.tag=='tr' and x.parent and x.parent.tag=='tbody')
            for row in body_rows:
                cells=[x for x in row.children if x.tag=='td']
                if len(cells)<2:continue
                refs=find(cells[1],'benchmark-reference')
                check(bool(refs),'benchmark: 竞品单元格缺少分段结构')
                if refs:
                    labels=[re.sub(r'\s+','',x.content()) for x in refs[0].all(lambda x:x.tag=='strong')]
                    check(all(label in labels for label in ['具体竞品：','参考功能：','功能亮点：']),'benchmark: 竞品、参考功能和功能亮点须分别成段')
    ids=[n.attrs['id'] for n in root.all(lambda x:'id' in x.attrs)]
    check(len(ids)==len(set(ids)),'DOM ID 重复')
    for index,v in enumerate(root.all(lambda x:'data-journey-viewer' in x.attrs),1):
        label=f'旅程 {index}'
        for c in ['journey-layer-toolbar','journey-map','journey-scroll','journey-board','journey-flow','journey-edges','journey-handoffs']:
            check(len(find(v,c))==1,f'{label}: 必须包含一个 {c}，不能用普通表格替代')
        boards=find(v,'journey-board')
        if not boards:continue
        board=boards[0];count=int(board.attrs.get('data-action-count','0'))
        check(count>0,f'{label}: 缺少动作列数')
        check(not v.all(lambda x:x.tag=='table'),f'{label}: 旅程被降级为普通表格')
        check(bool(v.all(lambda x:'data-journey-fullscreen' in x.attrs)),f'{label}: 缺少全屏控件')
        controls=v.all(lambda x:'data-journey-controls' in x.attrs)
        check(bool(controls) and controls[0].attrs.get('data-target')==board.attrs.get('id'),f'{label}: 筛选目标不匹配')
        target=v.attrs.get('data-journey-type')=='target'
        required_layers=['doing','experience','design','metrics'] if target else ['doing','thinking','pain','need','idea']
        if target:
            check(not board.all(lambda x:x.attrs.get('data-journey-layer') in {'pain','need','idea','evidence'}),f'{label}: 目标旅程不应展示现状断点或现状需求行')
        for layer in required_layers:
            check(bool(v.all(lambda x:x.attrs.get('data-layer-toggle')==layer)),f'{label}: 缺少 {layer} 筛选')
            check(bool(board.all(lambda x:x.attrs.get('data-journey-layer')==layer)),f'{label}: 缺少 {layer} 内容层')
        phases=find(board,'phase');sub=find(board,'substage')
        check(len(phases)==1 and len(sub)==1,f'{label}: 缺少两级阶段/动作表头')
        if phases:
            total=sum(int(m.group(1)) for cell in phases[0].children for m in [re.search(r'grid-column:\s*span\s+(\d+)',cell.attrs.get('style',''))] if m)
            check(total==count,f'{label}: 阶段跨度与动作列数不一致')
        for row in find(board,'journey-row'):
            if not row.has('phase'):check(len(row.children)==count+1,f'{label}: {row.attrs.get("class")}: 行列数未对齐')
        nodes=find(board,'journey-node');nodeids={x.attrs.get('id') for x in nodes}
        check(len(nodes)==count,f'{label}: 每个动作列须有对应动作节点')
        flows=find(board,'journey-flow')
        if flows:
            try:
                links=json.loads(flows[0].attrs.get('data-journey-links','[]'))
                check(bool(links),f'{label}: 缺少交接/依赖连线')
                for l in links:check(l.get('from') in nodeids and l.get('to') in nodeids,f'{label}: 连线端点不属于本 Case')
            except ValueError:errors.append(f'{label}: 连线数据无效')
    visible=re.sub(r'<(?:script|style)>.*?</(?:script|style)>','',src,flags=re.S)
    visible=re.sub(r'<!--.*?-->','',visible,flags=re.S)
    visible=re.sub(r'<[^>]+>','',visible)
    check(not re.search(r'\[[^\]\n]*[\u4e00-\u9fff][^\]\n]*\]',visible),'仍有可见模板占位文案')
    return errors
if __name__=='__main__':
    file=Path(sys.argv[1]);template=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).resolve().parent.parent/'assets/sangfor-feishu-analysis-template.html'
    errors=validate(file,template);print(json.dumps(dict(ok=not errors,file=str(file),errors=errors),ensure_ascii=False,indent=2));sys.exit(bool(errors))
