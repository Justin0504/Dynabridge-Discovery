"""Auto image collection for PPT slides.

Collects brand-relevant images from three sources:
1. Brand website — product shots, lifestyle imagery, logos
2. E-commerce listings — Amazon product images
3. Unsplash — free stock photos matched by category keywords

Images are saved to output/project_{id}/images/ and returned as a
categorized dict for the PPT generator to use.
"""
import asyncio
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from config import OUTPUT_DIR


async def collect_images(
    project_id: int,
    brand_name: str,
    brand_url: str = "",
    scrape_data: dict = None,
    ecommerce_data: dict = None,
    category_keywords: list[str] = None,
) -> dict:
    """Collect images from all sources.

    Returns:
        {
            "brand": [Path, ...],       # Brand website images
            "product": [Path, ...],     # E-commerce product images
            "lifestyle": [Path, ...],   # Stock/lifestyle images
            "all": [Path, ...],         # All images combined
        }
    """
    img_dir = OUTPUT_DIR / f"project_{project_id}" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        _collect_from_website(img_dir, brand_url, scrape_data),
        _collect_from_ecommerce(img_dir, ecommerce_data),
        _collect_from_website_httpx(img_dir, brand_url, brand_name),
        _collect_via_web_search(img_dir, brand_name, category_keywords),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    brand_imgs = results[0] if not isinstance(results[0], Exception) else []
    product_imgs = results[1] if not isinstance(results[1], Exception) else []
    httpx_imgs = results[2] if not isinstance(results[2], Exception) else []
    search_imgs = results[3] if not isinstance(results[3], Exception) else []

    # Merge httpx brand images with Playwright brand images (deduplicate by path)
    seen = {p.name for p in brand_imgs}
    for p in httpx_imgs:
        if p.name not in seen:
            brand_imgs.append(p)
            seen.add(p.name)

    lifestyle_imgs = search_imgs

    # Sort each list: landscape-first (wider images get priority)
    brand_imgs = _sort_by_aspect(brand_imgs)
    product_imgs = _sort_by_aspect(product_imgs)
    lifestyle_imgs = _sort_by_aspect(lifestyle_imgs)

    total = len(brand_imgs) + len(product_imgs) + len(lifestyle_imgs)
    print(f"[image_collector] Collected {total} images: brand={len(brand_imgs)}, product={len(product_imgs)}, lifestyle={len(lifestyle_imgs)}")

    return {
        "brand": brand_imgs,
        "product": product_imgs,
        "lifestyle": lifestyle_imgs,
        "all": brand_imgs + product_imgs + lifestyle_imgs,
    }


def _sort_by_aspect(paths: list[Path]) -> list[Path]:
    """Sort images by area (largest first), then landscape-preference."""
    def _score(p):
        try:
            from PIL import Image
            with Image.open(str(p)) as img:
                area = img.width * img.height
                landscape_bonus = 1.2 if img.width > img.height else 1.0
                return area * landscape_bonus
        except Exception:
            return 0
    return sorted(paths, key=_score, reverse=True)


def _img_filename(url: str, prefix: str) -> str:
    """Generate a stable filename from URL."""
    h = hashlib.md5(url.encode()).hexdigest()[:10]
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    return f"{prefix}_{h}{ext}"


MIN_WIDTH = 500
MIN_HEIGHT = 300
MAX_ASPECT = 4.0   # reject very wide banners
MIN_ASPECT_DEFAULT = 0.3  # reject very tall/narrow


