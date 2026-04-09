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

Score on 4 dimensions (integers 0–100). Be rigorous and honest — scores below 70 should be common for average content. Return ONLY valid JSON, no preamble, no markdown fences.

SCORING CRITERIA:

1. TONE & BRAND (score: tone)
Mitel's voice: professional, direct, confident, outcome-focused, human. Never hypey or corporate-stiff.
- Score 90+: Every sentence earns its place. Specific outcomes, numbers, active voice throughout. Zero clichés.
- Score 70-89: Mostly strong but some vague claims or passive constructions.
- Score 50-69: Noticeable clichés (seamless/robust/innovative/cutting-edge/next-gen/game-changing/empower), passive voice, or marketing fluff present.
- Score below 50: Heavy clichés, vague claims with no evidence, or tone feels generic and could be any vendor.

2. SEO / AEO (score: seo)
Score for search engine discoverability AND AI answer engine optimization (featured snippets, direct answers).
- Score 90+: Keywords appear naturally in H1, first paragraph, and subheadings. Content directly answers the implied search query. FAQ or Q&A structure present. Scannable.
- Score 70-89: Keywords present but placement could be stronger. Some structure but could be more scannable.
- Score 50-69: Keywords sparse or forced. Wall-of-text paragraphs. Missing subheads.
- Score below 50: Keywords absent or stuffed unnaturally. No structure. Would not rank or appear in AI answers.

3. PERSONA FIT (score: persona)
Score against ALL selected personas simultaneously.
- Score 90+: Content speaks directly to the role-specific concerns of every selected persona. Technical depth matches each audience. Pain points addressed explicitly.
- Score 70-89: Relevant to most personas but misses specific pain points for some.
- Score 50-69: Generic content that could apply to anyone. Misses role-specific language entirely for some personas.
- Score below 50: Wrong audience entirely, or ignores primary pain points across most selected personas.

4. CRO READINESS (score: cro)
- Score 90+: Clear, compelling CTA. Value proposition in first paragraph. Benefits stated before features. Social proof present. Logical conversion path.
- Score 70-89: CTA present but could be stronger. Value prop present but not prominent.
- Score 50-69: CTA buried or generic ("Contact us"). Features listed without connecting to business outcomes.
- Score below 50: No CTA. No value proposition. Pure feature list. Reader has no reason to act.

Return EXACTLY this structure:
{"overall_score":<int>,"dimensions":{"tone":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":["<specific actionable fix>","<specific actionable fix>","<specific actionable fix>"]},"seo":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":["<specific actionable fix>","<specific actionable fix>","<specific actionable fix>"]},"persona":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":["<specific actionable fix>","<specific actionable fix>","<specific actionable fix>"],"persona_breakdown":[{"name":"<persona label>","alignment":<int 0-100>,"gap":"<max 10 words>"}]},"cro":{"score":<int>,"summary":"<one honest verdict, max 12 words>","fixes":["<specific actionable fix>","<specific actionable fix>","<specific actionable fix>"]}}}"""

    user = f"CONTENT TO AUDIT:\n---\n{content}\n---\n\nTARGET PERSONAS:\n{persona_lines}\n\nKEYWORDS TO SCORE AGAINST: {', '.join(keywords) if keywords else 'none specified'}\n\nReturn JSON only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1400,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def build_keywords_payload(body: dict) -> dict:
    content = body.get("content", "")
    existing = body.get("existing", [])

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": "You are an SEO strategist for Mitel, a B2B unified communications company. Suggest keywords that will improve both traditional search rankings and AI engine visibility (AEO). Return ONLY a JSON array of 6-8 keyword strings — no preamble, no markdown fences.",
        "messages": [{
            "role": "user",
            "content": f"Analyze this content and suggest the most impactful SEO/AEO keywords to target. Focus on B2B telecom, unified communications, cloud phone systems, and contact center terms that real buyers search for.\n\nContent:\n---\n{content}\n---\n\nAlready targeting: {', '.join(existing) if existing else 'none'}\n\nSuggest NEW keywords not already in the list. Return: [\"keyword 1\",\"keyword 2\",...]"
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

    system = """You are a senior B2B copywriter at Mitel. Your job is to substantially rewrite marketing content so it scores significantly higher on tone, SEO, persona fit, and conversion.

REWRITING RULES — follow these without exception:
1. REPLACE every cliché immediately: never use seamless, robust, innovative, cutting-edge, next-gen, game-changing, empower, leverage, utilize, holistic, synergy, transformative
2. MAKE IT SPECIFIC: replace vague claims with concrete outcomes and numbers wherever possible (e.g. "reduce call handling time", "connect 500+ users", "99.99% uptime SLA")
3. ACTIVE VOICE ONLY: rewrite every passive construction
4. FRONT-LOAD THE VALUE: the first sentence must state what the reader gains — not what the product does
5. INTEGRATE KEYWORDS NATURALLY: weave the target keywords into headline, first paragraph, and subheadings — not forced, not stuffed
6. ADD A CLEAR CTA: if none exists, add one. If weak, make it specific (e.g. "Book a 30-minute demo" not "Contact us")
7. PRESERVE STRUCTURE: keep roughly the same length and any existing section breaks
8. APPLY EVERY REQUESTED FIX: do not skip any improvement from the list

Return ONLY the rewritten content. No explanation, no preamble, no "Here is the improved version:" — just the content itself."""

    user = f"""ORIGINAL CONTENT:
---
{content}
---

TARGET PERSONAS: {persona_context}
KEYWORDS TO INTEGRATE: {kw_context}

IMPROVEMENTS TO APPLY:
{fixes_text}

Rewrite the content now. Make it meaningfully better — not cosmetically tweaked. The score should improve by at least 10-15 points on each targeted dimension. Return only the rewritten content."""

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
