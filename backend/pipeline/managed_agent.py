"""Web research via Claude Messages API with web_search tool.

Uses the standard Messages API with server-side web_search tool to run
autonomous research — Claude searches the web, reads results, and returns
structured findings in a single API call.

Three-session research pipeline (sequential, context-carrying):
  Session 1: Brand + Category Research — brand background, founding story, category landscape
  Session 2: Competitor Deep Research — 6-10 competitor profiles with positioning, pricing, strengths
  Session 3: Consumer + Market Research — purchase behavior, pain points, channel dynamics, sentiment

Also supports:
  - Competitor discovery (find and analyze competitors)
  - Industry trend research (market size, trends, dynamics)
"""
import json
import re
import asyncio
import time
from anthropic import Anthropic, RateLimitError
from config import ANTHROPIC_API_KEY

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if not _client and ANTHROPIC_API_KEY:
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _research_sync(system: str, prompt: str, max_tokens: int = 16000, max_searches: int = 10) -> str:
    """Run a research query with web_search tool. Returns the text response.

    Retries up to 3 times on rate limit errors with exponential backoff.
    """
    client = _get_client()
    if not client:
        print("[managed_agent] No API client available (missing ANTHROPIC_API_KEY)")
        return ""

    for attempt in range(4):
        try:
            print(f"[managed_agent] Calling API (attempt {attempt+1}/4, max_searches={max_searches})...")
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],
                messages=[{"role": "user", "content": prompt}],
            )

            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            result = "".join(text_parts)
            print(f"[managed_agent] Got response: {len(result)} chars")
            return result
        except RateLimitError:
            if attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"[managed_agent] Rate limited, waiting {wait}s (attempt {attempt + 1}/4)")
                time.sleep(wait)
            else:
                raise

    return ""


def _parse_json_response(text: str) -> dict:
    """Extract JSON from response (```json blocks or raw JSON).

    Tries multiple extraction strategies:
    1. ```json code blocks (possibly multiple — pick the largest)
    2. Raw top-level JSON object
    3. Raw top-level JSON array → wrap in {"items": [...]}
    """
    # Strategy 1: All ```json blocks — pick the one that parses to the largest result
    json_blocks = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    best_parsed = None
    best_size = 0
    for block in json_blocks:
        try:
            obj = json.loads(block)
            size = len(block)
            if size > best_size:
                best_parsed = obj
                best_size = size
        except (json.JSONDecodeError, ValueError):
            continue
    if best_parsed is not None:
        if isinstance(best_parsed, list):
            return {"items": best_parsed}
        return best_parsed

    # Strategy 2: Find raw JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Find raw JSON array
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            arr = json.loads(text[start:end])
            if isinstance(arr, list):
                return {"items": arr}
        except (json.JSONDecodeError, ValueError):
            pass

    return {"raw_text": text}


# ── Competitor Discovery ─────────────────────────────────────

