"""Repository-grounded hybrid architecture artwork and editorial sections."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]

def architecture():
    parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1388" viewBox="0 0 1180 910">
    <defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="#7054db"/><stop offset="1" stop-color="#4932a1"/></linearGradient>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L7 4 L0 8" fill="none" stroke="#8070cb" stroke-width="1.5"/></marker>
    <marker id="teal" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L7 4 L0 8" fill="none" stroke="#358a86" stroke-width="1.5"/></marker></defs>
    <style>text{font-family:Segoe UI,Arial,sans-serif;fill:#1b2840}.title{font-size:22px;font-weight:650}.body{font-size:19px;fill:#596981}.lane{font-size:15px;font-weight:700;letter-spacing:1.5px;fill:#7054c2}.small{font-size:17px;fill:#596981}</style>
    <rect width="1180" height="910" rx="24" fill="#f6f7fb"/>
    <text x="30" y="45" style="font-size:30px;font-weight:700">DocuMind / one hybrid intelligence system</text>
    <text x="30" y="78" class="body">Next.js → FastAPI · organization-scoped access · existing PostgreSQL-backed worker</text>
    <text x="30" y="120" class="lane">01 / INGEST, INDEX &amp; PRESERVE SOURCES</text>
    <text x="30" y="370" class="lane">02 / EMBED THE QUESTION → RETRIEVE EVIDENCE → GENERATE</text>
    <text x="30" y="620" class="lane">03 / VALIDATE RESULTS &amp; REVIEW CANDIDATES</text>''']
    def edge(path,analysis=False):
        parts.append(f'<path d="{path}" fill="none" stroke="{"#358a86" if analysis else "#8070cb"}" stroke-width="2.5" marker-end="url(#{"teal" if analysis else "arrow"})"'+(' stroke-dasharray="7 5"' if analysis else '')+'/>')
    # Documents and questions use the same configured local embedding profile.
    for path in ['M280 215 H308','M560 215 H588','M840 215 H868','M715 290 V388',
                 'M280 465 H308','M560 465 H588','M840 465 H868','M995 540 V638',
                 'M870 715 H842','M280 715 H308']:
        edge(path)
    # Structured AI reads authorized revisions directly, not the chat retriever.
    edge('M995 290 V388',True)
    # Independent deterministic rules on selected sources; never through GPT.
    edge('M950 290 V325 H15 V715 H28')
    # Human review applies to analysis candidates, not mandatory approval of chat.
    edge('M995 790 V815 H435 V792',True)
    def node(x,y,title,lines,hero=False):
        parts.append('<g class="architecture-node">')
        parts.append(f'<rect x="{x}" y="{y}" width="250" height="150" rx="14" fill="{"url(#g)" if hero else "white"}" stroke="{"#6650bc" if hero else "#dce1ed"}"/>')
        headings=title.split('|')
        for i,t in enumerate(headings):
            parts.append(f'<text x="{x+17}" y="{y+32+i*27}" class="title"'+(' style="fill:white"' if hero else '')+f'>{escape(t)}</text>')
        start=y+66+(len(headings)-1)*27
        for i,t in enumerate(lines):
            parts.append(f'<text x="{x+17}" y="{start+i*25}" class="body"'+(' style="fill:#eee8ff"' if hero else '')+f'>{escape(t)}</text>')
        parts.append('</g>')
    node(30,140,'Parse + chunk',['PDF / DOCX / TXT','OCR when necessary','Background worker'])
    node(310,140,'Local chunk encoder',['Sentence Transformers','all-MiniLM-L6-v2','384D vectors (default)'])
    node(590,140,'PostgreSQL',['pgvector chunk vectors','Sections + source refs','Jobs + revision history'])
    node(870,140,'Selected revisions',['Authorized source text','Configured AI analysis','Deterministic analysis'])
    node(30,390,'User question',['Selected document scope','Organization membership','Access checked by API'])
    node(310,390,'Local query encoder',['all-MiniLM-L6-v2','384D query vector','Same embedding profile'])
    node(590,390,'Authorized retrieval',['Cosine similarity','Organization + profile','Relevant stored chunks'])
    node(870,390,'OpenAI GPT|Intelligence',['Responses API','Q&A + AI analysis'],True)
    node(30,640,'Deterministic rules',['Fields + text differences','Configured risk rules','Commitment candidates'])
    node(310,640,'Human review + ops',['Analysis candidates','Approve / reject / correct','Assignments + audit'])
    node(590,640,'Grounded answers',['GPT-generated prose','Application citations','Abstain if insufficient'])
    node(870,640,'Evidence validation',['Source IDs + exact quotes','Numeric safeguards','Validate before publish'])
    parts += ['''<text x="1010" y="337" class="small" style="fill:#287873">AI analysis</text>
      <text x="1010" y="362" class="small" style="fill:#287873">selected revisions</text>
      <text x="438" y="839" class="small" style="fill:#287873">AI analysis candidates → human review</text>
      <text x="30" y="875" class="small">Embeddings retrieve; GPT generates. Token accounting, cost estimates and organization budgets bound GPT use.</text>
      <text x="30" y="899" class="small">The provider is configurable. Real paid GPT Q&amp;A was validated locally; deterministic workflows remain independent.</text></svg>''']
    svg=''.join(parts)
    (ROOT/'architecture/documind-architecture.svg').write_text(svg,encoding='utf-8')
    (ROOT/'architecture/documind-architecture-case.svg').write_text(svg.replace('width="1800" height="1388"','width="1180" height="910"'),encoding='utf-8')

def case_architecture_section():
    return '''<p class="eyebrow">02 / A hybrid system, not competing alternatives</p>
    <h2>Local retrieval.<br/>GPT intelligence.</h2>
    <p class="lead">Local vectors find relevant evidence. GPT generates grounded answers and configured AI analysis. Deterministic rules and human workflows add reliability and control.</p>
    <figure class="shot" style="padding:8px;margin-top:20px"><img src="../architecture/documind-architecture-case.svg" style="height:480px;object-fit:contain"/><figcaption>Chat uses retrieved chunks. Structured AI uses selected authorized revisions directly through the worker. Citations and source validation are application-managed.</figcaption></figure>
    <div class="grid hybrid-summary" style="margin-top:18px">
      <div class="card"><div class="num">LOCAL / RETRIEVAL + RULES</div><h3>Vectors are not answers</h3><p>Local all-MiniLM-L6-v2 produces 384D vectors by default. No paid embedding API. Rules handle supported tasks without GPT.</p></div>
      <div class="card"><div class="num">OPENAI / GENERATIVE INTELLIGENCE</div><h3>Generate, validate, review</h3><p>GPT synthesizes cited answers and configured extraction, risk/obligation and comparison candidates. Source checks and review follow.</p></div>
    </div>'''

def carousel_hybrid_section():
    return '''<p class="eyebrow">Under the hood / complementary strengths</p>
    <h2>Embeddings retrieve.<br/>GPT generates.</h2>
    <p class="lead">One hybrid system. Local semantic search supplies evidence for real GPT-powered intelligence.</p>
    <div style="margin-top:34px">
      <div class="step"><b>01</b><div><strong>Parse → selective OCR → chunk</strong><p>The worker preserves document and page references.</p></div></div>
      <div class="step"><b>02</b><div><strong>Encode locally → pgvector</strong><p>all-MiniLM-L6-v2: 384D chunk and question vectors. Cosine retrieval within the organization.</p></div></div>
      <div class="step"><b>03</b><div><strong>Evidence → OpenAI GPT</strong><p>Responses API synthesizes grounded answers. The application validates references and quotations.</p></div></div>
      <div class="step"><b>04</b><div><strong>Rules + human oversight</strong><p>Deterministic tasks work without an LLM. Structured AI candidates enter the review workflow.</p></div></div>
    </div><p class="note">Local embeddings avoid paid embedding requests; they do not generate natural-language answers. Structured AI reads selected revisions directly.</p>'''
