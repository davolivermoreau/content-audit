import os
import json
import urllib.request
import urllib.error
import re
from html.parser import HTMLParser
from http.server import HTTPServer, SimpleHTTPRequestHandler

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
SETTINGS_PASSWORD = os.environ.get("SETTINGS_PASSWORD", "MiTeLdEv26!")
API_URL = "https://api.anthropic.com/v1/messages"
SETTINGS_FILE = "settings.json"

# ── Real Mitel skill content injected into scoring prompts ────────────────────

TONE_SKILL = """
MITEL TONE & BRAND STANDARDS:
- Voice: Clear, confident, thoughtful. Warmly professional, pragmatic.
- Sentences: Short-to-medium (≤20 words). Longer (≤35 words) only for nuance.
- Hook rule: First two lines must be memorable and fluid — vivid, distinctive, natural transition into body.
- Priority order: Accuracy > Conversion > SEO
- Subheadings every 150-300 words for scannability.
- Use "we" for partnership tone.
- Each paragraph = 1 clear point + support (data, analogy, or insight).
- Max 1 analogy/example per 400-500 words.
- Max 1 humor aside per 500 words, only if it reinforces the message.
- Rhetorical devices (parallelism, tricolon, antithesis, etc.): max 1 of any type per piece.

BANNED WORDS & PHRASES (flag only if actually present in the text):
- Overblown clichés: game-changer, cutting-edge, revolutionary, state-of-the-art, world-class, next-level, unmatched, unparalleled, industry-leading, best-in-class (without proof)
- Vague hype: unlock potential, move the needle, future-proof, synergy, outside the box, low-hanging fruit, bleeding edge
- Overused metaphors: bridge the gap, silver bullet, tip of the iceberg, rocket ship, moonshot, seamless experience (without proof)
- Filler qualifiers: very/really/truly, amazing/incredible/fantastic (unless quantified), completely/absolutely
- LLM patterns: "In today's fast-paced world…", generic "Imagine…", ending with "The future is now", empty 3-part lists
- Trend buzzwords: AI-powered, digital transformation (unless defined/contextualized)

CRITICAL: Only flag banned words/phrases that ACTUALLY APPEAR in the submitted text. Never invent violations.
"""

SEO_AEO_SKILL = """
MITEL SEO & AEO STANDARDS:
- Strategy: 70% traditional SEO, 30% AEO (AI answer engine optimization).
- Priority: Organic conversions and qualified sessions — not vanity metrics.

KEYWORD PLACEMENT:
- Primary keyword must appear in: H1/title, first 100 words, at least one H2/H3, meta description.
- Keyword density: 1-2% (natural integration, not stuffed).
- Semantic keywords and variations throughout body.

CONTENT STRUCTURE FOR SEO:
- H2/H3 headers every 150-300 words.
- Bullet lists for 3+ items.
- Short paragraphs (3-5 sentences max).
- Internal links with descriptive anchor text.
- Meta title: <60 chars with keyword. Meta description: <155 chars.

AEO REQUIREMENTS (for AI answer engine citations):
- Direct, concise answers to implied questions — especially in opening paragraph.
- FAQ format highly effective: 1 primary question + 5-8 sub-questions, 100-200 word answers.
- Structured listicles with numbered H3s.
- Comparison tables for feature/product comparisons.
- Step-by-step guides with numbered, action-verb headers.
- schema.org/FAQPage markup recommended.
- Natural, conversational language that reads as a direct answer.
- Content must serve both click-through (SEO) and zero-click (AEO) discovery.

SEARCH INTENT ALIGNMENT:
- Informational (what/how/why): Educational articles, how-tos.
- Commercial investigation (best/compare/vs): Comparisons, case studies.
- Transactional (pricing/demo): Pricing pages, CTA-focused content.
"""

