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
        pass  # suppress request logs

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
        # Serve index.html for root
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

    system = """You are a senior B2B content strategist auditing marketing content for Mitel, a unified communications company. Mitel sells phone systems, collaboration tools (MiCollab, Mitel One), and contact center solutions to mid-market and enterprise businesses.

Score on 4 dimensions (integers 0–100). Return ONLY valid JSON — no preamble, no markdown fences.

1. TONE & BRAND: Professional, direct, confident Mitel voice. Penalize clichés (seamless/robust/innovative/cutting-edge), passive voice, fluff. Reward specific outcomes, numbers, active voice.
2. SEO / AEO: Score against ALL provided keywords. Penalize missing keywords in headline/subheads, walls of text. Reward natural integration, H2/H3 headers, direct answers, FAQ structure.
3. PERSONA FIT: Score against ALL selected personas simultaneously. Show per-persona alignment and gaps.
4. CRO READINESS: Ability to convert readers. Penalize no CTA, buried value prop, features without benefits. Reward clear CTA, benefit-first language, social proof.

Return EXACTLY:
{"overall_score":<int>,"dimensions":{"tone":{"score":<int>,"summary":"<max 12 words>","fixes":["<fix>","<fix>","<fix>"]},"seo":{"score":<int>,"summary":"<max 12 words>","fixes":["<fix>","<fix>","<fix>"]},"persona":{"score":<int>,"summary":"<max 12 words>","fixes":["<fix>","<fix>","<fix>"],"persona_breakdown":[{"name":"<label>","alignment":<int>,"gap":"<max 10 words>"}]},"cro":{"score":<int>,"summary":"<max 12 words>","fixes":["<fix>","<fix>","<fix>"]}}}"""

    user = f"CONTENT:\n---\n{content}\n---\nPERSONAS:\n{persona_lines}\nKEYWORDS: {', '.join(keywords) if keywords else 'none'}\n\nJSON only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1200,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def build_keywords_payload(body: dict) -> dict:
    content = body.get("content", "")
    existing = body.get("existing", [])

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": "You are an SEO strategist for Mitel, a B2B unified communications company. Return ONLY a JSON array of 6-8 keyword strings — no preamble, no fences.",
        "messages": [{
            "role": "user",
            "content": f"Suggest the most valuable SEO/AEO keywords for this content. Focus on B2B telecom and unified communications terms.\n\nContent:\n---\n{content}\n---\nExisting keywords: {', '.join(existing) if existing else 'none'}\n\nReturn: [\"keyword 1\",\"keyword 2\",...]"
        }],
    }


def build_regen_payload(body: dict) -> dict:
    content = body.get("content", "")
    fixes = body.get("fixes", [])
    fixes_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fixes))

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "system": "You are a senior B2B content writer for Mitel. Rewrite the content applying ONLY the specified improvements. Keep the same length and structure. Return ONLY the rewritten content — no explanation, no preamble.",
        "messages": [{
            "role": "user",
            "content": f"ORIGINAL:\n---\n{content}\n---\nAPPLY:\n{fixes_text}\n\nReturn only the improved content."
        }],
    }


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("Running on http://0.0.0.0:5000")
    server.serve_forever()
