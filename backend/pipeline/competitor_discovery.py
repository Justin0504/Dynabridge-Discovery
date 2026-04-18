"""Automatic competitor discovery module.

Combines multiple strategies (in priority order):
1. Claude Managed Agent — autonomous web research via web_search tool (preferred)
2. E-commerce scraping — search Amazon for the same category, extract brand names
3. AI inference — ask Claude to identify competitors based on brand/category context

Returns a deduplicated list of competitor names with confidence and source.
"""
import asyncio
import json
import re
from collections import Counter


async def discover_competitors(
    brand_name: str,
    brand_url: str = "",
    scrape_data: dict = None,
    ecommerce_data: dict = None,
    max_competitors: int = 8,
) -> list[dict]:
    """Discover competitors automatically.

    Tries Claude Managed Agent first (web_search-based research).
    Falls back to Amazon scraping + AI inference if Managed Agent is unavailable.

    Returns:
        [{"name": str, "source": "managed_agent"|"amazon"|"ai"|"both", "confidence": float, "url": str|None}]
    """
    # Strategy 1: Try Managed Agent (preferred — uses web_search, no Playwright needed)
    try:
        from pipeline.managed_agent import discover_competitors_managed

        category_context = _infer_category(ecommerce_data)
        managed_results = await discover_competitors_managed(
            brand_name=brand_name,
            brand_url=brand_url,
            category_context=category_context,
            max_competitors=max_competitors,
        )
        if managed_results and len(managed_results) >= 3:
            return managed_results
        else:
            print(f"[competitor_discovery] Managed agent returned {len(managed_results) if managed_results else 0} results, falling through")
    except Exception as e:
        print(f"[competitor_discovery] Managed agent failed: {e}")
        pass  # Fall through to legacy methods

    # Strategy 2: Legacy — Amazon scraping + AI inference in parallel
    amazon_task = _discover_from_amazon(brand_name, ecommerce_data)
    ai_task = _discover_from_ai(brand_name, brand_url, scrape_data)

    amazon_competitors, ai_competitors = await asyncio.gather(
        amazon_task, ai_task, return_exceptions=True
    )

    if isinstance(amazon_competitors, Exception):
        amazon_competitors = []
    if isinstance(ai_competitors, Exception):
        ai_competitors = []

    # Merge and deduplicate
    return _merge_competitors(
        brand_name, amazon_competitors, ai_competitors, max_competitors
    )


async def _discover_from_amazon(
    brand_name: str, ecommerce_data: dict = None
) -> list[dict]:
    """Extract competitor brand names from Amazon search results.

    Searches the same category and extracts brand names from listings
    that are NOT the target brand.
    """
    competitors = []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return competitors

    # Infer search query from brand name + common category keywords
    category_keywords = _infer_category(ecommerce_data)
    search_query = f"{category_keywords}" if category_keywords else brand_name

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            page = await context.new_page()

            # Search Amazon for the category
            search_url = f"https://www.amazon.com/s?k={search_query.replace(' ', '+')}"
            await page.goto(search_url, timeout=15000)
            await page.wait_for_timeout(2000)

            # Extract brand names from search results
            brands = await page.evaluate(r"""
                () => {
                    const results = [];
                    // Try multiple selectors for brand names
                    const items = document.querySelectorAll('[data-component-type="s-search-result"]');
                    items.forEach(item => {
                        // Brand name from "by Brand" text
                        const byLine = item.querySelector('.a-row .a-size-base, .a-row .a-color-secondary');
                        if (byLine) {
                            const text = byLine.textContent.trim();
                            const brandMatch = text.match(/^(?:by\s+)?(.+?)(?:\s+Visit.*)?$/i);
                            if (brandMatch) {
                                results.push(brandMatch[1].trim());
                            }
                        }
                        // Brand from sponsored label area
                        const sponsored = item.querySelector('.puis-label-popover-default .a-size-base');
                        if (sponsored) {
                            results.push(sponsored.textContent.trim());
                        }
                    });

                    // Also check brand filter sidebar
                    const brandFilters = document.querySelectorAll('#brandsRefinements .a-list-item a span');
                    brandFilters.forEach(el => {
                        const text = el.textContent.trim();
                        if (text && !text.match(/^\d/) && text.length > 1 && text.length < 50) {
                            results.push(text);
                        }
                    });

                    return results;
                }
            """)

            await browser.close()

            # Clean and count brand mentions
            brand_name_lower = brand_name.lower()
            junk_patterns = {
                "sponsored", "list:", "typical:", "save ", "climate pledge",
                "bought in past", "featured offers", "no featured",
                "amazon's choice", "best seller", "limited time",
                "deal of the day", "pack of", "count (pack",
                "subscribe", "free delivery", "prime", "coupon",
                "editorial", "results", "price:", "stars",
                "premium brands", "top brands", "top rated",
                "our brands", "related brands", "popular brands",
                "more results", "see more", "shop now",
                "customers also", "frequently bought",
                "from the manufacturer", "highly rated",
                "new arrivals", "new releases",
                "left in stock", "order soon", "only ",
                "add to cart", "add to list", "save for later",
                "in stock", "out of stock", "ships from",
                "fulfilled by", "sold by",
            }
            brand_counts = Counter()
            for b in brands:
                clean = b.strip()
                lower = clean.lower()
                if (
                    clean
                    and len(clean) > 1
                    and len(clean) < 50
                    and clean.lower() != brand_name_lower
                    and not clean.startswith("Visit")
                    and not clean.isdigit()
                    and not any(j in lower for j in junk_patterns)
                    and not lower.endswith("$")
                    and not lower[0].isdigit()
                ):
                    brand_counts[clean] += 1

            # Convert to competitor dicts
            for name, count in brand_counts.most_common(15):
                competitors.append({
                    "name": name,
                    "source": "amazon",
                    "confidence": min(1.0, count / 3),
                    "url": None,
                    "mention_count": count,
                })

    except Exception:
        pass

    return competitors


