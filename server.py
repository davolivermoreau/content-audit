import os
import json
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
SETTINGS_PASSWORD = os.environ.get("SETTINGS_PASSWORD", "MiTeLdEv26!")
API_URL = "https://api.anthropic.com/v1/messages"
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "personas": [
        {"id": "it_dm",    "label": "IT Decision Maker",       "role": "CIO / IT Director",        "pain": "reliability, security, vendor consolidation, reducing complexity"},
        {"id": "biz_dm",   "label": "Business Decision Maker", "role": "CEO / CFO / COO",           "pain": "employee productivity, cost control, business continuity, ROI"},
        {"id": "it_admin", "label": "IT Admin / Engineer",     "role": "Systems administrator",     "pain": "ease of management, uptime, integration, minimal maintenance"},
        {"id": "end_user", "label": "End User",                "role": "Daily communications user", "pain": "ease of use, call quality, mobile access, consistency"},
        {"id": "partner",  "label": "Channel Partner",         "role": "Reseller / MSP / VAR",      "pain": "margins, competitive positioning, customer retention"}
    ],
    "scoring": {
        "tone": "Mitel's voice is professional, direct, confident, outcome-focused, and human. Reward specific outcomes and concrete claims. Penalize vague marketing language, buzzwords actually present in the text, or unsubstantiated promises. Never invent violations — only flag what is actually in the content.",
        "seo": "Score for both traditional search and AI answer engine optimization. Reward natural keyword integration in headline and first paragraph, scannable H2/H3 structure, and content that directly answers implied search queries. Penalize keyword stuffing, walls of text, and missing structure.",
        "persona": "Score against all selected personas simultaneously. Reward role-specific language, appropriate technical depth, and content that addresses each persona's actual pain points. Penalize generic content that could apply to anyone. Do not recommend adding TCO data or ROI calculations.",
        "cro": "Score the content's ability to convert readers. Reward a clear value proposition in the first paragraph, benefit-first language, and a specific CTA. Penalize buried value props, feature lists without business outcomes, and generic CTAs like 'Contact us'."
    }
}


def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
            result = dict(DEFAULT_SETTINGS)
            result.update(saved)
            return result
    except Exception:
        return DEFAULT_SETTINGS


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def call_anthropic(payload: dict) -> dict:
    api_key = load_settings().get("api_key") or ANTHROPIC_KEY
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/settings":
            settings = load_settings()
            public = {
                "personas": settings.get("personas", DEFAULT_SETTINGS["personas"]),
                "scoring":  settings.get("scoring",  DEFAULT_SETTINGS["scoring"]),
                "has_api_key": bool(settings.get("api_key") or ANTHROPIC_KEY)
            }
            self.send_json(200, public)
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        allowed = ("/api/analyze", "/api/keywords", "/api/regenerate",
                   "/api/settings", "/api/settings/auth")
        if self.path not in allowed:
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        try:
            if self.path == "/api/settings/auth":
                if body.get("password") == SETTINGS_PASSWORD:
                    self.send_json(200, {"ok": True})
                else:
                    self.send_json(401, {"ok": False, "error": "Incorrect password"})
                return

            if self.path == "/api/settings":
                if body.get("password") != SETTINGS_PASSWORD:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                current = load_settings()
                if "personas" in body:
                    current["personas"] = body["personas"]
                if "scoring" in body:
                    current["scoring"] = body["scoring"]
                if "api_key" in body:
                    current["api_key"] = body["api_key"]
                save_settings(current)
                self.send_json(200, {"ok": True})
                return

            if self.path == "/api/analyze":
                result = call_anthropic(build_analyze_payload(body))
            elif self.path == "/api/keywords":
                result = call_anthropic(build_keywords_payload(body))
            elif self.path == "/api/regenerate":
                result = call_anthropic(build_regen_payload(body))

            text = result.get("content", [{}])[0].get("text", "")
            self.send_json(200, {"text": text})

        except urllib.error.HTTPError as e:
            self.send_json(e.code, {"error": e.read().decode()})
        except Exception as e:
            self.send_json(500, {"error": str(e)})


