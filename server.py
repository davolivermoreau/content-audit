import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"


def call_anthropic(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path not in ("/api/analyze", "/api/keywords", "/api/regenerate"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        try:
            if self.path == "/api/analyze":
                result = call_anthropic(build_analyze_payload(body))
            elif self.path == "/api/keywords":
                result = call_anthropic(build_keywords_payload(body))
            elif self.path == "/api/regenerate":
                result = call_anthropic(build_regen_payload(body))

            text = result.get("content", [{}])[0].get("text", "")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"text": text}).encode())

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": error_body}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()


def build_analyze_payload(body: dict) -> dict:
    content = body.get("content", "")
    personas = body.get("personas", [])
    keywords = body.get("keywords", [])

    persona_lines = "\n".join(
        f"- {p['label']} ({p['role']}): pain points — {p['pain']}"
        for p in personas
    )

    system = """You are a senior B2B content strategist auditing marketing content for Mitel, a unified communications company. Mitel sells phone systems, collaboration tools (MiCollab, Mitel One), and contact center solutions to mid-market and enterprise businesses globally.

Score on 4 dimensions (integers 0-100). Be rigorous and honest. Return ONLY valid JSON, no preamble, no markdown fences.

IMPORTANT RULES:
- Only flag issues that are ACTUALLY PRESENT in the submitted text. Never invent violations or hallucinate problems.
- Fixes must reference specific things found in the content, not generic advice.
- Do NOT recommend adding TCO data, ROI calculations, or cost justification — Mitel content rarely includes this and it is not expected.
- Do NOT penalize passive voice — there are too many legitimate exceptions in B2B writing.

SCORING CRITERIA:

1. TONE & BRAND (score: tone)
Mitel's voice: professional, direct, confident, outcome-focused, human.
- Score 90+: Every sentence earns its place. Claims are concrete and defensible. No empty marketing language.
- Score 70-89: Mostly strong but contains some vague or unsubstantiated claims.
- Score 50-69: Contains marketing fluff that is actually present in the text — buzzwords, overpromising, or claims with no supporting evidence.
- Score below 50: Dominated by vague, vendor-generic language or hype with no substance.

2. SEO / AEO (score: seo)
Score for search engine discoverability AND AI answer engine optimization.
- Score 90+: Keywords in H1, first paragraph, subheadings. Directly answers the implied search query. Scannable structure.
- Score 70-89: Keywords present but placement could be stronger. Some structure but not fully scannable.
- Score 50-69: Keywords sparse or forced. Wall-of-text paragraphs. Missing subheads.
- Score below 50: Keywords absent or stuffed. No structure. Would not rank or appear in AI answers.

3. PERSONA FIT (score: persona)
Score against ALL selected personas simultaneously. Focus on role-specific language, depth, and pain points that are actually addressable in marketing content.
- Score 90+: Speaks directly to the role-specific concerns of every selected persona. Right technical depth for each audience.
- Score 70-89: Relevant to most personas but misses specific pain points for some.
- Score 50-69: Generic content that misses role-specific language for some personas.
- Score below 50: Wrong audience or ignores primary pain points across most selected personas.

4. CRO READINESS (score: cro)
- Score 90+: Clear compelling CTA. Value proposition in first paragraph. Benefits stated before features. Social proof present.
- Score 70-89: CTA present but could be stronger. Value prop present but not prominent.
- Score 50-69: CTA buried or generic. Features listed without connecting to business outcomes.
- Score below 50: No CTA. No value proposition. Pure feature list.

For each fix, provide an impact score (integer 1-100) for the estimated score improvement if implemented.

Return EXACTLY this structure:
{"overall_score":<int>,"dimensions":{"tone":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":[{"text":"<specific fix referencing actual content>","impact":<int 1-100>},{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>}]},"seo":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":[{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>}]},"persona":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":[{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>}],"persona_breakdown":[{"name":"<persona label>","alignment":<int 0-100>,"gap":"<max 10 words>"}]},"cro":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":[{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>},{"text":"<fix>","impact":<int>}]}}}"""

    user = f"CONTENT TO AUDIT:\n---\n{content}\n---\n\nTARGET PERSONAS:\n{persona_lines}\n\nKEYWORDS TO SCORE AGAINST: {', '.join(keywords) if keywords else 'none specified'}\n\nReturn JSON only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1600,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def build_keywords_payload(body: dict) -> dict:
    content = body.get("content", "")
    existing = body.get("existing", [])

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": "You are an SEO strategist for Mitel, a B2B unified communications company. Suggest keywords that improve both traditional search rankings and AI engine visibility (AEO). Return ONLY a JSON array of 6-8 keyword strings — no preamble, no markdown fences.",
        "messages": [{
            "role": "user",
            "content": f"Analyze this content and suggest the most impactful SEO/AEO keywords. Focus on B2B telecom, unified communications, cloud phone systems, and contact center terms that real buyers search for.\n\nContent:\n---\n{content}\n---\n\nAlready targeting: {', '.join(existing) if existing else 'none'}\n\nSuggest NEW keywords not already in the list. Return: [\"keyword 1\",\"keyword 2\",...]"
        }],
    }


def build_regen_payload(body: dict) -> dict:
    content = body.get("content", "")
    fixes = body.get("fixes", [])
    keywords = body.get("keywords", [])
    personas = body.get("personas", [])

    persona_context = ", ".join(f"{p['label']} ({p['role']})" for p in personas) if personas else "general B2B audience"
    kw_context = ", ".join(keywords) if keywords else "none"
    fixes_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fixes))

    system = """You are a senior B2B copywriter at Mitel. Your job is to substantially rewrite marketing content so it scores higher on tone, SEO, persona fit, and conversion.

REWRITING RULES:
1. Only fix what is actually in the text — do not invent problems or add content that has no basis in the original
2. Replace vague claims with concrete outcomes and numbers where possible
3. Front-load the value: the first sentence should state what the reader gains
4. Integrate target keywords naturally into headline, first paragraph, and subheadings
5. Strengthen or add a clear CTA if missing or weak (e.g. "Book a 30-minute demo" not "Contact us")
6. Preserve the overall structure and length
7. Apply every requested fix from the list

Return ONLY the rewritten content. No explanation, no preamble."""

    user = f"""ORIGINAL CONTENT:
---
{content}
---

TARGET PERSONAS: {persona_context}
KEYWORDS TO INTEGRATE: {kw_context}

IMPROVEMENTS TO APPLY:
{fixes_text}

Rewrite now. Return only the rewritten content."""

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2500,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("Running on http://0.0.0.0:5000")
    server.serve_forever()
