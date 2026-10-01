"""Optional LLM extraction (Claude). PHI is redacted first and every returned quote is re-verified."""
import json
import os
from .models import Fact, Source, EXTRACTED
from .safety import redact
from .utils import norm

PROMPT = """You extract ADMINISTRATIVE facts from ONE patient document for care coordination.
Never diagnose, interpret results, or suggest treatment. Return ONLY JSON:
{"facts":[{"kind":"medication|lab_result|instruction|referral|appointment|visit|patient_question",
"date":"YYYY-MM-DD or null","description":"short","quote":"EXACT text copied from the document","page":1}]}
If you are unsure, omit the fact. The quote must be copied character-for-character."""


def extract_with_claude(doc, start_id: int = 1) -> list:
    import anthropic
    client = anthropic.Anthropic()
    pages = [redact(p) for p in doc.pages]
    body = "\n\n".join(f"[page {i}]\n{p}" for i, p in enumerate(pages, 1))
    resp = client.messages.create(model=os.getenv("CAREBRIDGE_MODEL", "claude-sonnet-5-5"), max_tokens=2000,
                                  system=PROMPT, messages=[{"role": "user", "content": body}])
    raw = "".join(b.text for b in resp.content if b.type == "text").replace("```json", "").replace("```", "")
    out = []
    for i, f in enumerate(json.loads(raw).get("facts", []), start_id):
        page = int(f.get("page", 1))
        if not (1 <= page <= len(pages)) or norm(f["quote"]) not in norm(pages[page - 1]):
            continue  # hallucinated quote -> rejected
        out.append(Fact(id=f"evt_{i:03d}", kind=f["kind"], date=f.get("date"), description=f["description"],
                        label=EXTRACTED, source=Source(doc.name, page, f["quote"]), confidence=0.8,
                        data={"origin": "llm"}))
    return out