async def _download_image(
    client: httpx.AsyncClient, url: str, save_path: Path, min_aspect: float = 0.0
) -> Path | None:
    """Download an image if it meets quality criteria.

    Rejects images that are too small (< 500x300), have extreme aspect
    ratios, or are below the byte-size threshold.
    """
    if save_path.exists() and save_path.stat().st_size > 5000:
        try:
            from PIL import Image
            with Image.open(str(save_path)) as img:
                ratio = img.width / img.height
                if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
                    return None
                if ratio < (min_aspect or MIN_ASPECT_DEFAULT) or ratio > MAX_ASPECT:
                    return None
            return save_path
        except Exception:
            pass
        return save_path
    try:
        resp = await client.get(url, follow_redirects=True, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 8000:
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type or save_path.suffix in (".jpg", ".jpeg", ".png", ".webp"):
                from PIL import Image
                import io
                try:
                    with Image.open(io.BytesIO(resp.content)) as img:
                        ratio = img.width / img.height
                        if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
                            return None
                        if ratio < (min_aspect or MIN_ASPECT_DEFAULT) or ratio > MAX_ASPECT:
                            return None
                except Exception:
                    return None

                # Convert WEBP to PNG (python-pptx doesn't support WEBP)
                if save_path.suffix.lower() == ".webp" or "webp" in content_type:
                    try:
                        with Image.open(io.BytesIO(resp.content)) as img:
                            save_path = save_path.with_suffix(".png")
                            img.convert("RGB").save(str(save_path), format="PNG")
                    except Exception:
                        save_path.write_bytes(resp.content)
                else:
                    save_path.write_bytes(resp.content)
                return save_path
    except Exception:
        pass
    return None


# ── Source 1: Brand Website ──────────────────────────────────

async def _collect_from_website(
    img_dir: Path, brand_url: str, scrape_data: dict
) -> list[Path]:
    """Extract and download key images from the brand's website."""
    if not brand_url or not scrape_data:
        return []

    images = []
    image_urls = set()

    # Collect image URLs from scrape data pages
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            page = await context.new_page()

            # Visit up to 3 key pages to extract images
            pages_to_visit = []
            for pg in scrape_data.get("pages", [])[:5]:
                if pg.get("page_type") in ("homepage", "product", "about"):
                    pages_to_visit.append(pg["url"])

            for page_url in pages_to_visit[:3]:
                try:
                    await page.goto(page_url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(1000)

                    # Extract large images (likely product/hero images)
                    urls = await page.evaluate("""
                        () => {
                            const imgs = [];
                            document.querySelectorAll('img').forEach(img => {
                                const src = img.src || img.dataset.src || img.dataset.lazySrc || '';
                                const w = img.naturalWidth || img.width || 0;
                                const h = img.naturalHeight || img.height || 0;
                                // Only keep images that are reasonably large
                                if (src && (w >= 200 || h >= 200 || (!w && !h))) {
                                    // Skip tiny icons, tracking pixels
                                    if (!src.includes('pixel') && !src.includes('track') &&
                                        !src.includes('analytics') && !src.includes('.svg') &&
                                        !src.includes('data:image')) {
                                        imgs.push(src);
                                    }
                                }
                            });
                            // Also check CSS background images on hero sections
                            document.querySelectorAll('.hero, .banner, [class*="hero"], [class*="banner"]').forEach(el => {
                                const bg = getComputedStyle(el).backgroundImage;
                                const match = bg.match(/url\\(['"]?(.*?)['"]?\\)/);
                                if (match) imgs.push(match[1]);
                            });
                            return imgs.slice(0, 15);
                        }
                    """)

                    for u in urls:
                        abs_url = urljoin(page_url, u)
                        if abs_url not in image_urls:
                            image_urls.add(abs_url)
                except Exception:
                    continue

            await browser.close()

    except ImportError:
        return []

    # Download collected images — filter out very narrow/tall images (aspect >= 0.5)
    async with httpx.AsyncClient() as client:
        for url in list(image_urls)[:20]:
            fname = _img_filename(url, "brand")
            path = await _download_image(client, url, img_dir / fname, min_aspect=0.5)
            if path:
                images.append(path)
            if len(images) >= 10:
                break

    return images


# ── Source 2: E-commerce Product Images ──────────────────────

async def _collect_from_ecommerce(
    img_dir: Path, ecommerce_data: dict
) -> list[Path]:
    """Download product images from e-commerce data."""
    if not ecommerce_data:
        return []

    images = []
    image_urls = []

    for product in ecommerce_data.get("products", [])[:10]:
        # Try various image fields
        img_url = (
            product.get("image_url")
            or product.get("image")
            or product.get("thumbnail")
            or ""
        )
        if img_url and img_url.startswith("http"):
            image_urls.append(img_url)

    async with httpx.AsyncClient() as client:
        for url in image_urls[:8]:
            fname = _img_filename(url, "product")
            path = await _download_image(client, url, img_dir / fname)
            if path:
                images.append(path)

    return images


# ── Source 3: httpx-based website image extraction ─────────

async def _collect_from_website_httpx(
    img_dir: Path, brand_url: str, brand_name: str,
) -> list[Path]:
    """Extract images from the brand website using plain httpx + regex.

    Fallback when Playwright is unavailable. Fetches the homepage HTML
    and extracts img src attributes, og:image meta tags, and other
    common image patterns.
    """
    if not brand_url:
        return []

    images = []
    image_urls = set()

    pages_to_try = [brand_url]
    if not brand_url.endswith("/"):
        pages_to_try.append(brand_url + "/")
    for suffix in ("/collections", "/products", "/pages/about"):
        pages_to_try.append(brand_url.rstrip("/") + suffix)

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=12,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    ) as client:
        for page_url in pages_to_try[:4]:
            try:
                resp = await client.get(page_url)
                if resp.status_code != 200:
                    continue
                html = resp.text

                # og:image
                for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html):
                    image_urls.add(urljoin(page_url, m.group(1)))

                # img src (skip tiny icons and data URIs)
                for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)', html):
                    src = m.group(1)
                    if src.startswith("data:") or ".svg" in src:
                        continue
                    if any(skip in src for skip in ("pixel", "track", "analytics", "icon", "logo", "favicon")):
                        continue
                    image_urls.add(urljoin(page_url, src))

                # srcset (pick largest)
                for m in re.finditer(r'srcset=["\']([^"\']+)', html):
                    parts = m.group(1).split(",")
                    best_url = ""
                    best_w = 0
                    for part in parts:
                        tokens = part.strip().split()
                        if len(tokens) >= 2:
                            w_match = re.match(r'(\d+)w', tokens[-1])
                            if w_match and int(w_match.group(1)) > best_w:
                                best_w = int(w_match.group(1))
                                best_url = tokens[0]
                    if best_url and best_w >= 400:
                        image_urls.add(urljoin(page_url, best_url))

            except Exception:
                continue

        # Download (limit to 15 candidates, keep 10 max)
        for url in list(image_urls)[:15]:
            fname = _img_filename(url, "httpx")
            path = await _download_image(client, url, img_dir / fname, min_aspect=0.5)
            if path:
                images.append(path)
            if len(images) >= 10:
                break

    print(f"[image_collector] httpx website: found {len(image_urls)} URLs, downloaded {len(images)}")
    return images