PERSONA_SKILL = """
MITEL BUYER PERSONAS:

PERSONA 1 — ECONOMIC BUYER (CFO / CIO / COO / VP Finance)
Decision criteria: TCO, ROI timeline, CapEx vs OpEx, vendor consolidation, risk mitigation, business continuity.
Pain points: Telecom costs out of control, too many vendors, can't support hybrid work, need to demonstrate ROI to board, legacy infrastructure capital burden.
Content that works: Business outcomes first, financial language (ROI, payback, NPV), quantified results, executive peer quotes, risk/continuity framing.
What to avoid: Technical depth, jargon without substance, over-promising on timelines.

PERSONA 2 — CHAMPION (Director IT Ops / VP Customer Experience / Head of UC)
Decision criteria: Career advancement through project success, user satisfaction, reliability (fewer support tickets), integration with existing stack, ease of management.
Pain points: Constant firefighting, poor user experience especially for remote workers, can't support business growth, too complex to manage, innovation blocked by legacy.
Content that works: Empower them as the hero, provide tools for internal selling, peer testimonials, implementation case studies, quick wins.
What to avoid: Making them feel like a middleman, content they can't repurpose internally.

PERSONA 3 — DECISION MAKER (VP IT / Director Telecom / IT Operations Manager)
Decision criteria: Architecture, security/compliance certifications, integration with Microsoft 365/Salesforce/ServiceNow, SLAs, ease of administration, migration path.
Pain points: Legacy PBX can't scale, call quality issues, integration nightmares, security/compliance pressure, vendor lock-in, lack of visibility and control.
Content that works: Technical architecture detail, SLA specifics, integration proof, reference customers in similar environments, migration paths.
What to avoid: Marketing fluff without technical backing, unrealistic implementation promises.

PERSONA 4 — TECHNICAL INFLUENCER (Network Engineer / IT Security / Sysadmin / Voice Engineer)
Decision criteria: Day-to-day administration, provisioning workflows, monitoring tools, security patching, bandwidth requirements, quality of vendor support.
Pain points: Poor admin UX, security vulnerabilities in legacy systems, slow provisioning, limited diagnostic tools, inadequate documentation.
Content that works: Hands-on technical detail, API and integration documentation, real configuration examples, support quality proof.
What to avoid: High-level marketing language, over-simplified technical claims.

PERSONA 5 — BUSINESS INFLUENCER (Dept Head / Operations Director / Contact Center Manager)
Decision criteria: How communication tools affect their team's productivity, customer experience, and ability to meet business goals.
Pain points: Poor tools hurt team productivity, contact center performance gaps, can't serve customers well across channels, remote work coordination problems.
Content that works: Outcome-focused, productivity metrics, customer experience improvements, before/after comparisons.
What to avoid: Technical depth, IT-centric language, generic claims without business context.

SCORING NOTE: Do not recommend adding TCO data or ROI calculations — Mitel content rarely includes this and it is not required.
"""

CRO_SKILL = """
MITEL CRO STANDARDS FOR CONTENT:
- Value proposition must appear in the first paragraph — not buried mid-page.
- Benefit-first language: state the outcome before the feature.
- CTA must be specific and action-oriented (e.g. "Book a 30-minute demo", "Download the guide", "See pricing") — not generic ("Contact us", "Learn more").
- CTA placement: visible above the fold and at natural decision points in the content.
- Social proof signals: customer logos, case study references, uptime SLAs, customer counts, awards — referenced where relevant.
- B2B content should address the buyer's stage: awareness (educate), consideration (compare/differentiate), decision (de-risk, prove).
- Objection handling: anticipate and address the top 1-2 objections the target persona would have.
- Urgency or reason to act: provide a clear reason why the reader should act now vs. later — without false urgency.
- For lead-gen pages: minimize friction in the path to conversion (clear next step, no unnecessary clicks).

CRO SCORING FOCUS FOR CONTENT AUDIT:
Score based on what is actually present in the submitted copy — not on assumptions about the surrounding page.
Reward: specific CTAs, upfront value proposition, benefit-first framing, social proof signals present in the text.
Penalize: buried value prop, feature-only lists, generic CTAs, no reason to act.
"""

