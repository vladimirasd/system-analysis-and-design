"""Build reviewable Word/PDF and stage Markdown from local course sources."""
from pathlib import Path
from html import escape
import re
import json
import zipfile
from collections import Counter
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION_START, WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, PageBreak, NextPageTemplate, Image, LongTable, TableStyle, KeepTogether, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'coursework'
SRC=OUT/'sources'
TITLE='Агрегатор оценок шавермы в Санкт-Петербурге'
DATE='13 ноября 2026 г.'

for name,file in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf'),('Arial-BoldItalic','arialbi.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-BoldItalic')


def markdown_table(rows):
    return '\n'.join('| '+' | '.join(r)+' |' for r in [rows[0],['---']*len(rows[0]),*rows[1:]])


def md_tables(text):
    tables=[]
    block=[]
    for ln in (text+'\n').splitlines():
        if ln.startswith('|'):block.append([s.strip() for s in ln.strip().strip('|').split('|')])
        elif block:
            tables.append([r for r in block if not all(re.fullmatch(r'[-: ]+',c) for c in r)])
            block=[]
    return tables


def source_documents():
    vision=(SRC/'00_vision.md').read_text(encoding='utf-8')
    vision=vision.replace('# '+TITLE,'# Введение и границы проекта',1)
    stakeholders=(ROOT/'stakeholders.md').read_text(encoding='utf-8')
    roles=next(t for t in md_tables(stakeholders) if t[0][0]=='ID')
    compact=[['ID','Тип','Стейкхолдер','Роль','Влияние','Интерес']]
    compact += [[r[0],r[1],r[2],r[3],r[5],r[6]] for r in roles[1:]]
    classification=stakeholders.split('## Принцип классификации\n',1)[1].split('## Таблица стейкхолдеров',1)[0].strip()
    levels=stakeholders.split('## Как понимать влияние и интерес\n',1)[1].strip()
    plan=(ROOT/'requirements_plan.md').read_text(encoding='utf-8')
    plan=re.sub(r'^(#+)',r'#\1',plan,flags=re.M)
    business=(ROOT/'business_requirements.md').read_text(encoding='utf-8')
    brtable=next(t for t in md_tables(business) if t[0][0]=='ID')
    selected=[brtable[0]]+[r for r in brtable[1:] if r[0] in ('BR-01','BR-02','BR-04')]
    stage1='\n\n'.join([
        '# Итерация 1. Стейкхолдеры и выявление требований',
        '## Карта стейкхолдеров',classification,markdown_table(compact),levels,
        plan,
        '## Предварительное видение: три ключевых SMART-требования',
        'Сроки отсчитываются от запуска пилота. Это целевые показатели учебного проекта, а не результаты исследования рынка. Сохранены исходные ID; выбранные BR-01, BR-02 и BR-04 соответствуют BR-01, BR-02 и BR-03 документа «Сис анал.pdf».',
        markdown_table(selected),
        'В BR-01 к запуску должны быть доступны не менее 50 уникальных точек с оценками двух внешних источников. Если источник недоступен, цель пересматривается до запуска. Приёмка учитывает происхождение данных; выдуманные оценки не заменяют внешний источник.',
        'Для BR-02 используются сопоставимые задания и меняется порядок способов поиска между участниками. Снижение времени рассчитывается: (медиана самостоятельного поиска − медиана выбора через агрегатор) / медиана самостоятельного поиска × 100%. Исходное время определяется в исследовании.',
        'В BR-04 учитываются только опубликованные собственные оценки реальных участников: импортированные записи, тестовые аккаунты и удалённые публикации исключаются. Одна пара «автор–заведение» даёт не более одной опубликованной оценки.',
        'Остальные цели исходного business_requirements.md сохранены как резерв развития: BR-03 — доверие аудитории, BR-05 — актуальность каталога, BR-06 — аудитория шестого месяца. Для текущей сдачи выбраны ровно три цели. Реальные опросы и показатели пока не получены.',
    ])+'\n'
    stage2=(SRC/'02_process.md').read_text(encoding='utf-8')
    stage3=(SRC/'03_use_cases.md').read_text(encoding='utf-8')
    fr=(SRC/'04_functional_requirements.md').read_text(encoding='utf-8')
    fr=re.sub(r'^(#+)',r'#\1',fr,flags=re.M)
    stage3+='\n\n'+fr
    appendix=(SRC/'05_acceptance.md').read_text(encoding='utf-8')
    docs=[('00_introduction.md',vision),('01_iteration_1.md',stage1),('02_iteration_2.md',stage2),('03_iteration_3.md',stage3),('04_appendix.md',appendix)]
    for name,text in docs:
        # Output files live in coursework, rather than coursework/sources.
        text=text.replace('../diagrams/','diagrams/')
        (OUT/name).write_text(text,encoding='utf-8')
    return [(n,(OUT/n).read_text(encoding='utf-8')) for n,_ in docs]