async def discover_competitors_managed(
    brand_name: str,
    brand_url: str = "",
    category_context: str = "",
    max_competitors: int = 8,
) -> list[dict]:
    """Discover competitors using web search.

    Returns:
        [{"name": str, "source": "managed_agent", "confidence": float,
          "category_role": str, "reason": str}]
    """
    if not ANTHROPIC_API_KEY:
        return []

    system = (
        "You are a competitive intelligence researcher for a brand consulting firm. "
        "Use web search to find and research competitors for the given brand.\n\n"
        "Search for '[brand] competitors', '[category] brands', marketplace listings, "
        "and comparison articles. Find 6-10 real competitors.\n\n"
        "Return your final answer as a JSON code block:\n"
        "```json\n"
        '{"competitors": [{"name": "Brand", "category_role": "direct|aspirational|adjacent", '
        '"reason": "why they compete", "confidence": 0.9}]}\n'
        "```\n"
        "Be specific about names (official capitalization)."
    )

    prompt = f"Research competitors for the brand '{brand_name}'.\nWebsite: {brand_url}\n"
    if category_context:
        prompt += f"Category context: {category_context}\n"
    prompt += (
        f"\nFind {max_competitors} real competitors. Search for:\n"
        f"- '{brand_name} competitors'\n"
        f"- The product category this brand operates in\n"
        f"- Amazon and e-commerce listings in the same category\n"
        f"- Industry analysis or comparison articles\n\n"
        "Return the JSON result with the competitors array."
    )

    result_text = await asyncio.to_thread(_research_sync, system, prompt, max_tokens=4000, max_searches=5)

    parsed = _parse_json_response(result_text)
    competitors = parsed.get("competitors", [])
    result = []
    for c in competitors[:max_competitors]:
        result.append({
            "name": c.get("name", "Unknown"),
            "source": "managed_agent",
            "confidence": float(c.get("confidence", 0.8)),
            "url": c.get("url"),
            "category_role": c.get("category_role", "direct"),
            "reason": c.get("reason", ""),
        })
    return result


# ── Industry Trend Research ──────────────────────────────────

async def research_industry_trends(
    brand_name: str,
    brand_url: str = "",
    category: str = "",
) -> dict:
    if not ANTHROPIC_API_KEY:
        return {}

    system = (
        "You are a market research analyst. Research industry trends, market dynamics, "
        "and brand reputation. Return findings as a JSON code block:\n"
        "```json\n"
        '{"market_size": "...", "growth_rate": "...", '
        '"key_trends": [{"trend": "name", "description": "detail", "impact": "high/medium/low"}], '
        '"opportunities": ["..."], "threats": ["..."], '
        '"reputation": {"sentiment": "...", "notable_events": ["..."], "social_mentions": "..."}}\n'
        "```"
    )

    prompt = (
        f"Research the industry and market trends for '{brand_name}'.\n"
        f"Website: {brand_url}\n"
    )
    if category:
        prompt += f"Category: {category}\n"
    prompt += (
        f"\nPlease research:\n"
        f"1. The overall market size and growth rate for this product category\n"
        f"2. 4-6 key industry trends shaping this market right now\n"
        f"3. Emerging opportunities that '{brand_name}' could capitalize on\n"
        f"4. Threats or headwinds in the market\n"
        f"5. '{brand_name}' brand reputation — any notable press, social media sentiment\n\n"
        "Return the JSON result."
    )

    result_text = await asyncio.to_thread(_research_sync, system, prompt, max_tokens=4000, max_searches=5)
    return _parse_json_response(result_text)


# ── Session 1: Brand + Category Research ───────────────────