def build_analyze_payload(body: dict) -> dict:
    content  = body.get("content", "")
    personas = body.get("personas", [])
    keywords = body.get("keywords", [])
    settings = load_settings()
    scoring  = settings.get("scoring", DEFAULT_SETTINGS["scoring"])

    persona_lines = "\n".join(
        f"- {p['label']} ({p['role']}): pain points — {p['pain']}"
        for p in personas
    )

    system = f"""You are a senior B2B content strategist auditing marketing content for Mitel, a unified communications company. Mitel sells phone systems, collaboration tools (MiCollab, Mitel One), and contact center solutions to mid-market and enterprise businesses globally.

Score on 4 dimensions (integers 0-100). Be rigorous and honest. Return ONLY valid JSON, no preamble, no markdown fences.

CRITICAL: Only flag issues ACTUALLY PRESENT in the submitted text. Never invent violations. Fixes must reference specific content found in the text.

SCORING CRITERIA:

1. TONE & BRAND (score: tone)
{scoring['tone']}
- Score 90+: Excellent. Concrete, specific, defensible claims throughout.
- Score 70-89: Good but some vague or unsubstantiated language present.
- Score 50-69: Noticeable fluff or buzzwords actually found in the text.
- Score below 50: Dominated by generic, hypey, or unsubstantiated content.

2. SEO / AEO (score: seo)
{scoring['seo']}
- Score 90+: Keywords well-placed, strong structure, answers implied query directly.
- Score 70-89: Keywords present but placement or structure could be stronger.
- Score 50-69: Sparse keywords, limited structure, hard to scan.
- Score below 50: No keyword strategy visible, no structure.

3. PERSONA FIT (score: persona)
{scoring['persona']}
- Score 90+: Speaks to every selected persona's role and concerns directly.
- Score 70-89: Relevant to most but misses some pain points.
- Score 50-69: Generic, misses role-specific language for some personas.
- Score below 50: Wrong audience or ignores most persona pain points.

4. CRO READINESS (score: cro)
{scoring['cro']}
- Score 90+: Clear CTA, value prop upfront, benefits before features.
- Score 70-89: CTA and value prop present but not prominent.
- Score 50-69: CTA buried or generic, feature-first.
- Score below 50: No CTA, no value proposition.

For each fix, provide an impact score (integer 1-100) estimating the score improvement if implemented.

Return EXACTLY:
{{"overall_score":<int>,"dimensions":{{"tone":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}},"seo":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}},"persona":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}],"persona_breakdown":[{{"name":"<label>","alignment":<int>,"gap":"<max 10 words>"}}]}},"cro":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}}}}}}"""

    user = f"CONTENT TO AUDIT:\n---\n{content}\n---\n\nTARGET PERSONAS:\n{persona_lines}\n\nKEYWORDS TO SCORE AGAINST: {', '.join(keywords) if keywords else 'none specified'}\n\nReturn JSON only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1600,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def build_keywords_payload(body: dict) -> dict:
    content  = body.get("content", "")
    existing = body.get("existing", [])
    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": "You are an SEO strategist for Mitel, a B2B unified communications company. Return ONLY a JSON array of 6-8 keyword strings — no preamble, no markdown fences.",
        "messages": [{
            "role": "user",
            "content": f"Suggest the most impactful SEO/AEO keywords for this content. Focus on B2B telecom, unified communications, cloud phone systems, contact center terms.\n\nContent:\n---\n{content}\n---\n\nAlready targeting: {', '.join(existing) if existing else 'none'}\n\nReturn only NEW keywords not in the list: [\"keyword 1\",\"keyword 2\",...]"
        }],
    }


def build_regen_payload(body: dict) -> dict:
    content  = body.get("content", "")
    fixes    = body.get("fixes", [])
    keywords = body.get("keywords", [])
    personas = body.get("personas", [])

    persona_context = ", ".join(f"{p['label']} ({p['role']})" for p in personas) if personas else "general B2B audience"
    kw_context  = ", ".join(keywords) if keywords else "none"
    fixes_text  = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fixes))

    system = """You are a senior B2B copywriter at Mitel. Rewrite the content to meaningfully improve its tone, SEO, persona fit, and conversion — applying only the listed improvements.

Rules:
- Only fix what is actually in the text
- Replace vague claims with concrete outcomes where possible
- Front-load the value proposition
- Integrate target keywords naturally
- Strengthen or add a specific CTA if weak or missing
- Preserve overall structure and length
- Apply every listed fix

Return ONLY the rewritten content. No explanation, no preamble."""

    user = f"ORIGINAL:\n---\n{content}\n---\nPERSONAS: {persona_context}\nKEYWORDS: {kw_context}\n\nFIXES:\n{fixes_text}\n\nReturn only the rewritten content."

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