def blocks(text):
    lines=text.splitlines();i=0
    while i<len(lines):
        ln=lines[i].strip()
        if not ln:i+=1;continue
        if ln.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[s.strip() for s in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+',c) for c in cells):rows.append(cells)
                i+=1
            yield 'table',rows;continue
        m=re.match(r'^(#{1,6})\s+(.*)',ln)
        if m:yield 'heading',(len(m[1]),m[2]);i+=1;continue
        m=re.match(r'^!\[(.*?)\]\((.*?)\)',ln)
        if m:yield 'image',(m[1],m[2]);i+=1;continue
        m=re.match(r'^[-*]\s+(.*)',ln)
        if m:yield 'bullet',m[1];i+=1;continue
        m=re.match(r'^(\d+)\.\s+(.*)',ln)
        if m:yield 'number',m[1]+'. '+m[2];i+=1;continue
        acc=[ln];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|[-*] |\d+\. )',lines[i].strip()):
            acc.append(lines[i].strip());i+=1
        yield 'paragraph',' '.join(acc)


def plain(s):
    s=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',s)
    return s.replace('**','').replace('`','')


def rich(s):
    s=escape(s)
    s=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    return s.replace('`','')


def widths(rows,total):
    n=len(rows[0]);hdr=rows[0]
    if n==6 and hdr[0]=='ID':fr=[.08,.12,.29,.21,.15,.15]
    elif n==4 and hdr[0]=='ID':fr=[.09,.42,.17,.32]
    elif n==4 and hdr[0]=='ID сторон':fr=[.17,.26,.30,.27]
    elif n==4 and hdr[0]=='Период от начала выявления':fr=[.18,.40,.20,.22]
    elif n==4 and hdr[1]=='Требование':fr=[.09,.46,.15,.30]
    elif n==4 and hdr[0]=='Цель':fr=[.22,.20,.22,.36]
    elif n==4:fr=[.16,.30,.28,.26]
    elif n==3 and hdr[0]=='Код':fr=[.07,.30,.63]
    elif n==3:fr=[.19,.32,.49]
    elif n==2:
        fr=[.14,.86] if hdr[0] in ('ID','Шаг','Номер') else [.35,.65]
    else:fr=[1/n]*n
    # Special case functional requirements must precede the generic ID table.
    if n==4 and hdr[1]=='Требование':fr=[.09,.46,.15,.30]
    return [x/sum(fr)*total for x in fr]