BRAND_RESEARCH_SYSTEM = (
    "You are a brand research analyst at a consulting firm. Your job is to build a comprehensive "
    "profile of a brand through desktop research — as if a client just gave you the brand name "
    "and nothing else.\n\n"
    "Research methodology:\n"
    "1. Search for the brand's website, About page, founding story\n"
    "2. Search for press coverage, media mentions, funding/investment news\n"
    "3. Search for the brand on social media (Instagram followers, TikTok presence, YouTube)\n"
    "4. Search Amazon/e-commerce for the brand's products, pricing, ratings, review count\n"
    "5. Identify the product category and search for category market size, growth, key trends\n"
    "6. Look for the brand's unique claims, messaging, and positioning signals\n\n"
    "Be thorough. Cross-reference findings.\n\n"
    "Return your findings as a JSON code block with this structure:\n"
    "```json\n"
    "{\n"
    '  "brand_profile": {\n'
    '    "founding_story": "What you found about how/when/why the brand was started",\n'
    '    "founders": "Founder names and background if found",\n'
    '    "headquarters": "Location if found",\n'
    '    "year_founded": "Year or approximate",\n'
    '    "key_milestones": ["Milestone 1", "Milestone 2"],\n'
    '    "funding": "Investment/funding info if found",\n'
    '    "mission_statement": "Brand mission or tagline if found"\n'
    "  },\n"
    '  "online_presence": {\n'
    '    "website_summary": "What the website communicates — brand voice, key claims, visual style",\n'
    '    "social_media": {\n'
    '      "instagram": "follower count and content style",\n'
    '      "tiktok": "presence and engagement",\n'
    '      "youtube": "presence and content type",\n'
    '      "facebook": "presence"\n'
    "    },\n"
    '    "amazon_presence": "Number of products, average rating, total review count, BSR if found",\n'
    '    "other_channels": "Walmart, Target, DTC, wholesale — any distribution signals"\n'
    "  },\n"
    '  "brand_positioning": {\n'
    '    "target_audience": "Who the brand appears to target based on messaging and products",\n'
    '    "price_positioning": "Price range and where it sits (value/mid/premium)",\n'
    '    "key_claims": ["Claim 1 from website/listings", "Claim 2"],\n'
    '    "differentiators": ["What the brand says makes it different"],\n'
    '    "brand_voice": "Professional/casual/aspirational/clinical — based on messaging"\n'
    "  },\n"
    '  "category_landscape": {\n'
    '    "category_name": "The product category this brand operates in",\n'
    '    "market_size": "Estimated market size with source",\n'
    '    "growth_rate": "YoY growth rate",\n'
    '    "key_dynamics": ["Dynamic 1 — e.g., DTC growth", "Dynamic 2"],\n'
    '    "consumer_trends": ["Trend 1", "Trend 2", "Trend 3"],\n'
    '    "distribution_shifts": "How the category is sold — channel evolution"\n'
    "  },\n"
    '  "press_coverage": [\n'
    '    {"headline": "Article title", "source": "Publication", "summary": "Key point"}\n'
    "  ],\n"
    '  "reputation_signals": {\n'
    '    "sentiment": "positive/neutral/negative/mixed",\n'
    '    "strengths_mentioned": ["What reviewers/press praise"],\n'
    '    "concerns_mentioned": ["What reviewers/press criticize"],\n'
    '    "notable_events": ["Any PR events, recalls, controversies, awards"]\n'
    "  }\n"
    "}\n"
    "```"
)

async def research_brand_context(
    brand_name: str,
    brand_url: str = "",
    category: str = "",
) -> dict:
    """Session 1: Research the brand itself and its category landscape."""
    if not ANTHROPIC_API_KEY:
        return {}

    prompt = (
        f"Conduct comprehensive desktop research on the brand '{brand_name}'.\n"
        f"Website: {brand_url or 'Unknown — please search for it'}\n"
    )
    if category:
        prompt += f"Suspected category: {category}\n"
    prompt += (
        "\nThis is a brand discovery project. The client provided only the brand name — "
        "no documents, no briefing. You need to build a complete picture through web research.\n\n"
        "Search strategy (do ALL of these):\n"
        f"1. Search '{brand_name}' to find their website and About page\n"
        f"2. Search '{brand_name} brand story' or '{brand_name} founded' for founding/background\n"
        f"3. Search '{brand_name} Amazon' — find products, pricing, star rating, review count, Best Seller Rank\n"
        f"4. Search '{brand_name} Instagram' or '{brand_name} social media' for social presence and follower counts\n"
        f"5. Once you identify the category, search for '[category] market size 2025' and '[category] industry trends'\n"
        f"6. Search '{brand_name} reviews' for consumer sentiment signals\n"
        f"7. Search '{brand_name} sales' or '{brand_name} revenue' for any available sales data or estimates\n"
        f"8. Search '{brand_name}' on Walmart, Target, or other retailers for distribution breadth\n\n"
        "For Amazon products, always note: product title, price, star rating, number of reviews, "
        "and Best Seller Rank (BSR) if visible. These are important sales volume proxies.\n\n"
        "Be thorough. Return the complete JSON."
    )

    result_text = await asyncio.to_thread(
        _research_sync, BRAND_RESEARCH_SYSTEM, prompt, max_tokens=8000, max_searches=10
    )
    return _parse_json_response(result_text)


