"""Editable diagrams and vector/PDF previews from one layout model."""
from pathlib import Path
import math
import textwrap
import xml.etree.ElementTree as E
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'coursework' / 'diagrams'
OUT.mkdir(parents=True, exist_ok=True)
FONTDIR = Path('C:/Windows/Fonts')
for name, file in [('Arial', 'arial.ttf'), ('Arial-Bold', 'arialbd.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONTDIR / file)))


class Drawing:
    def __init__(self, name, width, height, title):
        self.name, self.w, self.h = name, width, height
        self.nodes, self.edges, self.notes = [], [], []
        self.title = title

    def node(self, id, kind, x, y, w, h, text='', parent='1', color='#ffffff'):
        n = dict(id=id, kind=kind, x=x, y=y, w=w, h=h, text=text, parent=parent, color=color)
        self.nodes.append(n)
        return n

    def edge(self, id, source, target, points, kind='sequence', label='', label_at=None):
        self.edges.append(dict(id=id, source=source, target=target, points=points,
                               kind=kind, label=label, label_at=label_at))

    def note(self, x, y, text, size=15):
        self.notes.append((x, y, text, size))

    def export(self):
        self.drawio()
        self.pdf()

    def drawio(self):
        root = E.Element('mxfile', host='app.diagrams.net')
        page = E.SubElement(root, 'diagram', id=self.name, name=self.title)
        model = E.SubElement(page, 'mxGraphModel', page='1', pageWidth=str(self.w),
                             pageHeight=str(self.h), grid='1', gridSize='10')
        cells = E.SubElement(model, 'root')
        E.SubElement(cells, 'mxCell', id='0')
        E.SubElement(cells, 'mxCell', id='1', parent='0')
        lookup = {n['id']: n for n in self.nodes}
        title = E.SubElement(cells, 'mxCell', id='title', parent='1', vertex='1',
                             value=self.title, style='text;html=0;fontSize=25;fontStyle=1;align=left;')
        E.SubElement(title, 'mxGeometry', x='50', y='22', width=str(self.w-100), height='45', **{'as':'geometry'})
        for n in self.nodes:
            kind=n['kind']
            style = f'whiteSpace=wrap;html=0;fontFamily=Arial;fontSize=17;fillColor={n["color"]};strokeColor=#23364d;'
            if kind in ('pool','lane','blackbox'):
                style += 'swimlane;horizontal=0;startSize=42;fontStyle=1;'
                if kind=='blackbox': style += 'startSize=0;'
            elif kind in ('start','end','catch','message_start'):
                style += ('shape=doubleEllipse;' if kind=='catch' else 'ellipse;')
                style += 'aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;labelBackgroundColor=#ffffff;'
                if kind=='end': style+='strokeWidth=4;'
            elif kind=='gateway':
                style += 'rhombus;verticalLabelPosition=top;verticalAlign=bottom;'
            elif kind=='uc': style+='ellipse;'
            elif kind=='actor': style+='shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;'
            elif kind=='boundary': style+='rounded=0;verticalAlign=top;fontStyle=1;align=left;spacingTop=10;spacingLeft=10;'
            else: style+='rounded=1;arcSize=15;'
            value=n['text']
            cell=E.SubElement(cells, 'mxCell', id=n['id'], parent=n['parent'], vertex='1', value=value, style=style)
            px=lookup[n['parent']]['x'] if n['parent'] in lookup else 0
            py=lookup[n['parent']]['y'] if n['parent'] in lookup else 0
            E.SubElement(cell, 'mxGeometry', x=str(n['x']-px), y=str(n['y']-py), width=str(n['w']),height=str(n['h']), **{'as':'geometry'})
            if kind in ('message_start','catch'):
                icon=E.SubElement(cells,'mxCell',id=n['id']+'_icon',parent=n['id'],vertex='1',value='',
                                  style='shape=message;fillColor=#ffffff;strokeColor=#23364d;')
                E.SubElement(icon,'mxGeometry',x=str(n['w']*.25),y=str(n['h']*.31),width=str(n['w']*.5),height=str(n['h']*.36),**{'as':'geometry'})
            if kind=='gateway':
                icon=E.SubElement(cells,'mxCell',id=n['id']+'_x',parent=n['id'],vertex='1',value='×',style='text;fontSize=25;align=center;verticalAlign=middle;')
                E.SubElement(icon,'mxGeometry',x='10',y='8',width=str(n['w']-20),height=str(n['h']-16),**{'as':'geometry'})
        for ed in self.edges:
            style='edgeStyle=none;rounded=0;html=0;fontSize=15;labelBackgroundColor=#ffffff;strokeColor=#23364d;'
            k=ed['kind']
            if k=='message': style+='dashed=1;startArrow=oval;startFill=0;endArrow=open;endFill=0;'
            elif k in ('include','extend'): style+='dashed=1;endArrow=open;endFill=0;'
            elif k=='association': style+='endArrow=none;'
            elif k=='generalization': style+='endArrow=block;endFill=0;endSize=16;'
            else: style+='endArrow=block;endFill=1;'
            # Explicit perimeter anchors preserve the same routing as the PDF.
            a,b=lookup[ed['source']],lookup[ed['target']]
            p,q=ed['points'][0],ed['points'][-1]
            for prefix,n,pt in [('exit',a,p),('entry',b,q)]:
                style+=f'{prefix}X={(pt[0]-n["x"])/n["w"]:.6f};{prefix}Y={(pt[1]-n["y"])/n["h"]:.6f};{prefix}Dx=0;{prefix}Dy=0;'
            cell=E.SubElement(cells,'mxCell',id=ed['id'],parent='1',edge='1',source=ed['source'],target=ed['target'],value=ed['label'],style=style)
            geo=E.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
            if ed['points'][1:-1]:
                arr=E.SubElement(geo,'Array',**{'as':'points'})
                for x,y in ed['points'][1:-1]: E.SubElement(arr,'mxPoint',x=str(x),y=str(y))
        for idx,(x,y,txt,size) in enumerate(self.notes):
            c=E.SubElement(cells,'mxCell',id=f'note_{idx}',parent='1',vertex='1',value=txt,style=f'text;whiteSpace=wrap;html=0;align=left;fontSize={size};')
            E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(self.w-x-45),height='55',**{'as':'geometry'})
        E.indent(root)
        E.ElementTree(root).write(OUT/(self.name+'.drawio'),encoding='utf-8',xml_declaration=True)

    def pdf(self):
        c=canvas.Canvas(str(OUT/(self.name+'.pdf')),pagesize=(self.w,self.h))
        c.setTitle(self.title)
        c.setAuthor('Учебный проект: агрегатор оценок шавермы')
        def line(points, dash=None, width=1.8, color='#23364d'):
            c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.setDash(dash or [])
            p=c.beginPath();p.moveTo(points[0][0],self.h-points[0][1])
            for x,y in points[1:]:p.lineTo(x,self.h-y)
            c.drawPath(p)
            c.setDash([])
        def text(x,y,txt,size=17,bold=False,align='center',wrap_width=None):
            lines=[]
            for t in txt.split('\n'):
                if wrap_width:
                    words=t.split(); cur=''
                    for word in words:
                        trial=(cur+' '+word).strip()
                        if pdfmetrics.stringWidth(trial,'Arial-Bold' if bold else 'Arial',size)>wrap_width and cur:
                            lines.append(cur);cur=word
                        else:cur=trial
                    lines.append(cur)
                else:lines.append(t)
            c.setFont('Arial-Bold' if bold else 'Arial',size);c.setFillColor(HexColor('#172e46'))
            for i,t in enumerate(lines):
                yy=self.h-y-i*size*1.22
                if align=='center':c.drawCentredString(x,yy,t)
                else:c.drawString(x,yy,t)
        text(50,45,self.title,25,True,'left')
        # Containers precede connectors; connectors precede nodes.
        for n in self.nodes:
            if n['kind'] not in ('pool','lane','blackbox','boundary'):continue
            x,y,w,h=n['x'],n['y'],n['w'],n['h']
            c.setFillColor(HexColor(n['color']));c.setStrokeColor(HexColor('#7c8d9d'));c.setLineWidth(1.2)
            c.rect(x,self.h-y-h,w,h,fill=1,stroke=1)
            if n['kind']=='boundary':text(x+18,y+28,n['text'],21,True,'left')
            elif n['kind']=='blackbox':text(x+w/2,y+h/2+6,n['text'],20,True)
            else:
                line([(x+42,y),(x+42,y+h)],width=1.2,color='#7c8d9d')
                c.saveState();c.translate(x+28,self.h-(y+h/2));c.rotate(90)
                c.setFont('Arial-Bold',16);c.setFillColor(HexColor('#172e46'));c.drawCentredString(0,0,n['text']);c.restoreState()
        for ed in self.edges:
            pts=ed['points'];k=ed['kind']
            line(pts,[7,5] if k in ('message','include','extend') else None,width=1.5)
            end=pts[-1];prev=pts[-2];angle=math.atan2(end[1]-prev[1],end[0]-prev[0])
            if k!='association':
                size=13 if k=='generalization' else 10
                aa=(end[0]-size*math.cos(angle-.45),end[1]-size*math.sin(angle-.45))
                bb=(end[0]-size*math.cos(angle+.45),end[1]-size*math.sin(angle+.45))
                if k in ('sequence','generalization'):
                    p=c.beginPath();p.moveTo(end[0],self.h-end[1]);p.lineTo(aa[0],self.h-aa[1]);p.lineTo(bb[0],self.h-bb[1]);p.close()
                    c.setFillColor(HexColor('#ffffff' if k=='generalization' else '#23364d'));c.drawPath(p,fill=1)
                else:line([aa,end,bb],width=1.5)
            if k=='message':
                c.setFillColor(HexColor('#ffffff'));c.circle(pts[0][0],self.h-pts[0][1],3.5,fill=1)
            if ed['label']:
                xx,yy=ed['label_at'] or pts[len(pts)//2]
                label=ed['label'];size=14
                tw=max(pdfmetrics.stringWidth(t,'Arial',size) for t in label.split('\n'))
                c.setFillColor(HexColor('#ffffff'));c.rect(xx-tw/2-3,self.h-yy-4-(len(label.split('\n'))-1)*17,tw+6,len(label.split('\n'))*17,fill=1,stroke=0)
                text(xx,yy,label,size)
        for n in self.nodes:
            k=n['kind']
            if k in ('pool','lane','blackbox','boundary'):continue
            x,y,w,h=n['x'],n['y'],n['w'],n['h'];cx=x+w/2;cy=y+h/2
            c.setStrokeColor(HexColor('#23364d'));c.setFillColor(HexColor(n['color']));c.setLineWidth(1.8)
            if k in ('start','end','catch','message_start'):
                c.setLineWidth(4 if k=='end' else 1.6);c.circle(cx,self.h-cy,w/2,fill=1)
                if k=='catch':c.circle(cx,self.h-cy,w/2-4)
                if k in ('catch','message_start'):
                    ew=w*.48;eh=w*.32;xx=cx-ew/2;yy=cy-eh/2
                    c.setLineWidth(1.3);c.rect(xx,self.h-yy-eh,ew,eh)
                    line([(xx,yy),(cx,yy+eh*.55),(xx+ew,yy)],width=1.2)
                text(cx,y+h+21,n['text'],15)
            elif k=='gateway':
                p=c.beginPath();p.moveTo(cx,self.h-y);p.lineTo(x+w,self.h-cy);p.lineTo(cx,self.h-y-h);p.lineTo(x,self.h-cy);p.close();c.drawPath(p,fill=1)
                text(cx,cy+7,'×',27,True)
                if n['id']=='URetry':text(cx-120,y-12,n['text'],15)
                elif n['id']=='URouteNeeded':text(cx,y+h+30,n['text'],15)
                else:text(cx,y-23,n['text'],15)
            elif k=='uc':
                c.ellipse(x,self.h-y-h,x+w,self.h-y,fill=1)
                size=16
                while max(pdfmetrics.stringWidth(t,'Arial',size) for t in n['text'].split('\n'))>w-24:size-=.5
                lines=n['text'].split('\n');text(cx,cy-(len(lines)-1)*size*.6+5,n['text'],size)
            elif k=='actor':
                c.circle(cx,self.h-y-13,12)
                line([(cx,y+25),(cx,y+60)])
                line([(cx-23,y+38),(cx+23,y+38)])
                line([(cx-22,y+85),(cx,y+60),(cx+22,y+85)])
                text(cx,y+110,n['text'],17,True)
            else:
                c.roundRect(x,self.h-y-h,w,h,10,fill=1)
                size=16
                while max(pdfmetrics.stringWidth(t,'Arial',size) for t in n['text'].split('\n'))>w-18:size-=.5
                lines=n['text'].split('\n');text(cx,cy-(len(lines)-1)*size*.6+5,n['text'],size)
        for x,y,txt,size in self.notes:text(x,y+size,txt,size,False,'left')
        c.showPage();c.save()
        doc=pymupdf.open(OUT/(self.name+'.pdf'))
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(OUT/(self.name+'.png'))
        doc.close()


def process():
    d=Drawing('02_search_process',2200,1080,'BPMN 2.0 · Поиск и выбор заведения · TO-BE')
    d.node('PoolUser','pool',50,120,2090,390,'Посетитель',color='#f3f7fc')
    d.node('PoolSystem','pool',50,600,2090,195,'Агрегатор',color='#ffffff')
    d.node('LaneAuto','lane',92,600,2048,195,'Автообработка',parent='PoolSystem',color='#eff7f3')
    d.node('PoolMaps','blackbox',50,880,2090,95,'Картографический сервис · закрытый пул',color='#fff6df')
    U='PoolUser';S='LaneAuto'
    for args in [
        ('UStart','start',100,205,36,36,'Выбор'),
        ('USearch','userTask',170,190,170,70,'Задать точку и фильтры;\nотправить запрос'),
        ('UResults','catch',400,207,36,36,'Ответ поиска'),
        ('UFound','gateway',490,200,50,50,'Получен список\nточек?'),
        ('UChoose','userTask',610,190,170,70,'Выбрать заведение;\nзапросить карточку'),
        ('UCard','catch',840,207,36,36,'Ответ карточки'),
        ('UCardOK','gateway',930,200,50,50,'Карточка\nдоступна?'),
        ('URouteNeeded','gateway',1070,200,50,50,'Нужен\nмаршрут?'),
        ('URouteReq','userTask',1220,190,170,70,'Запросить маршрут\nот точки поиска'),
        ('URoute','catch',1700,207,36,36,'Маршрут или\nпричина отказа'),
        ('UMerge','gateway',1850,200,50,50,''),
        ('UEnd','end',1970,207,36,36,'Заведение выбрано,\nадрес получен'),
        ('URetry','gateway',490,365,50,50,'Продолжить\nпоиск?'),
        ('UCancel','end',650,372,36,36,'Поиск прекращён'),
    ]:d.node(*args,parent=U)
    for args in [
        ('SSearchStart','message_start',180,660,36,36,'Запрос поиска'),
        ('SSearch','serviceTask',260,640,180,76,'Проверить запрос;\nопределить точку;\nнайти заведения'),
        ('SReply','sendTask',485,640,160,76,'Отправить список,\nпустой результат\nили ошибку'),
        ('SSearchEnd','end',690,660,36,36,''),
        ('SCardStart','message_start',795,660,36,36,'Запрос карточки'),
        ('SCard','serviceTask',875,640,160,76,'Проверить точку;\nподготовить карточку\nили объяснение'),
        ('SCardReply','sendTask',1080,640,160,76,'Отправить ответ\nна запрос карточки'),
        ('SCardEnd','end',1280,660,36,36,''),
        ('SRouteStart','message_start',1410,660,36,36,'Запрос маршрута'),
        ('SRoute','serviceTask',1490,640,160,76,'Проверить точки;\nполучить маршрут\nили причину отказа'),
        ('SRouteReply','sendTask',1695,640,160,76,'Отправить маршрут\nили объяснение\nнедоступности'),
        ('SRouteEnd','end',1900,660,36,36,''),
    ]:d.node(*args,parent=S)
    seq=[
        ('UStart','USearch',[(136,223),(170,223)],''),
        ('USearch','UResults',[(340,225),(400,225)],''),
        ('UResults','UFound',[(436,225),(490,225)],''),
        ('UFound','UChoose',[(540,225),(610,225)],'Да'),
        ('UFound','URetry',[(515,250),(515,365)],'Нет / ошибка'),
        ('URetry','USearch',[(490,390),(255,390),(255,260)],'Да'),
        ('URetry','UCancel',[(540,390),(650,390)],'Нет'),
        ('UChoose','UCard',[(780,225),(840,225)],''),
        ('UCard','UCardOK',[(876,225),(930,225)],''),
        ('UCardOK','URouteNeeded',[(980,225),(1070,225)],'Да'),
        ('UCardOK','URetry',[(955,250),(955,450),(565,450),(565,390),(540,390)],'Нет'),
        ('URouteNeeded','URouteReq',[(1120,225),(1220,225)],'Да'),
        ('URouteNeeded','UMerge',[(1095,200),(1095,155),(1875,155),(1875,200)],'Нет'),
        ('URouteReq','URoute',[(1390,225),(1700,225)],''),
        ('URoute','UMerge',[(1736,225),(1850,225)],''),
        ('UMerge','UEnd',[(1900,225),(1970,225)],''),
        ('SSearchStart','SSearch',[(216,678),(260,678)],''),
        ('SSearch','SReply',[(440,678),(485,678)],''),
        ('SReply','SSearchEnd',[(645,678),(690,678)],''),
        ('SCardStart','SCard',[(831,678),(875,678)],''),
        ('SCard','SCardReply',[(1035,678),(1080,678)],''),
        ('SCardReply','SCardEnd',[(1240,678),(1280,678)],''),
        ('SRouteStart','SRoute',[(1446,678),(1490,678)],''),
        ('SRoute','SRouteReply',[(1650,678),(1695,678)],''),
        ('SRouteReply','SRouteEnd',[(1855,678),(1900,678)],''),
    ]
    for i,(a,b,pts,label) in enumerate(seq):
        mid=pts[len(pts)//2]
        # Keep labels away from gateway headings and diagram elements.
        loc=((pts[0][0]+pts[1][0])/2,(pts[0][1]+pts[1][1])/2-8) if len(pts)==2 else (mid[0]+25,mid[1]-10)
        if a=='UFound' and b=='URetry':loc=(585,310)
        if a=='URetry' and b=='USearch':loc=(375,380)
        if a=='UCardOK' and b=='URetry':loc=(830,440)
        if a=='URouteNeeded' and b=='UMerge':loc=(1470,148)
        d.edge(f'F{i+1}',a,b,pts,label=label,label_at=loc)
    messages=[
        ('USearch','SSearchStart',[(240,260),(240,545),(198,545),(198,660)],'Поиск',(180,530)),
        ('SReply','UResults',[(560,640),(560,575),(418,575),(418,243)],'Результат',(460,560)),
        ('UChoose','SCardStart',[(695,260),(695,535),(813,535),(813,660)],'Карточка',(750,520)),
        ('SCardReply','UCard',[(1160,640),(1160,565),(858,565),(858,243)],'Ответ',(1030,550)),
        ('URouteReq','SRouteStart',[(1305,260),(1305,535),(1428,535),(1428,660)],'Маршрут',(1360,520)),
        ('SRouteReply','URoute',[(1775,640),(1775,560),(1718,560),(1718,243)],'Результат',(1805,545)),
        ('SSearch','PoolMaps',[(305,716),(305,840),(350,840),(350,880)],'Адрес → координаты',(260,825)),
        ('PoolMaps','SSearch',[(425,880),(425,815),(390,815),(390,716)],'Координаты / отказ',(475,805)),
        ('SRoute','PoolMaps',[(1520,716),(1520,835),(1510,835),(1510,880)],'Точки → маршрут',(1435,825)),
        ('PoolMaps','SRoute',[(1620,880),(1620,815),(1610,815),(1610,716)],'Маршрут / отказ',(1720,805)),
    ]
    for i,(a,b,pts,label,loc) in enumerate(messages):d.edge(f'M{i+1}',a,b,pts,'message',label,loc)
    d.note(50,995,'Сплошная стрелка — порядок внутри пула; пунктир — сообщение между участниками. Двойной круг — ожидание ответа. XOR — один из путей.',16)
    d.note(50,1025,'Три ветки агрегатора обслуживают отдельные запросы. Оценки читаются из каталога. Ошибки и предел ожидания карт (10 с) уточнены в UC-01.',16)
    d.export();native_bpmn(d)
    return d


def native_bpmn(d):
    ns={'bpmn':'http://www.omg.org/spec/BPMN/20100524/MODEL','bpmndi':'http://www.omg.org/spec/BPMN/20100524/DI','dc':'http://www.omg.org/spec/DD/20100524/DC','di':'http://www.omg.org/spec/DD/20100524/DI','xsi':'http://www.w3.org/2001/XMLSchema-instance'}
    for k,v in ns.items():E.register_namespace(k,v)
    def tag(k):p,n=k.split(':');return '{'+ns[p]+'}'+n
    defs=E.Element(tag('bpmn:definitions'),id='Definitions_Search',targetNamespace='https://example.org/shawarma/requirements')
    coll=E.SubElement(defs,tag('bpmn:collaboration'),id='Collaboration_Search')
    for pid,name,ref in [('PoolUser','Посетитель','Process_User'),('PoolSystem','Агрегатор','Process_System'),('PoolMaps','Картографический сервис',None)]:
        attrs={'id':pid,'name':name}
        if ref:attrs['processRef']=ref
        E.SubElement(coll,tag('bpmn:participant'),attrs)
    lookup={n['id']:n for n in d.nodes}
    for e in d.edges:
        if e['kind']=='message':E.SubElement(coll,tag('bpmn:messageFlow'),id=e['id'],name=e['label'],sourceRef=e['source'],targetRef=e['target'])
    for pid,parent in [('Process_User','PoolUser'),('Process_System','LaneAuto')]:
        p=E.SubElement(defs,tag('bpmn:process'),id=pid,isExecutable='false')
        if parent=='LaneAuto':
            ls=E.SubElement(p,tag('bpmn:laneSet'),id='LaneSet_System')
            lane=E.SubElement(ls,tag('bpmn:lane'),id='LaneAuto',name='Автоматическая обработка')
            for n in d.nodes:
                if n['parent']==parent:E.SubElement(lane,tag('bpmn:flowNodeRef')).text=n['id']
        elems={}
        for n in d.nodes:
            if n['parent']!=parent or n['kind'] in ('lane','pool'):continue
            k=n['kind'];typ={'start':'startEvent','message_start':'startEvent','end':'endEvent','catch':'intermediateCatchEvent','gateway':'exclusiveGateway'}.get(k,k)
            attrs={'id':n['id'],'name':n['text'].replace('\n',' ')}
            if k=='gateway':attrs['gatewayDirection']='Converging' if n['id']=='UMerge' else ('Mixed' if n['id']=='URetry' else 'Diverging')
            el=E.SubElement(p,tag('bpmn:'+typ),attrs);elems[n['id']]=el
            for e in d.edges:
                if e['kind']!='sequence':continue
                if e['target']==n['id']:E.SubElement(el,tag('bpmn:incoming')).text=e['id']
                if e['source']==n['id']:E.SubElement(el,tag('bpmn:outgoing')).text=e['id']
            if k in ('message_start','catch'):E.SubElement(el,tag('bpmn:messageEventDefinition'),id=n['id']+'_MessageDefinition')
        for e in d.edges:
            if e['kind']!='sequence' or e['source'] not in elems:continue
            attrs={'id':e['id'],'sourceRef':e['source'],'targetRef':e['target']}
            if e['label']:attrs['name']=e['label']
            el=E.SubElement(p,tag('bpmn:sequenceFlow'),attrs)
            if lookup[e['source']]['kind']=='gateway' and e['source']!='UMerge':
                cond=E.SubElement(el,tag('bpmn:conditionExpression'),{tag('xsi:type'):'bpmn:tFormalExpression'})
                cond.text=e['label']
    diagram=E.SubElement(defs,tag('bpmndi:BPMNDiagram'),id='BPMNDiagram_Search')
    plane=E.SubElement(diagram,tag('bpmndi:BPMNPlane'),id='BPMNPlane_Search',bpmnElement='Collaboration_Search')
    for n in d.nodes:
        attrs={'id':n['id']+'_di','bpmnElement':n['id']}
        if n['kind'] in ('pool','lane','blackbox'):attrs['isHorizontal']='true'
        shape=E.SubElement(plane,tag('bpmndi:BPMNShape'),attrs)
        E.SubElement(shape,tag('dc:Bounds'),x=str(n['x']),y=str(n['y']),width=str(n['w']),height=str(n['h']))
        if n['kind'] in ('start','message_start','catch','end','gateway') and n['text']:
            label=E.SubElement(shape,tag('bpmndi:BPMNLabel'))
            y=n['y']-60 if n['kind']=='gateway' else n['y']+n['h']+6
            x=n['x']+n['w']/2-65
            if n['id']=='URetry':x-=120;y=n['y']-32
            if n['id']=='URouteNeeded':y=n['y']+n['h']+12
            E.SubElement(label,tag('dc:Bounds'),x=str(x),y=str(y),width='130',height='45')
    for ed in d.edges:
        e=E.SubElement(plane,tag('bpmndi:BPMNEdge'),id=ed['id']+'_di',bpmnElement=ed['id'])
        for x,y in ed['points']:E.SubElement(e,tag('di:waypoint'),x=str(x),y=str(y))
        if ed['label']:
            lx,ly=ed['label_at'];lab=E.SubElement(e,tag('bpmndi:BPMNLabel'))
            E.SubElement(lab,tag('dc:Bounds'),x=str(lx-65),y=str(ly-20),width='130',height='30')
    E.indent(defs);E.ElementTree(defs).write(OUT/(d.name+'.bpmn'),encoding='utf-8',xml_declaration=True)


def use_cases():
    d=Drawing('03_use_cases',2000,1300,'UML · Варианты использования агрегатора')
    d.node('System','boundary',340,85,1260,1070,'Агрегатор оценок шавермы в Санкт-Петербурге',color='#f7faff')
    actors=[('Visitor',120,180,'Посетитель'),('Author',120,490,'Автор отзывов'),('Editor',120,810,'Редактор каталога'),('Maps',1790,180,'Картографический\nсервис'),('Source',1790,810,'Источник внешних\nоценок'),('Moderator',1790,550,'Модератор'),('Admin',1790,1010,'Администратор')]
    for id,x,y,label in actors:d.node(id,'actor',x,y,60,90,label)
    ucs=[
        ('UC01',440,150,270,80,'UC-01\nНайти и выбрать заведение'),
        ('UC11',850,150,270,80,'UC-11\nОпределить точку поиска'),
        ('UC02',1250,150,270,80,'UC-02\nПросмотреть карточку'),
        ('UC14',440,320,270,80,'UC-14\nЗарегистрироваться'),
        ('UC07',850,320,270,80,'UC-07\nСообщить об ошибке'),
        ('UC06',1250,320,270,80,'UC-06\nПолучить маршрут'),
        ('UC15',440,490,270,80,'UC-15\nВойти в систему'),
        ('UC03',850,490,270,80,'UC-03\nОтправить оценку и отзыв'),
        ('UC12',1250,490,270,80,'UC-12\nПроверить данные отзыва'),
        ('UC05',440,660,270,80,'UC-05\nПроверить свой отзыв'),
        ('UC04',850,660,270,80,'UC-04\nРассмотреть отзыв'),
        ('UC13',1250,660,270,80,'UC-13\nЗафиксировать решение'),
        ('UC08',440,830,270,80,'UC-08\nВести каталог'),
        ('UC09',850,830,270,80,'UC-09\nОбновить внешние оценки'),
        ('UC10',1250,1000,270,80,'UC-10\nУправлять ролями'),
    ]
    for args in ucs:d.node(*args[:1],'uc',*args[1:],parent='System',color='#ffffff')
    assoc=[
        ('Visitor','UC01',[(180,225),(440,190)]),
        ('Visitor','UC02',[(150,180),(150,135),(1385,135),(1385,150)]),
        ('Visitor','UC14',[(180,225),(300,225),(300,360),(440,360)]),
        ('Visitor','UC15',[(180,225),(280,225),(280,530),(440,530)]),
        ('Visitor','UC06',[(180,225),(250,225),(250,275),(1550,275),(1550,360),(1520,360)]),
        ('Author','UC03',[(180,535),(300,535),(300,610),(985,610),(985,570)]),
        ('Author','UC05',[(180,535),(300,535),(300,700),(440,700)]),
        ('Editor','UC08',[(180,855),(440,870)]),
        ('Editor','UC09',[(180,855),(300,855),(300,950),(985,950),(985,910)]),
        ('Maps','UC11',[(1790,225),(1670,225),(1670,145),(985,145),(985,150)]),
        ('Maps','UC06',[(1790,225),(1670,225),(1670,360),(1520,360)]),
        ('Source','UC09',[(1790,855),(1120,870)]),
        ('Moderator','UC04',[(1790,595),(1660,595),(1660,780),(985,780),(985,740)]),
        ('Admin','UC10',[(1790,1055),(1520,1040)]),
    ]
    for i,(a,b,pts) in enumerate(assoc):d.edge(f'A{i}',a,b,pts,'association')
    d.edge('G1','Author','Visitor',[(150,490),(150,300)],'generalization')
    # Two includes above the first row, and two aligned with their base UC.
    d.edge('I1','UC01','UC11',[(710,190),(850,190)],'include','«include»',(780,180))
    d.edge('I2','UC01','UC02',[(575,150),(575,78),(1385,78),(1385,150)],'include','«include»',(1160,73))
    d.edge('I3','UC03','UC12',[(1120,530),(1250,530)],'include','«include»',(1185,520))
    d.edge('I4','UC04','UC13',[(1120,700),(1250,700)],'include','«include»',(1185,690))
    d.edge('E1','UC06','UC02',[(1385,320),(1385,230)],'extend','«extend»',(1450,300))
    d.edge('E2','UC07','UC02',[(1120,360),(1180,360),(1180,250),(1300,250),(1300,225)],'extend','«extend»',(1180,315))
    d.note(50,1180,'include — обязательное включение; extend — дополнение карточки при запросе маршрута или обнаружении ошибки. Автор наследует функции посетителя.',16)
    d.note(50,1210,'Служебные роли входят в систему по UC-15 (общие связи входа опущены). Источник оценок — актор при прямой интеграции; при выгрузке действует редактор.',16)
    d.note(50,1240,'Представитель заведения использует роль посетителя. Карты участвуют в адресном определении точки и маршруте; доступ по геопозиции не обязателен.',16)
    d.export()
    puml=['@startuml','left to right direction','skinparam defaultFontName Arial','skinparam packageStyle rectangle','actor "Посетитель" as Visitor','actor "Автор отзывов" as Author','actor "Редактор каталога" as Editor','actor "Модератор" as Moderator','actor "Администратор" as Admin','actor "Картографический сервис" as Maps','actor "Источник внешних оценок" as Source','Author --|> Visitor','rectangle "Агрегатор оценок шавермы в Санкт-Петербурге" {']
    for n in d.nodes:
        if n['kind']=='uc':puml.append(f'  usecase "{n["text"].replace(chr(10), chr(92)+"n")}" as {n["id"]}')
    puml.append('}')
    for a,b,_ in assoc:puml.append(f'{a} -- {b}')
    puml += ['UC01 ..> UC11 : <<include>>','UC01 ..> UC02 : <<include>>','UC03 ..> UC12 : <<include>>','UC04 ..> UC13 : <<include>>','UC06 ..> UC02 : <<extend>>\n(request route)','UC07 ..> UC02 : <<extend>>\n(report error)','@enduml']
    # Parenthesized free-standing lines are not PlantUML syntax: keep conditions in labels.
    puml=[s.replace('<<extend>>\n(request route)','<<extend>>\\nпо запросу маршрута').replace('<<extend>>\n(report error)','<<extend>>\\nпри обнаружении ошибки') for s in puml]
    (OUT/'03_use_cases.puml').write_text('\n'.join(puml)+'\n',encoding='utf-8')
    return d


if __name__=='__main__':
    process();use_cases()
    print('Generated BPMN, UML, editable drawio, PDF and PNG previews.')