def word(docs):
    doc=Document()
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10.5)
    normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.line_spacing=1.10
    for nm in ('Heading 1','Heading 2','Heading 3'):
        doc.styles[nm].font.name='Arial';doc.styles[nm].font.color.rgb=RGBColor.from_string('17334F')
        doc.styles[nm].paragraph_format.space_before=Pt(12)
    doc.styles['Heading 1'].font.size=Pt(18)
    doc.styles['Heading 2'].font.size=Pt(13)
    doc.styles['Heading 3'].font.size=Pt(11)
    sec=doc.sections[0];portrait(sec)
    head=sec.header.paragraphs[0];head.text='СИСТЕМНЫЙ АНАЛИЗ И СИСТЕМНОЕ ПРОЕКТИРОВАНИЕ';head.style='Caption'
    foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    foot.add_run('Итерации 1–3 · ')
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)
    for _ in range(4):doc.add_paragraph()
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run('КУРСОВОЙ ПРОЕКТ');r.bold=True;r.font.size=Pt(17)
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(TITLE);r.bold=True;r.font.size=Pt(22)
    p=doc.add_paragraph('Спецификация требований к программному обеспечению\nИтерации 1–3');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('\n\nУниверситет: ______________________________\nВыполнили: ________________________________\nГруппа: ___________________________________\nПреподаватель: ____________________________')
    doc.add_paragraph('Версия 1.0 · '+DATE+'\nСанкт-Петербург, 2026')
    doc.add_page_break();doc.add_heading('Содержание',level=1)
    for _,text in docs:
        for kind,val in blocks(text):
            if kind=='heading' and val[0]==1:doc.add_paragraph(val[1],style='TOC Heading' if False else 'Normal')
    doc.add_paragraph('Разделы и подразделы также доступны в панели навигации Word. Диаграммы расположены на отдельных альбомных страницах; их редактируемые исходники включены в комплект.')
    for _,text in docs:
        for kind,val in blocks(text):
            if kind=='heading':
                lev,title=val
                if lev==1:doc.add_page_break()
                doc.add_heading(title,level=min(lev,3))
            elif kind=='table':
                tab=doc.add_table(rows=1,cols=len(val[0]));tab.style='Table Grid';tab.autofit=False
                ws=widths(val,17.0)
                for j,w in enumerate(ws):tab.columns[j].width=Cm(w)
                for rowidx,row in enumerate(val):
                    cells=tab.rows[0].cells if rowidx==0 else tab.add_row().cells
                    for j,txt in enumerate(row):
                        cells[j].width=Cm(ws[j]);cells[j].text=plain(txt)
                        for p in cells[j].paragraphs:
                            p.paragraph_format.space_after=Pt(3);p.paragraph_format.space_before=Pt(2)
                            for run in p.runs:run.font.size=Pt(8.5);run.bold=(rowidx==0)
                        if rowidx==0:
                            props=cells[j]._tc.get_or_add_tcPr();shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7EFF6');props.append(shade)
                    trPr=tab.rows[rowidx]._tr.get_or_add_trPr()
                    if rowidx==0:trPr.append(OxmlElement('w:tblHeader'))
                    # Keep each row together; long tables may flow across pages.
                    trPr.append(OxmlElement('w:cantSplit'))
                doc.add_paragraph()
            elif kind=='image':
                caption,path=val
                s=doc.add_section(WD_SECTION_START.NEW_PAGE);s.orientation=WD_ORIENT.LANDSCAPE
                s.page_width=Cm(42);s.page_height=Cm(29.7);s.top_margin=Cm(1.5);s.bottom_margin=Cm(1.5);s.left_margin=Cm(1.5);s.right_margin=Cm(1.5)
                p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                with pymupdf.open(str((OUT/path).with_suffix('.pdf'))) as im:
                    w,h=im[0].rect.width,im[0].rect.height
                factor=min(39/w,24/h)
                p.add_run().add_picture(str(OUT/path),width=Cm(w*factor),height=Cm(h*factor))
                p=doc.add_paragraph(caption,style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                portrait(doc.add_section(WD_SECTION_START.NEW_PAGE))
            else:
                style='List Bullet' if kind=='bullet' else None
                p=doc.add_paragraph(plain(val),style=style)
    doc.core_properties.title=TITLE+' — итерации 1–3'
    doc.core_properties.subject='Карта стейкхолдеров, BPMN, Use Case и функциональные требования'
    doc.core_properties.author=''
    doc.save(OUT/'iterations_1_3.docx')


def portrait(sec):
    sec.orientation=WD_ORIENT.PORTRAIT;sec.page_width=Cm(21);sec.page_height=Cm(29.7)
    sec.top_margin=Cm(1.8);sec.bottom_margin=Cm(1.8);sec.left_margin=Cm(2);sec.right_margin=Cm(2)


class Report(BaseDocTemplate):
    def __init__(self,path,**kwargs):
        super().__init__(str(path),**kwargs)
        self.heading_counts={}
    def beforeDocument(self):
        self.heading_counts={}
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name in ('H1','H2'):
            lvl=0 if flowable.style.name=='H1' else 1
            txt=flowable.getPlainText()
            idx=self.heading_counts.get(txt,0);self.heading_counts[txt]=idx+1
            key='h_'+str(abs(hash(txt)))+'_'+str(idx)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(txt,key,level=lvl,closed=False)
            if lvl==0 or txt.startswith(('Карта стейкхолдеров','План выявления требований','Предварительное видение:', 'UC-01.', 'UC-03.', 'UC-04.', 'Функциональные требования')):
                self.notify('TOCEntry',(lvl,txt,self.page,key))


def pdf(docs):
    margin=48;W,H=A4;LW,LH=landscape(A3)
    styles={
        'Body':ParagraphStyle('Body',fontName='Arial',fontSize=10,leading=14,spaceAfter=7),
        'H1':ParagraphStyle('H1',fontName='Arial-Bold',fontSize=18,leading=23,spaceAfter=14,keepWithNext=True,textColor=colors.HexColor('#17334F')),
        'H2':ParagraphStyle('H2',fontName='Arial-Bold',fontSize=12.5,leading=17,spaceBefore=10,spaceAfter=8,keepWithNext=True,textColor=colors.HexColor('#17334F')),
        'H3':ParagraphStyle('H3',fontName='Arial-Bold',fontSize=10.5,leading=14,spaceBefore=9,spaceAfter=6,keepWithNext=True),
        'Cell':ParagraphStyle('Cell',fontName='Arial',fontSize=8.2,leading=10.8,spaceAfter=0),
        'Header':ParagraphStyle('Header',fontName='Arial-Bold',fontSize=8.2,leading=10.8),
        'Title':ParagraphStyle('Title',fontName='Arial-Bold',fontSize=24,leading=32,alignment=1,textColor=colors.HexColor('#17334F')),
        'Subtitle':ParagraphStyle('Subtitle',fontName='Arial',fontSize=13,leading=20,alignment=1,spaceAfter=12),
        'Caption':ParagraphStyle('Caption',fontName='Arial-Italic',fontSize=10,leading=14,alignment=1,spaceBefore=8),
    }
    def footer(c,doc):
        w,h=c._pagesize
        if doc.page==1:return
        c.setFont('Arial',8);c.setFillColor(colors.HexColor('#5c6d7c'))
        c.drawString(margin,25,'Агрегатор оценок шавермы · Итерации 1–3')
        c.drawRightString(w-margin,25,str(doc.page))
    doc=Report(OUT/'iterations_1_3.pdf',pagesize=A4,title=TITLE+' — итерации 1–3',author='',allowSplitting=1)
    doc.addPageTemplates([
        PageTemplate(id='Portrait',frames=[Frame(margin,margin,W-2*margin,H-2*margin,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],pagesize=A4,onPage=footer),
        PageTemplate(id='Landscape',frames=[Frame(35,45,LW-70,LH-85,id='large',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],pagesize=landscape(A3),onPage=footer),
    ])
    story=[Spacer(1,110),Paragraph('КУРСОВОЙ ПРОЕКТ',styles['Subtitle']),Spacer(1,20),Paragraph(TITLE,styles['Title']),Spacer(1,20),Paragraph('Спецификация требований к программному обеспечению<br/>Итерации 1–3',styles['Subtitle']),Spacer(1,65),Paragraph('Университет: ______________________________<br/>Выполнили: ________________________________<br/>Группа: ___________________________________<br/>Преподаватель: ____________________________',styles['Body']),Spacer(1,45),Paragraph('Версия 1.0 · '+DATE+'<br/>Санкт-Петербург, 2026',styles['Subtitle']),PageBreak()]
    story.append(Paragraph('Содержание',ParagraphStyle('TocTitle',parent=styles['H1'])))
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC1',fontName='Arial-Bold',fontSize=10,leading=16,spaceBefore=8),ParagraphStyle('TOC2',fontName='Arial',fontSize=9,leading=13,leftIndent=12,firstLineIndent=0,spaceBefore=2)]
    story.append(toc)
    for _,text in docs:
        for kind,val in blocks(text):
            if kind=='heading':
                lev,title=val
                if lev==1:story.append(PageBreak())
                elif title.startswith(('UC-01.','UC-03.','UC-04.')):story.append(CondPageBreak(225))
                story.append(Paragraph(rich(title),styles['H'+str(min(lev,3))]))
            elif kind=='table':
                rows=[[Paragraph(rich(t),styles['Header' if i==0 else 'Cell']) for t in row] for i,row in enumerate(val)]
                tab=LongTable(rows,colWidths=widths(val,W-2*margin),repeatRows=1,hAlign='LEFT',splitByRow=1)
                tab.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EFF6')),
                    ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#B6C4D0')),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                    ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8FAFC')]),
                ]))
                story.extend([tab,Spacer(1,10)])
            elif kind=='image':
                caption,path=val
                story.extend([NextPageTemplate('Landscape'),PageBreak()])
                with pymupdf.open(str((OUT/path).with_suffix('.pdf'))) as im:w,h=im[0].rect.width,im[0].rect.height
                factor=min((LW-70)/w,(LH-140)/h)
                story.append(Image(str(OUT/path),width=w*factor,height=h*factor))
                story.append(Paragraph(caption,styles['Caption']))
                story.extend([NextPageTemplate('Portrait'),PageBreak()])
            elif kind=='bullet':story.append(Paragraph('• '+rich(val),styles['Body']))
            else:story.append(Paragraph(rich(val),styles['Body']))
    doc.multiBuild(story)