# ── Session 2: Competitor Deep Research ────────────────────

COMPETITOR_RESEARCH_SYSTEM = (
    "You are a competitive intelligence analyst at a brand consulting firm. "
    "You research competitor brands to build detailed profiles for competitive analysis.\n\n"
    "For each competitor, find:\n"
    "- What they sell and their core product line\n"
    "- Price range (specific price points from their website or Amazon)\n"
    "- Target audience (who their marketing speaks to)\n"
    "- Key differentiator (what makes them stand out)\n"
    "- Channel strategy (DTC, Amazon, wholesale, retail)\n"
    "- Brand voice and positioning\n"
    "- Strengths and vulnerabilities\n\n"
    "Search each competitor individually. Be specific with price points and evidence.\n\n"
    "Return your findings as a JSON code block:\n"
    "```json\n"
    "{\n"
    '  "competitor_profiles": [\n'
    "    {\n"
    '      "name": "Brand Name",\n'
    '      "tagline": "Their tagline or positioning statement",\n'
    '      "category_role": "direct|aspirational|adjacent",\n'
    '      "product_range": "What they sell — key product lines",\n'
    '      "price_range": "$XX - $XX per piece/unit",\n'
    '      "price_positioning": "value|mid-market|premium|luxury",\n'
    '      "target_audience": "Who they target and why",\n'
    '      "key_differentiator": "What makes them stand out in the market",\n'
    '      "channel_strategy": "Where they sell — DTC, Amazon, wholesale, retail",\n'
    '      "brand_voice": "How they communicate",\n'
    '      "social_following": "Notable social media stats if found",\n'
    '      "amazon_stats": "Rating, review count, BSR if found",\n'
    '      "strengths": ["Strength 1", "Strength 2"],\n'
    '      "vulnerabilities": ["Weakness 1", "Weakness 2"],\n'
    '      "key_learning": "What the target brand can learn from this competitor"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "```"
)

async def research_competitor_profiles(
    brand_name: str,
    competitors: list[str],
    category: str = "",
    brand_context: dict = None,
) -> list[dict]:
    """Session 2: Deep-research each competitor's positioning, pricing, and strategy."""
    if not ANTHROPIC_API_KEY or not competitors:
        return []

    category_context = ""
    if brand_context:
        cat_data = brand_context.get("category_landscape", {})
        brand_data = brand_context.get("brand_positioning", {})
        category_context = (
            f"Category: {cat_data.get('category_name', category)}\n"
            f"Market size: {cat_data.get('market_size', 'Unknown')}\n"
            f"Brand's price positioning: {brand_data.get('price_positioning', 'Unknown')}\n"
        )

    comp_list = ", ".join(competitors[:10])
    prompt = (
        f"Research these competitors of '{brand_name}' in detail:\n"
        f"Competitors: {comp_list}\n\n"
        f"{category_context}\n"
        f"For EACH competitor, search for:\n"
        f"1. '[competitor name]' — find their website, product range\n"
        f"2. '[competitor name] Amazon' — find pricing, ratings, reviews\n"
        f"3. '[competitor name] vs' or '[competitor name] review' — find positioning signals\n\n"
        f"Research all {len(competitors[:10])} competitors. Be specific with price points. "
        "Return the complete JSON with all competitor profiles."
    )

    result_text = await asyncio.to_thread(
        _research_sync, COMPETITOR_RESEARCH_SYSTEM, prompt, max_tokens=10000, max_searches=15
    )

    if not result_text:
        print(f"[managed_agent] Session 2 returned empty response")
        return []

    parsed = _parse_json_response(result_text)
    profiles = parsed.get("competitor_profiles", [])
    if not profiles:
        # Try common alternative keys
        for key in ["items", "competitors", "profiles", "results"]:
            val = parsed.get(key, [])
            if isinstance(val, list) and len(val) > 0:
                profiles = val
                break
    if not profiles and "raw_text" not in parsed:
        # Try any list value in the parsed dict
        for key in parsed:
            if isinstance(parsed[key], list) and len(parsed[key]) > 0:
                profiles = parsed[key]
                break
    if not profiles and "raw_text" in parsed:
        print(f"[managed_agent] Session 2 JSON parse failed, first 500 chars: {result_text[:500]}")
    print(f"[managed_agent] Session 2 parsed {len(profiles)} competitor profiles (response: {len(result_text)} chars)")
    return profiles


