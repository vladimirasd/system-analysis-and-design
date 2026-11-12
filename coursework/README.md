# Первые три итерации курсового проекта

Тема: агрегатор оценок шавермы в Санкт-Петербурге. Подготовлено по заданию, наброску «Сис анал.pdf» и пользовательской диаграмме «sec(2).drawio».

## Что открыть

- [iterations_1_3.docx](iterations_1_3.docx) — основной редактируемый отчёт для сдачи.
- [iterations_1_3.pdf](iterations_1_3.pdf) — версия для просмотра с оглавлением и закладками.
- [diagrams_sources.zip](diagrams_sources.zip) — редактируемые диаграммы и неизменённый пользовательский BPMN-исходник.

Word и PDF собраны из одних текстов; номера страниц могут различаться. Диаграммы размещены на альбомных листах A3, остальные страницы — A4. Перед сдачей нужно заполнить ФИО, группу, вуз и преподавателя на титульном листе. Результаты интервью и достижения бизнес-метрик не выдуманы: документ содержит план и целевые значения.

## По этапам

| Этап | Содержание | Текст |
| --- | --- | --- |
| 1 | Карта 19 стейкхолдеров, план выявления требований, три ключевые SMART-цели | [01_iteration_1.md](01_iteration_1.md) |
| 2 | Поиск и выбор заведения с маршрутом: процесс TO-BE по пользовательскому наброску | [02_iteration_2.md](02_iteration_2.md) |
| 3 | 15 вариантов использования, три детальных UC, 56 функциональных требований и трассировка | [03_iteration_3.md](03_iteration_3.md) |

Дополнительно: [видение и правила](00_introduction.md), [чек-лист и глоссарий](04_appendix.md), [полный текст Markdown](iterations_1_3.md).

## Диаграммы

- BPMN: [Draw.io](diagrams/02_search_process.drawio), [BPMN 2.0 XML](diagrams/02_search_process.bpmn), [PDF](diagrams/02_search_process.pdf), [PNG](diagrams/02_search_process.png).
- Use Case: [Draw.io](diagrams/03_use_cases.drawio), [PlantUML](diagrams/03_use_cases.puml), [PDF](diagrams/03_use_cases.pdf), [PNG](diagrams/03_use_cases.png).

Файлы .drawio открываются в diagrams.net, .bpmn — в редакторе BPMN, .puml — в PlantUML. В исходнике BPMN пулы разделяют посетителя, агрегатор и карты; технические компоненты исходного наброска остаются материалом для четвёртой итерации. Выбор двух источников оценок и поставщика карт пока не подтверждён и явно отмечен как открытое решение.

## Воспроизведение сборки

Из корня D:\sad в PowerShell:

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r tools\requirements.txt
.venv\Scripts\python.exe -X utf8 tools\build_diagrams.py
.venv\Scripts\python.exe -X utf8 tools\build_report.py
.venv\Scripts\python.exe -X utf8 tools\validate_deliverables.py
```

Сборка использует Arial из C:\Windows\Fonts. Тексты редактируются в sources/ и корневых stakeholders.md, requirements_plan.md, business_requirements.md; файлы этапов и общий отчёт пересобираются. Отчёт проверки структуры документов — [validation.json](validation.json). Проверка документов не является тестированием реализации приложения: ПО в этих итерациях не разрабатывается.