async def _discover_from_ai(
    brand_name: str, brand_url: str, scrape_data: dict = None
) -> list[dict]:
    """Ask Claude to identify competitors based on brand context."""
    from config import ANTHROPIC_API_KEY

    if not ANTHROPIC_API_KEY:
        return _fallback_ai_competitors(brand_name, scrape_data)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        # Build context from scrape data
        context = ""
        if scrape_data and scrape_data.get("pages"):
            for page in scrape_data["pages"][:3]:
                context += f"\n{page.get('title', '')}: {page.get('text', '')[:500]}\n"

        prompt = f"""Based on this brand, identify 6-8 direct competitors.

Brand: {brand_name}
Website: {brand_url}
{f"Website content: {context}" if context else ""}

Return ONLY a JSON array of competitor objects. Each object must have:
- "name": competitor brand name (official capitalization)
- "category_role": one of "direct" | "aspirational" | "adjacent"
- "reason": one sentence explaining why they're a competitor

Example: [{{"name": "FIGS", "category_role": "aspirational", "reason": "Premium DTC scrubs brand that defined the lifestyle category"}}]

Return ONLY the JSON array, no other text."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(text[start:end])
            return [
                {
                    "name": item["name"],
                    "source": "ai",
                    "confidence": 0.9 if item.get("category_role") == "direct" else 0.7,
                    "url": None,
                    "category_role": item.get("category_role", "direct"),
                    "reason": item.get("reason", ""),
                }
                for item in items
            ]
    except Exception:
        pass

    return _fallback_ai_competitors(brand_name, scrape_data)


def _fallback_ai_competitors(brand_name: str, scrape_data: dict = None) -> list[dict]:
    """Fallback competitor list when AI is unavailable — infer from scrape data."""
    competitors = []

    if scrape_data:
        # Look for competitor mentions in scraped content
        all_text = ""
        for page in scrape_data.get("pages", []):
            all_text += " " + page.get("text", "")

        # Common brand patterns in medical/apparel context
        known_brands = [
            "FIGS", "Cherokee", "Dickies", "Carhartt", "Med Couture",
            "Healing Hands", "Jaanuu", "Barco", "WonderWink", "Dagacci",
            "Grey's Anatomy", "Koi", "HeartSoul", "Landau", "Urbane",
            "Nike", "Adidas", "Under Armour", "Lululemon", "Gymshark",
        ]

        for brand in known_brands:
            if brand.lower() != brand_name.lower() and brand.lower() in all_text.lower():
                competitors.append({
                    "name": brand,
                    "source": "ai",
                    "confidence": 0.5,
                    "url": None,
                })

    return competitors


def _infer_category(ecommerce_data: dict = None) -> str:
    """Infer product category from e-commerce data to improve search."""
    if not ecommerce_data:
        return ""

    # Extract common words from product names
    product_names = [
        p.get("name", "").lower()
        for p in ecommerce_data.get("products", [])
    ]
    all_words = " ".join(product_names)

    # Check for category keywords
    category_map = {
        "scrubs": "medical scrubs",
        "nursing": "nursing scrubs uniforms",
        "medical": "medical uniforms scrubs",
        "jogger": "medical scrub jogger pants",
        "lab coat": "lab coats medical",
        "yoga": "yoga pants leggings",
        "athletic": "athletic wear",
        "sneaker": "sneakers shoes",
        "shirt": "shirts apparel",
    }

    for keyword, search_term in category_map.items():
        if keyword in all_words:
            return search_term

    # Default: use first product name keywords
    if product_names:
        return product_names[0][:50]

    return ""


def _merge_competitors(
    brand_name: str,
    amazon_list: list[dict],
    ai_list: list[dict],
    max_count: int,
) -> list[dict]:
    """Merge and deduplicate competitors from both sources."""
    # Build a name → entry map (case-insensitive)
    merged = {}

    for item in amazon_list:
        key = item["name"].lower().strip()
        if key == brand_name.lower():
            continue
        merged[key] = {
            "name": item["name"],
            "source": "amazon",
            "confidence": item.get("confidence", 0.5),
            "url": item.get("url"),
            "category_role": item.get("category_role", ""),
            "reason": item.get("reason", "Found in Amazon category search results"),
        }

    for item in ai_list:
        key = item["name"].lower().strip()
        if key == brand_name.lower():
            continue
        if key in merged:
            # Exists in both — boost confidence and mark as "both"
            merged[key]["source"] = "both"
            merged[key]["confidence"] = min(1.0, merged[key]["confidence"] + 0.3)
            if item.get("category_role"):
                merged[key]["category_role"] = item["category_role"]
            if item.get("reason"):
                merged[key]["reason"] = item["reason"]
        else:
            merged[key] = {
                "name": item["name"],
                "source": item.get("source", "ai"),
                "confidence": item.get("confidence", 0.7),
                "url": item.get("url"),
                "category_role": item.get("category_role", ""),
                "reason": item.get("reason", ""),
            }

    # Sort by confidence (both > single source), then take top N
    sorted_competitors = sorted(
        merged.values(),
        key=lambda x: (
            {"both": 3, "amazon": 2, "ai": 1}.get(x["source"], 0),
            x["confidence"],
        ),
        reverse=True,
    )

    return sorted_competitors[:max_count]
