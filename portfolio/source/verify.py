"""Inspect PDFs and export contact sheets for human visual review."""
import json
from pathlib import Path
import pymupdf as fitz
from assets import SCREENSHOTS

ROOT=Path(__file__).resolve().parents[1]
for name in ['documind-architecture.svg','documind-architecture-case.svg']:
    svg=(ROOT/'architecture'/name).read_text(encoding='utf-8')
    for label in ['all-MiniLM-L6-v2','384D','OpenAI GPT','Responses API','Evidence validation','Deterministic rules','Grounded answers']:
        assert label in svg, f'{name}: missing hybrid architecture component {label}'
    assert 'bypasses the LLM' not in svg and 'Optional provider' not in svg
results=[]
for name,path in [('case-study',ROOT/'case-study/DocuMind-Engineering-Case-Study.pdf'),('carousel',ROOT/'carousel/DocuMind-LinkedIn-Carousel.pdf')]:
    doc=fitz.open(path)
    assert len(doc)==8, f'{name}: expected 8 pages'
    assert 'Designed & Developed by Fiza Ahmad' in ' '.join(doc[0].get_text().split()), f'{name}: missing cover author credit'
    assert all('Fiza Ahmad' in page.get_text() for page in doc), f'{name}: missing author footer'
    live_page=doc[4] if name=='case-study' else doc[6]
    live_text=' '.join(live_page.get_text().split())
    for value in ['gpt-6-luna','434','210','0.0001484','Manual test record']:
        assert value.casefold() in live_text.casefold(), f'{name}: missing manual validation detail {value}'
    sheet=fitz.open()
    contact=sheet.new_page(width=1120,height=820)
    for i,page in enumerate(doc):
        assert len(page.get_text().strip())>100, f'Empty page {i+1}'
        pix=page.get_pixmap(matrix=fitz.Matrix(.7,.7),alpha=False)
        preview=ROOT/f'verification/{name}-page-{i+1:02d}.png'
        pix.save(preview)
        x=(i%4)*280;y=(i//4)*410
        contact.insert_image(fitz.Rect(x+5,y+5,x+275,y+385),stream=pix.tobytes('png'),keep_proportion=True)
        contact.insert_text((x+10,y+404),f'{name} {i+1}',fontsize=10)
    contact.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(ROOT/f'verification/{name}-contact-sheet.png')
    results.append({'file':str(path.relative_to(ROOT)),'pages':len(doc),'page_size_points':[round(doc[0].rect.width,2),round(doc[0].rect.height,2)],'selectable_text':True})
    doc.close();sheet.close()
for i in range(1,9):
    pix=fitz.Pixmap(str(ROOT/f'carousel/png/slide-{i:02d}.png'))
    assert (pix.width,pix.height)==(1080,1350)
checks=json.loads((ROOT/'verification/layout-checks.json').read_text())
assert len(checks)==16 and not any(item['clipped'] for item in checks), 'Clipped layout; inspect layout-checks.json'
(ROOT/'verification/pdf-checks.json').write_text(json.dumps({'pdfs':results,'carousel_png_count':8,'carousel_png_dimensions':[1080,1350],'layout_blocks_checked':16},indent=2),encoding='utf-8')
dimensions=[]
for name in SCREENSHOTS:
    path=ROOT/name
    assert path.is_file(), f'Missing canonical screenshot: {name}'
    pix=fitz.Pixmap(str(path))
    assert pix.width>500 and pix.height>200
    if '/post-ready/' in name:
        assert (pix.width,pix.height)==(2880,2000)
    dimensions.append({'file':name,'width':pix.width,'height':pix.height})
(ROOT/'verification/screenshot-dimensions.json').write_text(json.dumps(dimensions,indent=2),encoding='utf-8')
print('Final PDFs, slides, hybrid diagrams, live-test figures, author credits and 12 selected screenshots verified.')
