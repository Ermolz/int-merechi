"""Create the report and portable evidence bundle from WDQS exports."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, XPreformatted, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[1]
DATE = "26.10.2026"
MANIFEST = json.loads((ROOT / "queries/manifest.json").read_text(encoding="utf-8"))
OUT = ROOT / "output/pdf/Практичне_заняття_6_Wikidata.pdf"
DATA = {}
BLOCKS = []


def val(binding, field):
    return binding.get(field, {}).get("value", "UNBOUND")


def compact(value):
    if value.startswith("http://www.wikidata.org/entity/"):
        return value.rsplit("/", 1)[-1]
    if "Special:FilePath/" in value:
        return unquote(value.split("Special:FilePath/", 1)[-1])
    return value.replace("T00:00:00Z", "")


def media_name(value):
    # Keep the full original URI in JSON and CSV; abbreviate scripts absent from Arial.
    return re.sub(r"[^\x00-\u052f]+", "...", compact(value))


def text(content): BLOCKS.append(("text", content))
def heading(content): BLOCKS.append(("heading", content))
def table(headers, rows, widths=None): BLOCKS.append(("table", (headers, rows, widths)))
def page(): BLOCKS.append(("page", None))


def query(index, question):
    item = MANIFEST[index-1]
    heading(f"{index} {item['title']}")
    code = "\n".join(line for line in (ROOT / item["query"]).read_text(encoding="utf-8").splitlines()
                     if not line.startswith("#title:") and line != "#defaultView:Table")
    BLOCKS.append(("code", code))
    text(f"Кількість рядків: {len(DATA[item['id']]['results']['bindings'])}.")
    return DATA[item["id"]]["results"]["bindings"]


def screenshot(key, caption, height=345):
    path = ROOT / "screenshots" / f"{key}_view.png"
    if not path.exists(): path = ROOT / "screenshots" / f"{key}.png"
    BLOCKS.append(("image", (path, caption, height)))


def prepare_data():
    verification = []
    for item in MANIFEST:
        path = ROOT / "results" / f"{item['id']}.json"
        raw = path.read_bytes()
        data = json.loads(raw)
        assert "head" in data and "results" in data, item["id"]
        DATA[item["id"]] = data
        fields = data["head"]["vars"]
        with path.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            for row in data["results"]["bindings"]:
                writer.writerow([val(row, field) if field in row else "" for field in fields])
        assert (ROOT / "screenshots" / f"{item['id']}.png").exists()
        verification.append({"query":item["query"], "date":DATE, "environment":"Wikidata Query Service web interface",
                             "rows":len(data["results"]["bindings"]),
                             "query_sha256":hashlib.sha256((ROOT/item["query"]).read_bytes()).hexdigest(),
                             "result_sha256":hashlib.sha256(raw).hexdigest()})
    assert [len(DATA[m["id"]]["results"]["bindings"]) for m in MANIFEST[:4]] == [1,7,14,7]
    assert len(DATA[MANIFEST[4]["id"]]["results"]["bindings"]) >= 5
    assert len(DATA[MANIFEST[6]["id"]]["results"]["bindings"]) > 0
    assert len(DATA[MANIFEST[7]["id"]]["results"]["bindings"]) > 0
    (ROOT/"validation/verification.json").write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding="utf-8")


def content():
    BLOCKS.append(("title", "Практичне заняття 6"))
    BLOCKS.append(("subtitle", "Запити до Wikidata Query Service"))
    text("Обрана сутність: Альберт Айнштайн (Q937). Мета: отримати базові, часові, медійні та геопросторові дані за допомогою SPARQL.")

    rows=query(1, "")
    table(["personLabel", "birth", "birthplaceLabel"],
          [[val(r,"personLabel"),compact(val(r,"birth")),val(r,"birthplaceLabel")] for r in rows], [190,130,191])
    rows=query(2, "")
    table(["country", "countryLabel"],
          [[compact(val(r,"country")),val(r,"countryLabel")] for r in rows], [100,411])
    text("wdt:P27 повертає значення громадянства без дат початку та завершення.")

    page()
    rows=query(3, "")
    table(["occupation", "occupationLabel"],
          [[compact(val(r,"occupation")),val(r,"occupationLabel")] for r in rows], [100,411])

    page()
    rows=query(4, "")
    table(["country", "countryLabel", "start", "end"],
          [[compact(val(r,f)) for f in ("country","countryLabel","start","end")] for r in rows], [65,222,112,112])
    text("p:P27 веде до заяви, ps:P27 - до її значення, pq:P580 і pq:P582 - до часових меж. Наприклад, апатридність має період 1896-01-28 - 1901-02-21.")
    text("OPTIONAL зберігає рядки без дат. UNBOUND означає пропуск, а не необмежений строк. Дати на кшталт 1918-01-01 можуть мати точність лише до року.")

    page()
    rows=query(5, "")
    text("Отримано шість зображень п'яти фізиків. ImageGrid вмикає галерею, wikibase:label додає підписи.")
    screenshot("05_physicists_gallery", "Галерея зображень", 360)

    page()
    rows=query(6, "")
    table(["personLabel", "kind", "Медіафайл"],
          [[val(r,"personLabel"),val(r,"kind"),media_name(val(r,"media"))] for r in rows], [140,95,276])
    text("Знайдено два записи голосу P990 та чотири записи вимови імені P443. Для P51 і P10 у цій вибірці результатів немає. Окремі назви файлів скорочено.")

    page()
    rows=query(7, "")
    table(["place", "placeLabel", "distance км"],
          [[compact(val(r,"place")),val(r,"placeLabel"),f'{float(val(r,"distance")):.3f}'] for r in rows[:4]], [70,341,100])
    text("Наведено чотири найближчі об'єкти. Радіус пошуку - 5 км; distance - відстань між координатами.")
    screenshot("07_bern_museums_map", "Карта музеїв Берна", 270)

    page()
    rows=query(8, "")
    table(["personLabel", "birthplaceLabel", "employerCount", "exampleEmployerLabel", "hasImage"],
          [[val(r,f) for f in ("personLabel","birthplaceLabel","employerCount","exampleEmployerLabel","hasImage")] for r in rows], [110,85,85,171,60])
    text("Відібрано фізиків, народжених до 1900 року, та періоди роботи, що перетинаються з 1900-1950 роками. Підрахунок охоплює лише заяви з обома часовими межами.")
    text("COUNT(DISTINCT) усуває повтори установ, SAMPLE обирає один приклад, OPTIONAL додає зображення за наявності. GROUP BY групує результати за особою та місцем народження.")
    heading("Висновок")
    text("Прямі властивості повертають значення без часового контексту. Заяви p:/ps: та кваліфікатори pq: дозволяють визначити період дії факту.")


def highlight_sparql(code):
    tokens=re.compile(
        r'(?P<iri><https?://[^>]*>)|(?P<string>"(?:\\.|[^"\\])*")|'
        r'(?P<comment>#[^\n]*)|(?P<variable>\?[A-Za-z_]\w*)|'
        r'(?P<prefix>\b(?:wd|wdt|p|ps|pq|bd|wikibase|xsd|hint):[A-Za-z0-9_]*)|'
        r'(?P<keyword>\b(?:PREFIX|SELECT|DISTINCT|WHERE|VALUES|SERVICE|OPTIONAL|FILTER|EXISTS|BIND|AS|GROUP|BY|HAVING|ORDER|ASC|DESC|COUNT|SAMPLE|BOUND)\b)|'
        r'(?P<number>\b\d+(?:\.\d+)?\b)'
    )
    palette={"iri":"#4D6A47","string":"#2E6739","comment":"#6D7378",
             "variable":"#155E8A","prefix":"#6B3679","keyword":"#173D7A","number":"#8B4B19"}
    fragments=[]
    offset=0
    for match in tokens.finditer(code):
        fragments.append(html.escape(code[offset:match.start()]))
        token=match.lastgroup
        font="CodeBold" if token=="keyword" else "Code"
        fragments.append(f'<font name="{font}" color="{palette[token]}">{html.escape(match.group())}</font>')
        offset=match.end()
    fragments.append(html.escape(code[offset:]))
    return "".join(fragments)


def render():
    fonts=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
    for name,file in (("Body","arial.ttf"),("BodyBold","arialbd.ttf"),("Code","consola.ttf"),("CodeBold","consolab.ttf")):
        pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBody",fontName="Body",fontSize=10.2,leading=14,spaceAfter=7,textColor=colors.black))
    styles.add(ParagraphStyle(name="ReportHeading",fontName="BodyBold",fontSize=13,leading=17,spaceBefore=10,spaceAfter=9,keepWithNext=True,textColor=colors.black))
    styles.add(ParagraphStyle(name="ReportTitle",fontName="BodyBold",fontSize=22,leading=27,spaceAfter=8,textColor=colors.black))
    styles.add(ParagraphStyle(name="ReportSubtitle",fontName="BodyBold",fontSize=15,leading=20,spaceAfter=15,textColor=colors.black))
    styles.add(ParagraphStyle(name="Cell",fontName="Body",fontSize=9.2,leading=12,splitLongWords=True))
    styles.add(ParagraphStyle(name="CellHeader",fontName="BodyBold",fontSize=9.2,leading=12,splitLongWords=True))
    styles.add(ParagraphStyle(name="CaptionR",fontName="Body",fontSize=8.5,leading=11,spaceAfter=9,alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CodeR",fontName="Code",fontSize=8.1,leading=10.1))
    story=[]
    for kind,body in BLOCKS:
        if isinstance(body,str): body=body.replace("–","-").replace("—","-")
        if kind in ("title","subtitle","heading","text"):
            key={"title":"ReportTitle","subtitle":"ReportSubtitle","heading":"ReportHeading","text":"ReportBody"}[kind]
            story.append(Paragraph(html.escape(body),styles[key]))
        elif kind=="code":
            code=XPreformatted(highlight_sparql(body),styles["CodeR"])
            code_block=Table([[code]],colWidths=[511],hAlign="LEFT")
            code_block.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F5F5F5")),
                ("BOX",(0,0),(-1,-1),.4,colors.HexColor("#C8C8C8")),
                ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
                ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
            ]))
            story.extend([code_block,Spacer(1,8)])
        elif kind=="table":
            headers,rows,widths=body
            content=[[Paragraph(html.escape(str(c)),styles["CellHeader" if i==0 else "Cell"]) for c in row]
                     for i,row in enumerate([headers]+rows)]
            item=Table(content,colWidths=widths or [511/len(headers)]*len(headers),repeatRows=1,hAlign="LEFT")
            item.setStyle(TableStyle([
                ("GRID",(0,0),(-1,-1),.4,colors.black),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
                ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ]))
            story.extend([item,Spacer(1,8)])
        elif kind=="image":
            path,caption,max_height=body
            with PILImage.open(path) as image: width,height=image.size
            scale=min(511/width,max_height/height)
            story.append(KeepTogether([Image(str(path),width=width*scale,height=height*scale),Spacer(1,4),Paragraph(html.escape(caption),styles["CaptionR"])]))
        elif kind=="page": story.append(PageBreak())
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=40,title="Практичне заняття 6 Запити до Wikidata Query Service",author="")
    doc.build(story)


def markdown():
    lines=[]
    for kind,body in BLOCKS:
        if kind in ("title","subtitle","heading","text"):
            prefix={"title":"# ","subtitle":"## ","heading":"## ","text":""}[kind]
            lines.extend([prefix+body,""])
        elif kind=="code": lines.extend(["```sparql",body,"```",""])
        elif kind=="table":
            heads,rows,_=body
            lines.extend(["| "+" | ".join(heads)+" |","|"+"---|"*len(heads)])
            lines.extend("| "+" | ".join(str(c).replace("|","\\|") for c in row)+" |" for row in rows)
            lines.append("")
        elif kind=="image":
            path,caption,_=body
            lines.extend([f"![{caption}]({path.relative_to(ROOT).as_posix()})",""])
        elif kind=="link": lines.extend([f"[{body[0]}]({body[1]})",""])
    (ROOT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    links="\n".join(f'<li><a href="{html.escape(m["url"],quote=True)}">{i+1}. {html.escape(m["title"])}</a> - {len(DATA[m["id"]]["results"]["bindings"])} рядків</li>' for i,m in enumerate(MANIFEST))
    (ROOT/"OPEN_QUERIES.html").write_text('<!doctype html><html lang="uk"><meta charset="utf-8"><title>Практичне заняття 6</title><style>body{font:18px/1.6 system-ui;max-width:900px;margin:40px auto;padding:20px}li{margin:12px 0}</style><h1>Практичне заняття 6</h1><p>Кожне посилання відкриває відповідний запит у Wikidata Query Service. Натисніть Execute для повторного виконання. Кількість рядків наведено станом на '+DATE+'.</p><ol style="list-style:none;padding-left:0">'+links+'</ol><p><a href="output/pdf/Практичне_заняття_6_Wikidata.pdf">Звіт PDF</a> · <a href="REPORT.md">Звіт Markdown</a></p></html>',encoding="utf-8")


def main():
    prepare_data()
    content()
    render()
    markdown()
    print(OUT)
    print("All 8 WDQS exports and screenshots verified")


if __name__=="__main__": main()

