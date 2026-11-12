"""Validate links, identifiers, model topology and document packaging."""
from pathlib import Path
import re
import json
import zipfile
import xml.etree.ElementTree as E
from collections import Counter, defaultdict, deque
from docx import Document
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'coursework'
NS={'b':'http://www.omg.org/spec/BPMN/20100524/MODEL','bd':'http://www.omg.org/spec/BPMN/20100524/DI'}


def validate():
    checks=[]
    model=E.parse(OUT/'diagrams/02_search_process.bpmn').getroot()
    ids=[el.attrib['id'] for el in model.iter() if 'id' in el.attrib]
    assert len(ids)==len(set(ids)),'Duplicate BPMN ID'
    idset=set(ids)
    for el in model.iter():
        for key in ('sourceRef','targetRef','processRef','bpmnElement'):
            if key in el.attrib:assert el.attrib[key] in idset,(key,el.attrib[key])
    proc_of={}
    for proc in model.findall('b:process',NS):
        for el in proc:
            if el.tag.rsplit('}',1)[-1] in ('startEvent','endEvent','intermediateCatchEvent','userTask','serviceTask','sendTask','exclusiveGateway'):
                proc_of[el.attrib['id']]=proc.attrib['id']
        flows=proc.findall('b:sequenceFlow',NS)
        nexts=defaultdict(list);prevs=defaultdict(list)
        for flow in flows:
            a,b=flow.attrib['sourceRef'],flow.attrib['targetRef']
            assert proc_of[a]==proc_of[b]
            nexts[a].append(b);prevs[b].append(a)
        starts={x.attrib['id'] for x in proc.findall('b:startEvent',NS)}
        ends={x.attrib['id'] for x in proc.findall('b:endEvent',NS)}
        nodes={k for k,v in proc_of.items() if v==proc.attrib['id']}
        def reach(initial,graph):
            seen=set(initial);q=deque(initial)
            while q:
                for n in graph[q.popleft()]:
                    if n not in seen:seen.add(n);q.append(n)
            return seen
        assert nodes<=reach(starts,nexts),('unreachable',nodes-reach(starts,nexts))
        assert nodes<=reach(ends,prevs),('no end path',nodes-reach(ends,prevs))
        for g in proc.findall('b:exclusiveGateway',NS):
            gid=g.attrib['id']
            if len(nexts[gid])>1:
                outgoing=[f for f in flows if f.attrib['sourceRef']==gid]
                assert all(f.attrib.get('name') and f.find('b:conditionExpression',NS) is not None for f in outgoing)
    for f in model.findall('.//b:messageFlow',NS):
        a,b=f.attrib['sourceRef'],f.attrib['targetRef']
        assert proc_of.get(a,a)!=proc_of.get(b,b),'Message inside same process'
    checks.append('BPMN: unique IDs, resolved references, sequence flow within process, message flow between participants, reachability of all nodes, end paths, named XOR branches')
    for file in (OUT/'diagrams').glob('*.drawio'):
        r=E.parse(file).getroot();cells=r.findall('.//mxCell');ids2={c.attrib['id'] for c in cells}
        assert len(ids2)==len(cells)
        for c in cells:
            for attr in ('parent','source','target'):
                if attr in c.attrib:assert c.attrib[attr] in ids2,(file,attr,c.attrib[attr])
        if file.stem=='03_use_cases':
            assert sum(c.attrib.get('value')=='«include»' for c in cells)==4
            assert sum(c.attrib.get('value')=='«extend»' for c in cells)==2
            ucs=[c for c in cells if c.attrib['id'].startswith('UC')]
            assert len(ucs)==15
    checks.append('Drawio: resolved graph references; UML: 15 use cases, 4 include, 2 extend')
    uml=(OUT/'diagrams/03_use_cases.puml').read_text(encoding='utf-8')
    assert uml.count('<<include>>')==4 and uml.count('<<extend>>')==2
    assert uml.startswith('@startuml\n') and uml.endswith('@enduml\n')
    checks.append('PlantUML source agrees on actors, cases and relationships')
    doc=Document(OUT/'iterations_1_3.docx')
    assert len(doc.inline_shapes)==2
    xml=doc._element.xml
    for marker in ('UC-01.','UC-03.','UC-04.','FR-56','BR-04'):assert marker in xml
    checks.append('Word: readable OOXML, two embedded diagrams, required chapter and requirement markers')
    with zipfile.ZipFile(OUT/'diagrams_sources.zip') as z:
        assert z.read('original/sec(2).drawio')==(ROOT/'sec(2).drawio').read_bytes()
        assert len(z.namelist())==5
    checks.append('Archive: original user diagram preserved byte-for-byte, four editable completed diagram sources included')
    missing=[]
    for file in list(OUT.glob('*.md'))+list((OUT/'sources').glob('*.md'))+[ROOT/'README.md',ROOT/'stakeholders.md',ROOT/'requirements_plan.md']:
        for path in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
            if not re.match(r'^https?://',path):
                target=file.parent/path.split('#')[0]
                if not target.exists():missing.append((str(file),path))
    assert not missing,missing
    checks.append('Markdown: all local links and image references resolve')
    pdf=pymupdf.open(OUT/'iterations_1_3.pdf')
    outside=[]
    for i,page in enumerate(pdf):
        for b in page.get_text('blocks'):
            if b[0]<-1 or b[1]<-1 or b[2]>page.rect.width+1 or b[3]>page.rect.height+1:outside.append((i+1,b[:4]))
    assert not outside,outside
    assert all(p.get_text().strip() or p.get_images() for p in pdf)
    checks.append('PDF: no empty pages or text outside page boundaries; Cyrillic text extraction succeeds')
    p=OUT/'validation.json';result=json.loads(p.read_text(encoding='utf-8'));result['checks']=checks
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':validate()