# ── Session 3: Consumer + Market Research ──────────────────

CONSUMER_RESEARCH_SYSTEM = (
    "You are a consumer research analyst at a brand consulting firm. "
    "You research consumer behavior, purchase patterns, and sentiment for a product category.\n\n"
    "Find real data about how consumers in this category behave:\n"
    "- How often they buy, how much they spend\n"
    "- Where they shop (Amazon, DTC, retail)\n"
    "- What drives purchase decisions (top factors)\n"
    "- Common pain points and unmet needs\n"
    "- Price sensitivity and willingness to pay for premium\n"
    "- Brand awareness and loyalty patterns\n"
    "- What 'premium' means in this category\n"
    "- Social media and information sources they use\n"
    "- Key demographic patterns of category buyers\n\n"
    "Search for industry reports, consumer surveys, market research, Reddit discussions, "
    "review analysis articles, and forum posts. Cite sources when possible.\n\n"
    "Return findings as a JSON code block:\n"
    "```json\n"
    "{\n"
    '  "category_buyers": {\n'
    '    "demographics": {\n'
    '      "gender_split": "e.g., 70% female, 30% male",\n'
    '      "age_distribution": "e.g., 55% Millennial, 25% Gen X, 15% Gen Z",\n'
    '      "income_profile": "Income distribution of category buyers",\n'
    '      "key_roles": "e.g., nurses, medical assistants — or parents, athletes"\n'
    "    },\n"
    '    "purchase_behavior": {\n'
    '      "purchase_frequency": "How often they buy",\n'
    '      "annual_spend": "Average/median annual spend in category",\n'
    '      "primary_channels": ["Channel 1 with %", "Channel 2 with %"],\n'
    '      "purchase_triggers": ["Trigger 1", "Trigger 2"],\n'
    '      "pre_purchase_steps": ["Step 1 with %", "Step 2 with %"]\n'
    "    },\n"
    '    "decision_drivers": {\n'
    '      "top_factors": [{"factor": "name", "importance_pct": 65}],\n'
    '      "premium_definition": ["What premium means 1", "What premium means 2"],\n'
    '      "willingness_to_pay": "% willing to pay more for quality",\n'
    '      "deal_breakers": ["Deal breaker 1", "Deal breaker 2"]\n'
    "    },\n"
    '    "pain_points": [\n'
    '      {"issue": "Pain point name", "frequency": "How common", "detail": "Specifics"}\n'
    "    ],\n"
    '    "brand_dynamics": {\n'
    '      "loyalty_level": "How brand-loyal are category buyers",\n'
    '      "switching_propensity": "How open to trying new brands",\n'
    '      "brand_awareness_order": ["Most known brand", "Second", "Third"],\n'
    '      "what_builds_trust": ["Trust factor 1", "Trust factor 2"]\n'
    "    },\n"
    '    "information_sources": {\n'
    '      "social_media": ["Platform 1 with %", "Platform 2 with %"],\n'
    '      "review_platforms": ["Where they read reviews"],\n'
    '      "influencer_impact": "How much influencers/KOLs affect purchase",\n'
    '      "word_of_mouth": "Role of peer recommendations"\n'
    "    },\n"
    '    "unmet_needs": [\n'
    '      "Specific unmet need 1",\n'
    '      "Specific unmet need 2"\n'
    "    ],\n"
    '    "verbatim_themes": [\n'
    '      {"theme": "Theme name", "sentiment": "positive|negative|mixed", '
    '       "example_quotes": ["Quote 1", "Quote 2"]}\n'
    "    ]\n"
    "  },\n"
    '  "data_sources": ["Source 1", "Source 2"]\n'
    "}\n"
    "```"
)

