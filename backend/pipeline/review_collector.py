"""Review collection and sentiment analysis module.

Collects customer reviews from Amazon and brand websites,
then runs NLP sentiment analysis to surface key themes.
"""
import asyncio
import re
import json
from collections import Counter


async def collect_reviews(brand_name: str, urls: list[str] = None, max_reviews: int = 100) -> dict:
    """Collect and analyze customer reviews for a brand.

    Args:
        brand_name: Brand name to search reviews for
        urls: Optional specific product URLs to scrape reviews from
        max_reviews: Maximum number of reviews to collect

    Returns:
        {
            "brand_name": str,
            "summary": {"average_rating": float, "total_reviews": int, "rating_distribution": {1:n,...,5:n}},
            "reviews": [{"rating", "title", "text", "date", "verified", "source"}],
            "sentiment": {"positive_pct": float, "negative_pct": float, "neutral_pct": float},
            "themes": {
                "positive": [{"theme": str, "count": int, "examples": [str]}],
                "negative": [{"theme": str, "count": int, "examples": [str]}],
            },
            "claims_evidence": [{"claim": str, "support_count": int, "contradict_count": int}],
        }
    """
    result = {
        "brand_name": brand_name,
        "summary": {"average_rating": 0, "total_reviews": 0, "rating_distribution": {}},
        "reviews": [],
        "sentiment": {"positive_pct": 0, "negative_pct": 0, "neutral_pct": 0},
        "themes": {"positive": [], "negative": []},
        "claims_evidence": [],
    }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return result

    all_reviews = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            page = await context.new_page()

            if urls:
                for url in urls:
                    if "amazon" in url.lower():
                        reviews = await _scrape_amazon_reviews(page, url, max_reviews // len(urls))
                        all_reviews.extend(reviews)
                    else:
                        reviews = await _scrape_page_reviews(page, url)
                        all_reviews.extend(reviews)
            else:
                # Search Amazon for brand reviews
                reviews = await _search_amazon_reviews(page, brand_name, max_reviews)
                all_reviews.extend(reviews)

            await browser.close()

    except Exception:
        pass

    if not all_reviews:
        return result

    result["reviews"] = all_reviews[:max_reviews]

    # Calculate summary
    ratings = [r["rating"] for r in all_reviews if r.get("rating")]
    if ratings:
        result["summary"]["average_rating"] = round(sum(ratings) / len(ratings), 2)
        result["summary"]["total_reviews"] = len(all_reviews)
        dist = Counter(int(r) for r in ratings)
        result["summary"]["rating_distribution"] = {str(k): dist.get(k, 0) for k in range(1, 6)}

    # AI-powered sentiment analysis (falls back to keyword-based)
    ai_result = _analyze_sentiment_ai(all_reviews)
    if ai_result:
        result["sentiment"] = ai_result.get("sentiment", {})
        result["themes"] = ai_result.get("themes", {"positive": [], "negative": []})
    else:
        result["sentiment"] = _analyze_sentiment(all_reviews)
        result["themes"] = _extract_themes(all_reviews)

    return result


async def _search_amazon_reviews(page, brand_name: str, max_reviews: int) -> list[dict]:
    """Search Amazon for a brand's products and collect reviews."""
    reviews = []
    search_url = f"https://www.amazon.com/s?k={brand_name.replace(' ', '+')}"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Get first few product links
        product_links = await page.evaluate(r"""
            () => {
                const links = [];
                document.querySelectorAll('[data-component-type="s-search-result"] h2 a').forEach(a => {
                    if (a.href) links.push(a.href);
                });
                return links.slice(0, 5);
            }
        """)

        per_product = max(max_reviews // max(len(product_links), 1), 10)

        for link in product_links:
            product_reviews = await _scrape_amazon_reviews(page, link, per_product)
            reviews.extend(product_reviews)
            if len(reviews) >= max_reviews:
                break

    except Exception:
        pass

    return reviews[:max_reviews]


async def _scrape_amazon_reviews(page, product_url: str, max_count: int = 30) -> list[dict]:
    """Scrape reviews from an Amazon product page."""
    reviews = []

    # Navigate to the reviews page
    review_url = product_url.replace("/dp/", "/product-reviews/")
    if "/product-reviews/" not in review_url:
        # Try extracting ASIN
        asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', product_url)
        if asin_match:
            review_url = f"https://www.amazon.com/product-reviews/{asin_match.group(1)}"
        else:
            return reviews

    pages_to_scrape = min(max_count // 10 + 1, 5)

    for page_num in range(1, pages_to_scrape + 1):
        try:
            url = f"{review_url}?pageNumber={page_num}&sortBy=recent"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)

            page_reviews = await page.evaluate(r"""
                () => {
                    const reviews = [];
                    document.querySelectorAll('[data-hook="review"]').forEach(el => {
                        const ratingEl = el.querySelector('[data-hook="review-star-rating"] .a-icon-alt, .review-rating .a-icon-alt');
                        const titleEl = el.querySelector('[data-hook="review-title"] span:not(.a-icon-alt), .review-title');
                        const bodyEl = el.querySelector('[data-hook="review-body"] span, .review-text');
                        const dateEl = el.querySelector('[data-hook="review-date"]');
                        const verifiedEl = el.querySelector('[data-hook="avp-badge"]');

                        if (bodyEl) {
                            const ratingText = ratingEl ? ratingEl.textContent : '';
                            const ratingMatch = ratingText.match(/([\d.]+)/);

                            reviews.push({
                                rating: ratingMatch ? parseFloat(ratingMatch[1]) : 0,
                                title: titleEl ? titleEl.textContent.trim().slice(0, 200) : '',
                                text: bodyEl.textContent.trim().slice(0, 1000),
                                date: dateEl ? dateEl.textContent.trim() : '',
                                verified: !!verifiedEl,
                                source: 'amazon',
                            });
                        }
                    });
                    return reviews;
                }
            """)

            reviews.extend(page_reviews)
            if len(reviews) >= max_count or len(page_reviews) == 0:
                break

        except Exception:
            break

    return reviews[:max_count]


async def _scrape_page_reviews(page, url: str) -> list[dict]:
    """Scrape reviews from a brand website or other review page."""
    reviews = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1)

        # Try common review selectors
        reviews = await page.evaluate(r"""
            () => {
                const reviews = [];
                const selectors = [
                    '.review', '[itemtype*="Review"]', '.testimonial',
                    '.customer-review', '.product-review',
                ];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => {
                        const rating = el.querySelector('[itemprop="ratingValue"], .rating, .stars');
                        const text = el.querySelector('[itemprop="reviewBody"], .review-body, .review-text, p');
                        const title = el.querySelector('[itemprop="name"], .review-title, h3, h4');
                        const date = el.querySelector('[itemprop="datePublished"], .review-date, time');

                        if (text) {
                            let ratingVal = 0;
                            if (rating) {
                                const match = rating.textContent.match(/([\d.]+)/);
                                if (match) ratingVal = parseFloat(match[1]);
                                // Normalize to 5-star scale
                                if (ratingVal > 5) ratingVal = ratingVal / 20;
                            }

                            reviews.push({
                                rating: ratingVal,
                                title: title ? title.textContent.trim().slice(0, 200) : '',
                                text: text.textContent.trim().slice(0, 1000),
                                date: date ? (date.getAttribute('datetime') || date.textContent.trim()) : '',
                                verified: false,
                                source: 'website',
                            });
                        }
                    });
                    if (reviews.length > 0) break;
                }
                return reviews.slice(0, 50);
            }
        """)
    except Exception:
        pass

    return reviews


# ── NLP / Sentiment Analysis ──────────────────────────────────

# Keyword-based sentiment (no external NLP library needed)
POSITIVE_WORDS = {
    "love", "great", "excellent", "amazing", "perfect", "comfortable", "soft",
    "quality", "recommend", "best", "favorite", "worth", "durable", "fits",
    "happy", "pleased", "wonderful", "fantastic", "awesome", "impressed",
    "sturdy", "nice", "good", "beautiful", "lovely", "smooth", "lightweight",
    "breathable", "stretchy", "flattering", "stylish", "professional",
}

NEGATIVE_WORDS = {
    "bad", "poor", "terrible", "worst", "disappointed", "cheap", "broke",
    "ripped", "shrunk", "faded", "uncomfortable", "stiff", "scratchy",
    "thin", "flimsy", "loose", "tight", "short", "long", "wrong",
    "returned", "refund", "waste", "overpriced", "misleading", "smell",
    "pilling", "wrinkled", "see-through", "itchy", "hot", "unflattering",
}

# Theme categories for product reviews
THEME_KEYWORDS = {
    "comfort": ["comfort", "comfortable", "cozy", "soft", "cushion", "ease"],
    "fit": ["fit", "fits", "fitting", "size", "sizing", "tight", "loose", "snug", "baggy"],
    "durability": ["durable", "lasting", "wash", "faded", "shrunk", "ripped", "pilling", "held up"],
    "material/fabric": ["fabric", "material", "cotton", "polyester", "stretchy", "breathable", "moisture"],
    "style/appearance": ["style", "look", "color", "design", "professional", "flattering", "cute"],
    "pockets": ["pocket", "pockets", "storage", "zipper pocket"],
    "value/price": ["price", "value", "worth", "expensive", "cheap", "affordable", "money"],
    "shipping/service": ["shipping", "delivery", "customer service", "return", "exchange"],
}


def _analyze_sentiment(reviews: list[dict]) -> dict:
    """Simple keyword-based sentiment analysis."""
    positive = 0
    negative = 0
    neutral = 0

    for review in reviews:
        text_lower = (review.get("text", "") + " " + review.get("title", "")).lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        pos_count = len(words & POSITIVE_WORDS)
        neg_count = len(words & NEGATIVE_WORDS)

        # Also factor in star rating
        rating = review.get("rating", 0)
        if rating >= 4:
            pos_count += 2
        elif rating <= 2 and rating > 0:
            neg_count += 2

        if pos_count > neg_count:
            positive += 1
        elif neg_count > pos_count:
            negative += 1
        else:
            neutral += 1

    total = len(reviews) or 1
    return {
        "positive_pct": round(positive / total * 100, 1),
        "negative_pct": round(negative / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
    }


def _extract_themes(reviews: list[dict]) -> dict:
    """Extract common positive and negative themes from reviews."""
    positive_themes = {theme: {"count": 0, "examples": []} for theme in THEME_KEYWORDS}
    negative_themes = {theme: {"count": 0, "examples": []} for theme in THEME_KEYWORDS}

    for review in reviews:
        text = review.get("text", "")
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        rating = review.get("rating", 3)
        is_positive = rating >= 4 or (rating == 0 and len(words & POSITIVE_WORDS) > len(words & NEGATIVE_WORDS))

        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                target = positive_themes if is_positive else negative_themes
                target[theme]["count"] += 1
                if len(target[theme]["examples"]) < 3:
                    # Extract the relevant sentence
                    for sentence in re.split(r'[.!?]', text):
                        if any(kw in sentence.lower() for kw in keywords):
                            target[theme]["examples"].append(sentence.strip()[:200])
                            break

    # Sort and filter
    def _to_list(themes_dict):
        items = [
            {"theme": theme, "count": data["count"], "examples": data["examples"]}
            for theme, data in themes_dict.items()
            if data["count"] > 0
        ]
        return sorted(items, key=lambda x: x["count"], reverse=True)

    return {
        "positive": _to_list(positive_themes),
        "negative": _to_list(negative_themes),
    }


# ── AI-Powered Sentiment Analysis ───────────────────────────

def _analyze_sentiment_ai(reviews: list[dict]) -> dict | None:
    """Use Claude Haiku for NLP-level sentiment + theme analysis."""
    try:
        from anthropic import Anthropic
        from config import ANTHROPIC_API_KEY
    except ImportError:
        return None

    if not ANTHROPIC_API_KEY:
        return None

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    review_texts = []
    for r in reviews[:50]:
        rating = r.get("rating", 0)
        text = r.get("text", "")[:300]
        title = r.get("title", "")
        review_texts.append(f"[{rating}★] {title}: {text}")

    if not review_texts:
        return None

    prompt = f"""Analyze these {len(review_texts)} customer product reviews. Return ONLY a JSON object with:

1. "sentiment": {{"positive_pct": number, "negative_pct": number, "neutral_pct": number}} (must sum to 100)
2. "themes": {{
     "positive": [{{"theme": "name", "count": estimated_count, "examples": ["quote1", "quote2"]}}],
     "negative": [{{"theme": "name", "count": estimated_count, "examples": ["quote1", "quote2"]}}]
   }}

Identify 4-8 themes per category. Use short theme names (e.g., "comfort", "fit", "durability").
Examples should be direct quotes from the reviews (1 sentence each).

Reviews:
{chr(10).join(review_texts)}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass

    return None