# ── Source 4: Web search → scrape discovered pages ────────

async def _collect_via_web_search(
    img_dir: Path, brand_name: str, category_keywords: list[str] = None,
) -> list[Path]:
    """Use Anthropic web_search to find product/lifestyle pages, then scrape images.

    Two-step process:
      1. Ask Claude to search for the brand and return PAGE URLs
         (Amazon listings, brand product pages, blog features)
      2. Fetch those pages via httpx and extract <img> src attributes
    """
    try:
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return []
    except ImportError:
        return []

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        category_hint = " ".join((category_keywords or [])[:2])
        prompt = f"""Search the web for "{brand_name}" products and find the best pages that contain product images.
{f'Category context: {category_hint}' if category_hint else ''}

I need PAGE URLs (not direct image URLs) where I can find high-quality product photos:
1. {brand_name} Amazon product listing pages
2. {brand_name} official product/collection pages
3. Blog or review sites featuring {brand_name} products

Return a JSON array of page URLs: ["https://...", "https://..."]
Return 5-8 URLs. Return ONLY the JSON array."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        page_urls = []
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                items = json.loads(text[start:end])
                for item in items:
                    url = item if isinstance(item, str) else (item.get("url", "") if isinstance(item, dict) else "")
                    if url.startswith("http"):
                        page_urls.append(url)
            except Exception:
                pass

        # Also extract raw URLs from the text
        for m in re.finditer(r'https?://[^\s"\'<>\]]+', text):
            url = m.group(0).rstrip(".,;)")
            if url.startswith("http") and url not in page_urls:
                page_urls.append(url)

        print(f"[image_collector] web_search: found {len(page_urls)} page URLs to scrape")

        # Step 2: scrape images from discovered pages
        images = []
        image_urls = set()
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        ) as dl_client:
            for page_url in page_urls[:6]:
                try:
                    resp = await dl_client.get(page_url)
                    if resp.status_code != 200:
                        continue
                    html = resp.text

                    # og:image
                    for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html):
                        image_urls.add(urljoin(page_url, m.group(1)))

                    # img src — prefer large/product images
                    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)', html):
                        src = m.group(1)
                        if src.startswith("data:") or ".svg" in src:
                            continue
                        if any(skip in src.lower() for skip in ("pixel", "track", "icon", "logo", "favicon", "sprite")):
                            continue
                        image_urls.add(urljoin(page_url, src))

                    # srcset largest
                    for m in re.finditer(r'srcset=["\']([^"\']+)', html):
                        parts = m.group(1).split(",")
                        best_url, best_w = "", 0
                        for part in parts:
                            tokens = part.strip().split()
                            if len(tokens) >= 2:
                                w_match = re.match(r'(\d+)w', tokens[-1])
                                if w_match and int(w_match.group(1)) > best_w:
                                    best_w = int(w_match.group(1))
                                    best_url = tokens[0]
                        if best_url and best_w >= 400:
                            image_urls.add(urljoin(page_url, best_url))

                except Exception:
                    continue

            # Download discovered images
            for url in list(image_urls)[:20]:
                fname = _img_filename(url, "search")
                path = await _download_image(dl_client, url, img_dir / fname, min_aspect=0.4)
                if path:
                    images.append(path)
                if len(images) >= 10:
                    break

        print(f"[image_collector] web_search: scraped {len(image_urls)} image URLs, downloaded {len(images)}")
        return images

    except Exception as e:
        print(f"[image_collector] web_search failed: {e}")
        return []


def infer_category_keywords(
    brand_name: str,
    category: str = "",
    brand_context: dict = None,
) -> list[str]:
    """Generate semantically-aligned image search keywords from brand/category context.

    Called by the pipeline to produce better stock photo matches.
    """
    keywords = []

    if brand_context:
        cat = brand_context.get("category_landscape", {})
        cat_name = cat.get("category_name", category)
        if cat_name:
            keywords.append(cat_name)

        pos = brand_context.get("brand_positioning", {})
        target = pos.get("target_audience", "")
        if target:
            keywords.append(target.split(",")[0].strip()[:50])

    if category:
        keywords.append(category)

    category_image_map = {
        "scrubs": ["nurse hospital professional", "healthcare worker scrubs", "medical team modern", "doctor confident portrait", "hospital hallway clinical"],
        "medical": ["healthcare professional", "medical team hospital", "nurse caring patient"],
        "baby": ["mother baby nursery", "parent infant care", "baby product lifestyle"],
        "cleaning": ["clean home modern", "steam cleaning floor", "household cleaning product"],
        "water filter": ["clean water kitchen", "water purification home", "family drinking water"],
        "bag": ["eco bag lifestyle", "sustainable fashion bag", "woman carrying bag urban"],
        "lingerie": ["confident woman fashion", "intimate apparel lifestyle", "woman self care"],
        "skincare": ["skincare routine woman", "beauty product lifestyle", "woman glowing skin"],
        "apparel": ["fashion lifestyle model", "casual wear street style", "modern clothing brand"],
        "yoga": ["yoga practice woman", "fitness lifestyle mindful", "athleisure fashion"],
        "shoe": ["sneaker lifestyle urban", "athletic shoe running", "shoe fashion street"],
    }

    cat_lower = (category or "").lower()
    if brand_context:
        cat_lower = brand_context.get("category_landscape", {}).get("category_name", cat_lower).lower()

    for key, searches in category_image_map.items():
        if key in cat_lower:
            keywords.extend(searches[:3])
            break

    if not keywords:
        keywords = [
            f"{brand_name} product lifestyle",
            "business professional team",
            "modern brand lifestyle",
            "consumer product premium",
            "professional workspace modern",
        ]

    return keywords[:5]