def package_and_check(docs):
    combined='# '+TITLE+'\n\nСпецификация требований к ПО. Итерации 1–3. Версия 1.0. '+DATE+'\n\n'
    combined+='\n\n'.join(t for _,t in docs)
    (OUT/'iterations_1_3.md').write_text(combined,encoding='utf-8')
    with zipfile.ZipFile(OUT/'diagrams_sources.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted((OUT/'diagrams').glob('*')):
            if p.suffix in ('.drawio','.bpmn','.puml'):z.write(p,'diagrams/'+p.name)
        z.write(ROOT/'sec(2).drawio','original/sec(2).drawio')
    doc=pymupdf.open(OUT/'iterations_1_3.pdf')
    text='\n'.join(p.get_text() for p in doc)
    fr=re.findall(r'^\| (FR-\d+) \|',combined,re.M)
    expected={f'FR-{i:02}' for i in range(1,57)}
    assert set(fr)==expected and len(fr)==56,Counter(fr)
    assert all(x in text for x in ('UC-01','UC-03','UC-04','FR-56','PENDING','BR-04'))
    assert not any(not p.get_text().strip() and not p.get_images() for p in doc),'Empty PDF page'
    result={'pdf_pages':len(doc),'requirements':len(fr),'detailed_use_cases':['UC-01','UC-03','UC-04'],'stakeholders':19,'main_business_requirements':['BR-01','BR-02','BR-04'],'pdf_page_sizes':sorted({(round(p.rect.width),round(p.rect.height)) for p in doc}),'note':'Checks concern documents and diagram structure; no application implementation is claimed.'}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    doc.close();print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    docs=source_documents();word(docs);pdf(docs);package_and_check(docs)