DEFAULT_SETTINGS = {
    "personas": [
        {"id": "econ_buyer",  "label": "Economic Buyer",       "role": "CFO / CIO / COO",                     "pain": "ROI, vendor consolidation, business continuity, controlling telecom costs"},
        {"id": "champion",    "label": "Champion",              "role": "Director IT / VP Customer Experience", "pain": "user satisfaction, reliability, ease of management, career advancement"},
        {"id": "decision_mk", "label": "Decision Maker",        "role": "VP IT / Director Telecom",             "pain": "scalability, integrations, security, SLAs, migration complexity"},
        {"id": "tech_inf",    "label": "Technical Influencer",  "role": "Network / Voice / Security Engineer",  "pain": "admin UX, provisioning, diagnostics, security patching, vendor support"},
        {"id": "biz_inf",     "label": "Business Influencer",   "role": "Dept Head / Contact Center Manager",   "pain": "team productivity, customer experience, remote work coordination"},
    ],
    "scoring": {
        "tone": TONE_SKILL.strip(),
        "seo": SEO_AEO_SKILL.strip(),
        "persona": PERSONA_SKILL.strip(),
        "cro": CRO_SKILL.strip(),
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



class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            content = attrs.get("content", "")
            if name in ("description", "og:description") and not self.description:
                self.description = content
            if name in ("og:title",) and not self.title:
                self.title = content

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and not self.title:
            self.title += data.strip()


def fetch_meta(url: str) -> dict:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MitelContentAudit/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read(80000).decode("utf-8", errors="ignore")
        parser = MetaParser()
        parser.feed(raw)
        return {
            "title": parser.title.strip(),
            "description": parser.description.strip(),
            "ok": True
        }
    except Exception as e:
        return {"title": "", "description": "", "ok": False, "error": str(e)}

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
                   "/api/settings", "/api/settings/auth", "/api/fetch-meta",
                   "/api/fetch-url", "/api/crosslinks")
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

            if self.path == "/api/fetch-meta":
                result = fetch_meta(body.get("url", ""))
                self.send_json(200, result)
                return

            if self.path == "/api/fetch-url":
                meta = fetch_meta(body.get("url", ""))
                # Also extract body text for content field
                try:
                    req = urllib.request.Request(
                        body.get("url", ""),
                        headers={"User-Agent": "Mozilla/5.0 (compatible; MitelContentAudit/1.0)"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        raw = resp.read(200000).decode("utf-8", errors="ignore")
                    # Strip tags, collapse whitespace
                    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL|re.IGNORECASE)
                    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL|re.IGNORECASE)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    text = text[:8000]  # cap at ~8k chars
                    self.send_json(200, {"text": text, "title": meta.get("title",""), "ok": True})
                except Exception as e:
                    self.send_json(200, {"text": "", "title": "", "ok": False, "error": str(e)})
                return

            if self.path == "/api/crosslinks":
                result = call_anthropic(build_crosslinks_payload(body))
                text = result.get("content", [{}])[0].get("text", "")
                self.send_json(200, {"text": text})
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

    persona_lines = "\n".join(
        f"- {p['label']} ({p['role']}): pain points — {p['pain']}"
        for p in personas
    )

    system = f"""You are a senior B2B content strategist auditing marketing content for Mitel, a unified communications company. You have deep knowledge of Mitel's brand standards, buyer personas, SEO/AEO methodology, and conversion optimization principles.

Score on 4 dimensions (integers 0-100). Be rigorous and honest — average content should score 60-75. Return ONLY valid JSON, no preamble, no markdown fences.

CRITICAL RULES:
- Only flag issues ACTUALLY PRESENT in the submitted text. Never invent violations or hallucinate problems.
- Fixes must reference specific things found in the content — not generic advice.
- Do NOT recommend adding TCO data, ROI calculations, or cost justification.
- Do NOT penalize passive voice.

━━━ DIMENSION 1: TONE & BRAND ━━━
{TONE_SKILL}

Scoring bands:
- 90+: Excellent — concrete, specific, defensible claims. No empty language. Hook is strong.
- 70-89: Good — mostly strong but some vague claims or weak sections.
- 50-69: Fair — noticeable fluff, buzzwords, or unsubstantiated claims ACTUALLY in the text.
- Below 50: Poor — dominated by generic, hypey language with no substance.

━━━ DIMENSION 2: SEO / AEO ━━━
{SEO_AEO_SKILL}

Scoring bands:
- 90+: Excellent — keyword in headline + first paragraph + subheadings. Directly answers implied query. Strong AEO structure.
- 70-89: Good — keywords present but placement or structure could be stronger.
- 50-69: Fair — keywords sparse or missing from key positions. Limited structure.
- Below 50: Poor — no keyword strategy visible. No scannable structure.

━━━ DIMENSION 3: PERSONA FIT ━━━
{PERSONA_SKILL}

Scoring bands:
- 90+: Excellent — speaks directly to role-specific concerns of every selected persona. Right depth for each.
- 70-89: Good — relevant to most but misses specific pain points for some.
- 50-69: Fair — generic content, misses role-specific language for some personas.
- Below 50: Poor — wrong audience or ignores most pain points.

━━━ DIMENSION 4: CRO READINESS ━━━
{CRO_SKILL}

Scoring bands:
- 90+: Excellent — value prop upfront, benefit-first language, specific CTA, social proof present.
- 70-89: Good — CTA and value prop present but not prominent enough.
- 50-69: Fair — CTA buried or generic. Feature-first without business outcomes.
- Below 50: Poor — no CTA, no value proposition, pure feature list.

For each fix, provide an impact score (integer 1-100) for the estimated score improvement if implemented.

Return EXACTLY this structure:
{{"overall_score":<int>,"dimensions":{{"tone":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix referencing actual content>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}},"seo":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}},"persona":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}],"persona_breakdown":[{{"name":"<label>","alignment":<int>,"gap":"<max 10 words>"}}]}},"cro":{{"score":<int>,"summary":"<max 12 words>","fixes":[{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}},{{"text":"<fix>","impact":<int>}}]}}}}}}"""

    user = f"CONTENT TO AUDIT:\n---\n{content}\n---\n\nSELECTED PERSONAS:\n{persona_lines}\n\nKEYWORDS TO SCORE AGAINST: {', '.join(keywords) if keywords else 'none specified'}\n\nReturn JSON only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1800,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def build_keywords_payload(body: dict) -> dict:
    content  = body.get("content", "")
    existing = body.get("existing", [])

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": "You are an SEO strategist for Mitel, a B2B unified communications company. Suggest keywords that improve both traditional search rankings and AI engine visibility (AEO). Return ONLY a JSON array of 6-8 keyword strings — no preamble, no markdown fences.",
        "messages": [{
            "role": "user",
            "content": f"Suggest the most impactful SEO/AEO keywords for this content. Focus on B2B telecom, unified communications, cloud phone systems, and contact center terms that real buyers search for.\n\nContent:\n---\n{content}\n---\n\nAlready targeting: {', '.join(existing) if existing else 'none'}\n\nReturn only NEW keywords not in the list: [\"keyword 1\",\"keyword 2\",...]"
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

    system = f"""You are a senior B2B copywriter at Mitel. Rewrite the content applying the listed improvements, grounded in Mitel's brand and content standards.

MITEL TONE RULES TO APPLY:
{TONE_SKILL}

REWRITING RULES:
1. Only fix what is actually in the text — do not invent problems
2. Replace vague claims with concrete outcomes where the original supports it
3. Front-load the value proposition — first sentence states what the reader gains
4. Integrate target keywords naturally into headline, first paragraph, and subheadings
5. Strengthen or add a specific CTA if weak or missing (e.g. "Book a 30-minute demo" not "Contact us")
6. Preserve the overall structure and approximate length
7. Apply every fix from the list

Return ONLY the rewritten content. No explanation, no preamble."""

    user = f"ORIGINAL:\n---\n{content}\n---\nTARGET PERSONAS: {persona_context}\nKEYWORDS TO INTEGRATE: {kw_context}\n\nFIXES TO APPLY:\n{fixes_text}\n\nReturn only the rewritten content."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2500,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }



def build_crosslinks_payload(body: dict) -> dict:
    content  = body.get("content", "")
    library  = body.get("library", [])

    pages_text = ""
    for group in library:
        pages_text += f"\nGROUP: {group.get('group', 'General')}\n"
        for p in group.get("pages", []):
            pages_text += f"  - Title: {p.get('title', '')}\n    URL: {p.get('url', '')}\n"
            if p.get("description"):
                pages_text += f"    Description: {p.get('description', '')}\n"

    system = """You are a senior SEO strategist for Mitel. Your job is to suggest the most relevant internal links to add to a piece of content, based on a library of existing pages.

Rules:
- Suggest 3-6 links maximum. Quality over quantity.
- Only suggest links that are genuinely relevant to the content — do not force links.
- For each link, specify: the recommended anchor text, the exact sentence or paragraph where it should be inserted, and why it's relevant.
- Anchor text must be natural and descriptive (not "click here" or "learn more").
- Prefer links that help the reader go deeper on a topic already mentioned in the content.
- Return ONLY valid JSON — no preamble, no markdown fences.

Return EXACTLY:
[{"url":"<url>","title":"<page title>","anchor_text":"<recommended anchor text>","placement":"<quote the exact sentence or phrase where the link should be inserted>","reason":"<max 15 words why this link is relevant>"}]"""

    user = f"CONTENT:\n---\n{content}\n---\n\nPAGE LIBRARY:\n{pages_text}\n\nSuggest internal links. Return JSON array only."

    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1200,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("Running on http://0.0.0.0:5000")
    server.serve_forever()
