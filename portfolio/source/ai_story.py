"""Editorial presentation of the developer's real manual API test record.

This is a transcription panel, never a simulated product screenshot.
"""
import json
from html import escape
from pathlib import Path

RECORD = json.loads((Path(__file__).resolve().parents[1] / 'verification/live-openai-validation.json').read_text(encoding='utf-8'))

def record_panel():
    return f'''<section class="live-record">
      <p class="label">Manual test record · supplied by Fiza Ahmad</p>
      <h3>{escape(RECORD['reported_model_name'])} <span> / {escape(RECORD['model'])}</span></h3>
      <p class="live-question">“{escape(RECORD['question'])}”</p>
      <blockquote>{escape(RECORD['answer'])}</blockquote>
      <dl class="live-metrics">
        <div><dt>Input tokens</dt><dd>{RECORD['input_tokens']}</dd></div>
        <div><dt>Output tokens</dt><dd>{RECORD['output_tokens']}</dd></div>
        <div><dt>Estimated request cost</dt><dd>USD {escape(RECORD['estimated_cost_usd'])}</dd></div>
      </dl>
      <p class="record-note">Real paid local Q&amp;A test with source citations. One recorded example, not a benchmark or billing invoice.</p>
    </section>'''

def case_ai_section():
    return '''<p class="eyebrow">04 / Real-world AI integration &amp; cost optimization</p>
    <h2>Paid GPT validation.<br/>Deliberate cost control.</h2>
    <p class="lead">I selected GPT-6 Luna with cost efficiency in mind. A real local Responses API request retrieved document evidence, synthesized an answer and displayed citations, token usage and an estimated cost.</p>''' + record_panel() + '''
    <div class="grid" style="margin-top:20px">
      <div class="card"><div class="num">PAY FOR SYNTHESIS</div><h3>Keep embeddings local</h3><p>Sentence Transformers avoids paid embedding requests. Organization-scoped pgvector retrieval supplies relevant passages rather than whole-document context.</p></div>
      <div class="card"><div class="num">MAKE SPEND EXPLICIT</div><h3>Bound usage, retain choice</h3><p>Track tokens and estimated cost; enforce organization-level token/cost budgets. Keep model selection behind the existing provider interface.</p></div>
    </div>
    <div class="callout"><p><strong>Evidence boundary:</strong> source IDs, exact quotes and numeric checks improve traceability; human review remains necessary. No comparative accuracy or model-quality benchmark is claimed.</p></div>
    <p class="note">The figures are Fiza Ahmad’s recorded manual result. The same question/source terms are documented in Phase 8; no raw provider log or authentic live-request screenshot was located in the repository. The request was not replayed for these assets.</p>'''

def carousel_ai_section():
    return '''<p class="eyebrow">Real API validation / cost-conscious engineering</p>
    <h2>Real GPT.<br/>Measured usage.</h2>
    <p class="lead">I successfully tested document-grounded Q&amp;A locally with a real, paid OpenAI Responses API request.</p>''' + record_panel() + '''
    <p class="captionline">The tradeoff: a cost-conscious model choice + local embeddings + scoped retrieval + token/cost budgets.</p>
    <p class="note">Developer-provided record; no quality benchmark or claim of equal accuracy to higher-cost models. No new paid call was made for this showcase.</p>'''

STYLE = '''
.live-record{margin-top:22px;padding:22px 24px;border:1px solid #d9d0ef;border-radius:16px;background:linear-gradient(125deg,#fff,#f0edfb)}
.live-record .label{font-size:10px;margin:0 0 10px;letter-spacing:.1em}
.live-record h3{font-size:21px;letter-spacing:-.025em;margin:0 0 14px}
.live-record h3 span{font-size:12px;font-weight:400;color:#65718a;letter-spacing:0}
.live-question{font-size:14px;font-weight:600;color:#403961}
.live-record blockquote{margin:12px 0 18px;font-size:17px;line-height:1.6;letter-spacing:-.015em;color:#24334d}
.live-metrics{display:grid;grid-template-columns:1fr 1fr 2fr;gap:12px;padding-top:15px;border-top:1px solid #dcd6eb;margin:0}
.live-metrics dt{font-size:10px;color:#626e86;margin-bottom:5px}
.live-metrics dd{margin:0;font-size:26px;line-height:1.2;font-weight:650;letter-spacing:-.035em;color:#6246b0;white-space:nowrap}
.record-note{font-size:10px;line-height:1.6;color:#626e86;margin-top:14px}
.slide .live-record{margin-top:28px;padding:28px}
.slide .live-record .label{font-size:15px;margin-bottom:14px}
.slide .live-record h3{font-size:30px;margin-bottom:18px}
.slide .live-record h3 span{font-size:20px}
.slide .live-question{font-size:26px;line-height:1.4}
.slide .live-record blockquote{font-size:28px;line-height:1.5;margin:18px 0 23px}
.slide .live-metrics{padding-top:22px;gap:16px}
.slide .live-metrics dt{font-size:18px}
.slide .live-metrics dd{font-size:34px}
.slide .record-note{font-size:18px;line-height:1.5;margin-top:20px}
.slide.dark .live-record{background:linear-gradient(125deg,#1a243a,#28223f);border-color:#4b406a}
.slide.dark .live-record h3,.slide.dark .live-record blockquote{color:#f0f2fa}
.slide.dark .live-record .label{color:#bba5ff}
.slide.dark .live-question,.slide.dark .live-metrics dd{color:#d6c5ff}
.slide.dark .live-record h3 span,.slide.dark .live-metrics dt,.slide.dark .record-note{color:#b8c2d7}
.slide.dark .live-metrics{border-color:#4b406a}
'''