async def research_consumer_landscape(
    brand_name: str,
    category: str = "",
    brand_context: dict = None,
    competitor_profiles: list[dict] = None,
) -> dict:
    """Session 3: Research consumer behavior, purchase patterns, and sentiment."""
    if not ANTHROPIC_API_KEY:
        return {}

    context_parts = []
    if brand_context:
        cat = brand_context.get("category_landscape", {})
        context_parts.append(f"Category: {cat.get('category_name', category)}")
        context_parts.append(f"Market size: {cat.get('market_size', 'Unknown')}")
        trends = cat.get("consumer_trends", [])
        if trends:
            context_parts.append(f"Known trends: {', '.join(trends[:5])}")

    if competitor_profiles:
        comp_names = [c.get("name", "") for c in competitor_profiles[:8]]
        context_parts.append(f"Key competitors: {', '.join(comp_names)}")
        price_points = [c.get("price_range", "") for c in competitor_profiles[:5] if c.get("price_range")]
        if price_points:
            context_parts.append(f"Competitor pricing: {'; '.join(price_points)}")

    context_block = "\n".join(context_parts)
    cat_name = category
    if brand_context:
        cat_name = brand_context.get("category_landscape", {}).get("category_name", category)

    prompt = (
        f"Research consumer behavior in the '{cat_name or brand_name}' category.\n\n"
        f"Context from prior research:\n{context_block}\n\n"
        "Search strategy (do ALL of these):\n"
        f"1. Search '{cat_name} consumer survey' or '{cat_name} buyer behavior'\n"
        f"2. Search '{cat_name} market research report'\n"
        f"3. Search '{cat_name} Reddit' or '{cat_name} forum' for consumer discussions\n"
        f"4. Search '{cat_name} purchase drivers' or 'why people buy {cat_name}'\n"
        f"5. Search '{cat_name} pain points' or '{cat_name} complaints'\n"
        f"6. Search '{cat_name} brand loyalty' or '{cat_name} brand switching'\n"
        f"7. Search '{cat_name} price sensitivity'\n"
        f"8. Search 'what does premium mean in {cat_name}'\n\n"
        "Find real data with percentages where possible. "
        "Return the complete JSON."
    )

    result_text = await asyncio.to_thread(
        _research_sync, CONSUMER_RESEARCH_SYSTEM, prompt, max_tokens=8000, max_searches=10
    )
    return _parse_json_response(result_text)


# ── Full Desktop Research Pipeline ─────────────────────────

async def run_desktop_research(
    brand_name: str,
    brand_url: str = "",
    category: str = "",
    competitors: list[str] = None,
) -> dict:
    """Run the full 3-session desktop research pipeline."""
    brand_context = await research_brand_context(
        brand_name=brand_name,
        brand_url=brand_url,
        category=category,
    )

    comp_names = competitors or []
    competitor_profiles = []
    if comp_names:
        competitor_profiles = await research_competitor_profiles(
            brand_name=brand_name,
            competitors=comp_names,
            category=category,
            brand_context=brand_context,
        )

    consumer_landscape = await research_consumer_landscape(
        brand_name=brand_name,
        category=category,
        brand_context=brand_context,
        competitor_profiles=competitor_profiles,
    )

    return {
        "brand_context": brand_context,
        "competitor_profiles": competitor_profiles,
        "consumer_landscape": consumer_landscape,
    }
