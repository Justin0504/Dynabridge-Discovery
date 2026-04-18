"""AI Analysis module using Claude API.

Supports phase-based analysis:
  - brand_reality: Capabilities section only (Phase 1)
  - market_structure: Capabilities + Competition (Phase 1+2)
  - full: Everything (Phase 1+2+3+4)
"""
import json
import time
from anthropic import Anthropic, RateLimitError
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# ── System Prompts ────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior brand strategist at DynaBridge, a US-based brand consulting firm
specializing in helping Chinese enterprises build global brands in Western markets.

You follow DynaBridge's Discovery methodology — a 3-step process:
- Step 1: Capabilities — assess what the brand has built, how it executes, and where gaps exist
- Step 2: Competition — map the competitive landscape, identify market roles, and find white space
- Step 3: Consumer — understand who buys, why, what segments exist, and what unmet needs to target

## Writing Style (match this exactly)

SLIDE TITLES: Must be ALL CAPS, descriptive, and opinionated — they state a finding, not a topic.
  GOOD: "HOW COZYFIT WAS BUILT: EXECUTION FIRST"
  GOOD: "A FOUNDER-LED, AMAZON-NATIVE BRAND"
  GOOD: "QUALITY IS A SYSTEM, NOT A CLAIM"
  GOOD: "BUILT TO WIN WHERE OTHERS UNDER-INVEST"
  GOOD: "STRONG PRODUCT FOUNDATION, UNCLEAR BRAND FOCUS"
  GOOD: "THE MEANING BEHIND THE NAME"
  GOOD: "THE NEXT STEP IS A CLEAR, RESEARCH-LED DECISION"
  BAD: "PRODUCT ANALYSIS" or "PRICING OVERVIEW" (too generic, too safe)

There are TWO content formats — match the right one to each field:

### Format A — CONTENT SLIDES (capabilities, competition, challenges)
BULLETS: 3 bullets per slide. Each bullet is a FULL PARAGRAPH: 2-4 sentences, rich with specific
  evidence from the data (prices, percentages, product names, channel details).
  GOOD: "CozyFit prioritized getting the product right, pricing competitively, and moving fast on Amazon. The founder-led approach focused on product iteration and review velocity rather than brand definition. This built strong initial traction but deferred the harder work of establishing a clear brand identity." (3 sentences)
  BAD: "CozyFit prioritized product quality and pricing." (too thin — no evidence, no depth)

### Format B — COMPETITOR POSITIONING & KEY LEARNINGS
Each statement uses BOLD-LABEL: DETAIL format. The label is a 3-5 word theme, the detail is 1-2 sentences.
  GOOD: "Design creates permission: Minimalist form signals quality and seriousness in a cluttered category."
  GOOD: "Longevity is the promise: Durability and repairability anchor trust more than feature innovation."
  GOOD: "Premium invites challenge: High pricing creates opportunity for brands that can match outcomes with better value."

### Format C — CHART SLIDES & INSIGHT BARS
Short text for chart titles and insight bars. MAX 80 characters, 1 sentence.
  GOOD: "CozyFit has built a product — but not yet a brand." (51 chars)
  GOOD: "They buy scrubs like they practice medicine — with evidence." (60 chars)
  BAD: "The brand has both strengths and weaknesses." (too generic)

SUMMARY PARAGRAPHS: 3-5 sentences, MAX 350 characters total. Write as connected prose, not bullets.
  Start with what the brand does well, then what it needs to fix, then what must happen next.
  End with a forward-looking statement that sets up the next phase of work.

## CRITICAL: Character Limits — STRICTLY ENFORCED (text boxes are fixed-size, overflow is hidden)
- Slide title: max 55 characters
- Insight text (blue bar): max 80 characters
- Content bullet (Format A): 2-4 sentences, max 350 characters per bullet
- Competitor label:detail (Format B): max 180 characters
- Summary paragraph: max 350 characters
COUNT YOUR CHARACTERS. Any text exceeding these limits will be truncated and look broken.

## Analysis Standards
- Evidence-based: cite specific data points, prices, phrases from the provided content
- Strategically honest: surface real weaknesses alongside strengths
- Implication-driven: every observation should point to a "so what"
- IMPORTANT: When data is limited, use your industry expertise to INFER and HYPOTHESIZE.
  Never write "no data available" or "cannot assess". Instead, write what you CAN infer
  from whatever signals exist (brand name, URL, category, competitors), and flag it as
  inference. A strategist always has a point of view — even with incomplete data.

## FEW-SHOT EXAMPLES — match this quality, density, and tone exactly:

EXAMPLE 1 (Capabilities — Format A):
{
  "title": "HOW COZYFIT WAS BUILT: EXECUTION FIRST",
  "bullets": [
    "CozyFit prioritized getting the product right, pricing competitively, and moving fast on Amazon. The founder-led approach focused on product iteration and review velocity rather than brand definition.",
    "Amazon-first launch built strong initial traction through product quality and competitive pricing. Early success was driven by execution discipline, not brand storytelling or emotional positioning.",
    "CozyFit's early success was built on product and channel execution — but execution alone won't sustain growth. Without brand definition, the path from product to brand remains unclear."
  ],
  "insight": "Execution-driven success — but execution alone won't sustain growth.",
  "has_image": true
}

EXAMPLE 2 (Capabilities — Format A):
{
  "title": "A FUNCTIONAL, FEATURE-LED, VALUE-FOCUSED OFFER",
  "bullets": [
    "Across channels, CozyFit emphasizes comfort, fit, features, and affordability over emotional storytelling or identity. Product pages communicate stretch, pockets, and fabric performance — functional language that invites direct comparison.",
    "Product fundamentals are competitive for CozyFit's price tier. Fabrics, construction, and key features match or exceed competitors at similar price points, but the brand lacks a material story or signature innovation to anchor premium perception.",
    "Easy to compare but follows category norms — CozyFit presents as a practical solution rather than a differentiated brand. Without a clear reason to choose CozyFit specifically, customers default to price and availability."
  ],
  "insight": "CozyFit presents as a practical solution, not a differentiated brand.",
  "has_image": true
}

EXAMPLE 3 (Competition — Format B, for POSITIONING field):
{
  "name": "Dupray",
  "banner_description": "Design-led steam specialist positioning Neat as a minimalist premium alternative",
  "positioning": [
    {"label": "Design-led steam specialist", "detail": "Positions Neat as a minimalist, premium alternative to bulky, disposable appliances. Clean aesthetics signal quality in a cluttered category."},
    {"label": "Buy-it-for-life mindset", "detail": "Emphasizes durability, lifetime boiler warranties, and long-term ownership over replacement. Repairability is part of the brand promise."},
    {"label": "Chemical-free authority", "detail": "Frames high-temperature steam as a safer, healthier way to sanitize the home. Health messaging attracts safety-conscious families."}
  ],
  "key_learnings": [
    {"label": "Design creates permission", "detail": "Minimalist form signals quality and seriousness in a cluttered category. Visual restraint earns premium consideration."},
    {"label": "Longevity is the promise", "detail": "Durability and repairability anchor trust more than feature innovation. Lifetime warranties substitute for brand history."},
    {"label": "Premium invites challenge", "detail": "High pricing creates opportunity for brands that can match outcomes with better value. The $300+ tier is vulnerable to credible challengers."}
  ]
}

EXAMPLE 4 (Segment — Consumer narrative):
{
  "name": "Endurance First",
  "tagline": "I need scrubs that perform during long, demanding shifts — durability and comfort are non-negotiable",
  "size_pct": 27,
  "narrative": "Meet the Endurance First Professional: Picture a Nurse Practitioner halfway through a 12-hour shift in a busy hospital ER. Her scrubs have been through patient lifts, medication rounds, and three coffee spills. She needs fabric that moves with her, breathes through pressure, and still looks professional at hour eleven. This segment represents 27% of the market and skews toward experienced healthcare workers in high-acuity settings. They spend the most on scrubs ($180+ annually) and set the performance standard for the entire category. For them, 'premium' means evidence of superior fabric technology and construction that survives industrial laundering. They don't chase trends — they chase proof.",
  "demographics": {
    "primary_role": "Nurse Practitioner / RN in hospital settings",
    "age_skew": "52% Millennial, 29% Gen X",
    "income": "51% upper-middle income ($75K-$149K)",
    "gender_split": "73% female, 27% male"
  },
  "what_premium_means": "Evidence of superior fabric technology (42%) and premium stitching/construction (38%) — proof, not marketing"
}

EXAMPLE 5 (De-prioritized segment reasoning):
{
  "name": "Smart Shopper",
  "size_pct": 31,
  "reason": "Promotion-driven and more price-sensitive with lower warranty emphasis. Competing here risks compressing margins and weakening premium positioning."
}

Notice: content bullets are FULL PARAGRAPHS with evidence. Competitor labels are bold themes.
Segment narratives are vivid character stories. De-prioritization states strategic risk.
Your output must match this caliber. Generic or vague analysis is unacceptable.

You must output ONLY valid JSON. No markdown, no commentary before or after."""


# ── Brand Reality Prompt (Phase 1) ────────────────────────────

BRAND_REALITY_PROMPT = """Analyze this brand's current capabilities and produce a Brand Reality assessment.

## Brand Information
- Brand Name: {brand_name}
- Website URL: {brand_url}
- Language: {language}

## Website Content (scraped)
{scrape_data}

## Uploaded Documents
{document_data}

## E-Commerce Data
{ecommerce_data}

## Customer Reviews
{review_data}

## Analysis Instructions

Assess the brand across these 7 dimensions. For each, write exactly 3 bullets.
Each bullet MUST be a FULL PARAGRAPH: 2-4 sentences, rich with specific evidence
from the data (prices, percentages, product names, channel details, review quotes).
Then write one "insight" sentence — a provocative strategic reframe, not a summary.

Think of each bullet as a mini-argument: [OBSERVATION with evidence] → [IMPLICATION for the brand].

### 1. Execution Summary
How was this brand built? Was it product-first, channel-first, or brand-first?
What execution choices defined its trajectory? Infer the founding logic from
website messaging, product range, pricing, channel presence.

### 2. Product Offering
What does the brand sell and how does it communicate? Analyze: core benefits emphasized,
feature language (stretch, pockets, fabric claims), product range breadth (sizes, colors,
categories), and whether there is emotional storytelling or purely functional communication.

### 3. Product Fundamentals
How strong is the actual product? Assess: materials/fabric quality signals, construction
details, feature set vs. category norms, size range inclusivity, color range, SKU depth.
Compare to competitor product claims if data is available. Are the fundamentals competitive?

### 4. Pricing Position
Where does the brand sit on the price spectrum? Cite actual price points from e-commerce data.
Assess whether pricing matches brand aspirations. Compare to competitor pricing if available.
Does the pricing strategy enable or limit growth?

### 5. Channel Analysis
How does the brand reach customers? Identify the primary growth engine (Amazon, DTC, wholesale).
Assess website quality, e-commerce presence, social media mentions, DTC vs. multi-channel mix.
Which channel drives the business and what does that dependency mean?

### 6. Brand Challenges (identify exactly 3 distinct challenges)
Find 3 real, specific weaknesses. Look for: naming issues, inconsistent messaging across channels,
lack of emotional connection, unclear target audience, visual identity gaps, brand architecture
problems, credibility gaps. Each challenge gets its own slide with 3 bullets and an insight.
Frame challenge titles as clear statements of the problem (e.g., "THE BRAND NAME CREATES A
STRUCTURAL CHALLENGE" not "NAMING ISSUES").

### 7. Capabilities Summary
A flowing paragraph (3-5 sentences) synthesizing: what this brand is good at (execution strengths),
what it needs to fix (brand/perception gaps), and what must happen next. This is NOT bullets —
write it as a connected narrative paragraph.

## Required Output — return this exact JSON structure:

{{
  "brand_name": "{brand_name}",
  "date": "{date}",

  "capabilities": {{
    "execution_summary": {{
      "title": "HOW {brand_name_upper} WAS BUILT: [DESCRIPTIVE PHRASE IN CAPS]",
      "bullets": [
        "2-3 sentence observation about founding/growth strategy with specific evidence from website or documents",
        "2-3 sentence observation about key execution decisions that shaped the brand trajectory",
        "2-3 sentence assessment of what this execution approach achieved and what it missed or deferred"
      ],
      "insight": "Single provocative sentence reframing the execution story — challenge an assumption",
      "has_image": true
    }},
    "product_offer": {{
      "title": "[DESCRIPTIVE PRODUCT POSITIONING HEADLINE IN CAPS]",
      "bullets": [
        "2-3 sentences about product range with specific SKU/category/feature evidence from the data",
        "2-3 sentences about how the brand communicates product benefits — what language does it use on site and listings",
        "2-3 sentences assessing whether the offer is differentiated or follows category norms, and what that means"
      ],
      "insight": "Strategic reframe of the product positioning — what it enables and what it limits",
      "has_image": true
    }},
    "product_fundamentals": {{
      "title": "[PRODUCT FUNDAMENTALS ASSESSMENT HEADLINE IN CAPS]",
      "bullets": [
        "2-3 sentences about material/fabric quality, construction, and how it compares to competitors",
        "2-3 sentences about feature set depth (pockets, stretch, breathability, etc.) relative to category norms",
        "2-3 sentences about size/color range, SKU depth, and whether the product line covers the market adequately"
      ],
      "insight": "Strategic assessment of whether product fundamentals are a strength to build on or a gap to close"
    }},
    "pricing_position": {{
      "title": "[PRICING STRATEGY HEADLINE IN CAPS — state the finding]",
      "bullets": [
        "2-3 sentences citing specific price points or ranges found on website/e-commerce with concrete numbers",
        "2-3 sentences about how pricing messaging positions the brand — value language, promotional tactics, perceived tier",
        "2-3 sentences about what the pricing strategy enables (trial, volume) and what it limits (premium perception, margins)"
      ],
      "insight": "Strategic implication of the pricing position for brand growth"
    }},
    "channel_analysis": {{
      "title": "[CHANNEL STRATEGY HEADLINE IN CAPS — state the finding]",
      "bullets": [
        "2-3 sentences about primary distribution channel with specific evidence (Amazon ranking, review count, etc.)",
        "2-3 sentences about secondary channels — DTC website quality, social media, wholesale/retail presence",
        "2-3 sentences assessing channel strategy strengths and dependencies — what happens if the primary channel changes"
      ],
      "insight": "Strategic implication of channel choices for long-term brand building"
    }},
    "brand_challenges": [
      {{
        "title": "[CHALLENGE 1: CLEAR PROBLEM STATEMENT IN CAPS]",
        "bullets": [
          "2-3 sentences with specific evidence of this challenge from website, listings, or reviews",
          "2-3 sentences about how this challenge manifests in the customer experience or brand perception",
          "2-3 sentences about what's at stake — the strategic risk if this isn't addressed"
        ],
        "insight": "Why this challenge matters strategically — connect to growth or positioning"
      }},
      {{
        "title": "[CHALLENGE 2: CLEAR PROBLEM STATEMENT IN CAPS]",
        "bullets": [
          "2-3 sentences with specific evidence of this challenge",
          "2-3 sentences about how it affects brand perception or customer experience",
          "2-3 sentences about the strategic risk"
        ],
        "insight": "Strategic implication — what this blocks or limits"
      }},
      {{
        "title": "[CHALLENGE 3: CLEAR PROBLEM STATEMENT IN CAPS]",
        "bullets": [
          "2-3 sentences describing this challenge with evidence",
          "2-3 sentences about its impact",
          "2-3 sentences about the path forward — frame as opportunity, not just problem"
        ],
        "insight": "Strategic reframe — how addressing this challenge unlocks the next stage"
      }}
    ],
    "capabilities_summary": "A flowing paragraph of 3-5 sentences. Follow this arc: [1] Name the brand and state its core execution strength with evidence. [2] Acknowledge the gap — what it has NOT yet built (brand, perception, positioning). [3] End with a forward-looking statement. Example: 'CozyFit is an execution-driven brand with competitive products and strong Amazon performance, now facing the need to clarify its naming and brand structure—including the role of Cozy Scrubs—to support long-term growth.'",
    "claims_vs_perception": {{
      "brand_claims": ["Specific claim the brand makes about itself — quote from website if possible", "Another specific claim"],
      "customer_perception": ["What customers actually say — quote or paraphrase from reviews", "Another customer perception"],
      "alignment": "Where claims and perception match — be specific about which claims hold up",
      "gaps": "Where they diverge — this is the most strategically important finding. Be specific and cite evidence."
    }}
  }},

  "next_steps": [
    "Specific recommended action 1 tied directly to a finding above",
    "Specific recommended action 2",
    "Specific recommended action 3",
    "Specific recommended action 4"
  ]
}}

CRITICAL RULES:
- Every bullet MUST be a FULL PARAGRAPH: 2-4 sentences with specific evidence (prices, numbers,
  product names, review quotes). One-sentence bullets are unacceptable. Think of each bullet as
  a mini-argument: [OBSERVATION with evidence] → [IMPLICATION for the brand].
- Titles MUST be ALL CAPS and state a finding/opinion, not a generic topic label.
  GOOD: "A FOUNDER-LED, AMAZON-NATIVE BRAND" / "QUALITY IS A SYSTEM, NOT A CLAIM"
  BAD: "PRODUCT ANALYSIS" / "CHANNEL OVERVIEW"
- The insight field MUST be a single sentence a CMO would underline — provocative, not safe.
  GOOD: "The best way in is through the door nobody else is walking through."
  BAD: "The brand needs to improve its positioning."
- brand_challenges MUST contain exactly 3 challenges. Each challenge title should state the
  PROBLEM clearly (e.g., "THE BRAND NAME CREATES A STRUCTURAL CHALLENGE", not "NAMING ISSUES").
- capabilities_summary MUST be a flowing paragraph (not bullets) following the arc:
  strength → gap → forward-looking next step.
- If data is missing for a section, say what's missing and infer from available data.
- Do NOT invent data points — but DO make strategic inferences from real data.
- Output ONLY the JSON object, nothing else"""


# ── Market Structure Prompt (Phase 2) ─────────────────────────

MARKET_STRUCTURE_PROMPT = """Analyze the competitive landscape for {brand_name} and produce a Market Structure assessment.

## Brand Information
- Brand Name: {brand_name}
- Website URL: {brand_url}
- Industry/Category context from Phase 1 capabilities analysis

## Competitor List
{competitors}

## Competitor Website Data (scraped)
{competitor_scrape_data}

## Competitor E-Commerce Data
{competitor_ecommerce_data}

## Competitor Review Data
{competitor_review_data}

## Phase 1 Context (Brand Reality findings)
{phase1_context}

## Analysis Instructions

### Market Overview
Identify ALL notable competitors in the category (aim for 8-12 brands). Assess the overall
market structure: is it mature, fragmented, consolidating? What dynamics shape competition?
Where does {brand_name} currently fit?

### Focused Competitor Review
Select 4-6 competitors for deep analysis — the ones most relevant to {brand_name}'s positioning.
Include a mix: direct competitors (similar price/product), aspirational competitors (where the
brand wants to be), and adjacent competitors (different approach to same customer).

### Individual Competitor Analysis (CRITICAL — this is the most content-rich section)
Each competitor gets TWO conceptual slides in the report: one for POSITIONING, one for KEY LEARNINGS.
Write each entry with the depth and specificity of a dedicated competitor brief.

For each focused competitor, provide:
- POSITIONING: 3 bold-label:detail statements. Each label is a 3-5 word STRATEGIC THEME
  (not generic labels like "Target Audience"). The detail is 1-2 sentences of specific evidence.
  GOOD labels: "Design-led steam specialist", "Buy-it-for-life mindset", "Chemical-free authority"
  GOOD labels: "Caregiver-centered brand", "Empathy-led messaging", "Accessible comfort"
  BAD labels: "Target Audience", "Price Point", "Key Differentiator" (too generic, too template-like)
- KEY LEARNINGS: 3 bold-label:detail insights. Each label states a strategic principle that
  {brand_name} can learn from. The detail explains WHY this matters with evidence.
  GOOD labels: "Design creates permission", "Longevity is the promise", "Premium invites challenge"
  GOOD labels: "Emotional permission matters", "Purpose travels across categories"
  BAD labels: "What works", "Vulnerability", "Learning" (too generic)
- banner_description: A 1-line strategic framing of this competitor's role in the market.
  GOOD: "Design-led steam specialist positioning Neat as a minimalist premium alternative"
  GOOD: "Prosumer steam specialist bridging mass-market and premium European players"

### Competitive Landscape Summary
Group brands by STRATEGIC ROLE (e.g., "Premium Lifestyle", "Heritage Authority", "Value Play",
"Fashion-Forward"). For each role, name the brands and explain what defines that competitive
territory. Then identify the white space — the specific positioning territory that NO brand
currently owns. Be concrete: "No brand currently combines [X capability] with [Y promise]."

### Competition Summary
Write a flowing paragraph of 3-5 sentences. Name specific brands and their winning strategies.
State what the competitive landscape rewards and punishes. End with a forward-looking statement
about what claiming white space requires for {brand_name}.
GOOD: "The steam cleaner market is divided across brands that win on trust (Bissell), design
(Dupray), power (McCulloch), longevity (Vapamore), or price, with each owning a single
decision trigger rather than delivering a complete, modern brand experience."

## Required Output — return this exact JSON structure:

{{
  "competition": {{
    "market_overview": {{
      "title": "KEY PLAYERS SHAPING THE [CATEGORY] CATEGORY",
      "competitor_names": ["Brand A", "Brand B", "Brand C", "Brand D", "Brand E", "Brand F", "Brand G", "Brand H"],
      "bullets": [
        "2-3 sentences describing the overall market structure and competitive dynamics",
        "2-3 sentences about key trends shaping competition — what's changing and why",
        "2-3 sentences about where {brand_name} currently fits and what that position means"
      ],
      "insight": "Single provocative sentence capturing the competitive reality {brand_name} faces"
    }},
    "focused_competitors": ["Brand A", "Brand B", "Brand C", "Brand D", "Brand E", "Brand F"],
    "competitor_analyses": [
      {{
        "name": "Competitor Name",
        "banner_description": "Strategic 1-line framing of their market role (e.g., 'Design-led steam specialist positioning as minimalist premium alternative')",
        "positioning": [
          {{"label": "3-5 word strategic theme (e.g., 'Design-led steam specialist')", "detail": "1-2 sentences with specific evidence of how they position. Cite product claims, price points, visual identity, channel strategy."}},
          {{"label": "Another strategic theme (e.g., 'Buy-it-for-life mindset')", "detail": "1-2 sentences. Be specific about HOW this positioning manifests — in messaging, product design, pricing, or customer experience."}},
          {{"label": "Third strategic theme (e.g., 'Chemical-free authority')", "detail": "1-2 sentences. What emotional or functional territory does this positioning claim?"}}
        ],
        "key_learnings": [
          {{"label": "Strategic principle (e.g., 'Design creates permission')", "detail": "1-2 sentences explaining why this matters. Connect to {brand_name}'s situation — what can be borrowed, challenged, or avoided."}},
          {{"label": "Another principle (e.g., 'Longevity is the promise')", "detail": "1-2 sentences. Identify what makes this competitor vulnerable or what territory they leave open."}},
          {{"label": "Third principle (e.g., 'Premium invites challenge')", "detail": "1-2 sentences. State the concrete takeaway for {brand_name} — what to do differently."}}
        ]
      }}
    ],
    "landscape_summary": {{
      "market_roles": [
        {{"role": "Role Name (e.g., Premium Lifestyle)", "brands": ["Brand1", "Brand2"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand3"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand4", "Brand5"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand6"], "description": "What defines this role"}}
      ],
      "white_space": "Specific positioning territory that no brand currently owns — be concrete about what this looks like",
      "category_norms": [
        "A norm/assumption most brands in this category share",
        "Another shared assumption",
        "A third shared assumption that could be challenged"
      ]
    }},
    "competition_summary": "A flowing paragraph of 3-5 sentences. Synthesize: what the competitive landscape looks like, which brands succeed by owning a clear role, and where the white space opportunity lies for {brand_name}. End with a forward-looking statement about what claiming that white space requires."
  }}
}}

CRITICAL RULES:
- competitor_analyses MUST contain 6-10 entries — analyze real, specific competitors (real cases average 8)
- Each competitor's positioning and key_learnings MUST have exactly 3 entries each
- market_roles MUST contain exactly 4 roles that cover the market structure
- Titles must be ALL CAPS and descriptive (e.g., "KEY PLAYERS SHAPING THE [CATEGORY] CATEGORY")
- competition_summary must be a paragraph, not bullets
- If competitor data is limited, infer from available evidence and state what you're inferring
- Output ONLY the JSON object, nothing else"""


# ── Full Analysis Prompt (all phases) ─────────────────────────

FULL_ANALYSIS_PROMPT = """Produce a complete Brand Discovery report for {brand_name}.

## Brand Information
- Brand Name: {brand_name}
- Website URL: {brand_url}
- Language: {language}

## Website Content (scraped)
{scrape_data}

## Uploaded Documents
{document_data}

## E-Commerce Data
{ecommerce_data}

## Customer Reviews
{review_data}

## Competitors
{competitors}

## Competitor Data
{competitor_data}

## Analysis Instructions

This is a FULL discovery report covering all 3 steps. Follow the structure precisely.

### Step 1: Capabilities
Analyze the brand across 7 dimensions: execution summary, product offer, product fundamentals,
pricing position, channel analysis, 3 brand challenges, and a capabilities summary paragraph.
Each slide needs 3 bullets (2-3 sentences each) + 1 insight sentence.

### Step 2: Competition
Map the competitive landscape: market overview (8-12 brands), focused review (4-6 deep dives),
landscape summary (4 market roles), and competition summary paragraph.

### Step 3: Consumer
This is the MOST important section. Based on available review data, e-commerce data, and any
uploaded research documents, build a comprehensive consumer analysis:

1. Research approach description
2. Shopping habits and purchase drivers (generate chart data from reviews/e-commerce signals)
3. Brand perception analysis
4. Consumer segmentation: identify 4-5 distinct consumer segments based on the data.
   Each segment MUST include:
   - An evocative 2-word name that captures the segment's core identity
     GOOD: "Endurance First", "Polished Pro", "Tender Caregiver", "Vivid Collector"
     BAD: "Segment 1", "Price Sensitive", "Quality Buyer" (too generic)
   - A first-person tagline that sounds like something the person would actually say
     GOOD: "I need scrubs that perform during long, demanding shifts"
     BAD: "This segment values quality and comfort" (third-person, generic)
   - A "Meet the [Segment]" narrative paragraph (5-7 sentences). START with a vivid character
     scene: "Meet the [Name]: Picture a [specific role] halfway through a [specific situation]..."
     Then cover: who they are demographically, how they shop for this category, what matters most,
     what frustrates them, and what would win their loyalty. Use specific details and percentages.
     Write as storytelling, not a data dump.
   - what_premium_means: What this segment specifically considers premium. Not generic — cite
     the exact attributes (e.g., "evidence of superior fabric technology (42%) and premium
     stitching/construction (38%)")
   - lifestyle_signals: 4 lifestyle data points (social media, music genre, car brand, key stat)
     that paint a vivid picture of who this person is beyond the category
   - mini_tables: structured data for purchase_drivers, pain_points, pre_purchase, social_media
     — each with item and pct fields for chart rendering
5. Target audience recommendation:
   - Which segment should {brand_name} prioritize and WHY (4 specific strategic reasons)
   - What targeting this segment ENABLES (3 strategic benefits)
   - What this choice does NOT yet decide (3 open questions for future work)
   - Per-segment de-prioritization reasoning: for EACH non-primary segment, state the specific
     strategic risk of targeting them (e.g., "Promotion-driven, competing here risks compressing margins")
6. Competitive fares: How {brand_name} stacks up against competition for the target segment
7. Consumer summary paragraph tying segment choice to capabilities and competitive position

## Required Output — return this exact JSON:

{{
  "brand_name": "{brand_name}",
  "date": "{date}",

  "capabilities": {{
    "execution_summary": {{
      "title": "HOW {brand_name_upper} WAS BUILT: [DESCRIPTIVE PHRASE]",
      "bullets": ["2-3 sentence point with evidence", "2-3 sentence point", "2-3 sentence point"],
      "insight": "Provocative single sentence reframe",
      "has_image": true
    }},
    "product_offer": {{
      "title": "[DESCRIPTIVE PRODUCT HEADLINE IN CAPS]",
      "bullets": ["2-3 sentence point with evidence", "2-3 sentence point", "2-3 sentence point"],
      "insight": "Strategic reframe",
      "has_image": true
    }},
    "product_fundamentals": {{
      "title": "[PRODUCT FUNDAMENTALS HEADLINE IN CAPS]",
      "bullets": ["2-3 sentence point", "2-3 sentence point", "2-3 sentence point"],
      "insight": "Strategic assessment"
    }},
    "pricing_position": {{
      "title": "[PRICING HEADLINE IN CAPS]",
      "bullets": ["2-3 sentence point with prices", "2-3 sentence point", "2-3 sentence point"],
      "insight": "Strategic implication"
    }},
    "channel_analysis": {{
      "title": "[CHANNEL HEADLINE IN CAPS]",
      "bullets": ["2-3 sentence point", "2-3 sentence point", "2-3 sentence point"],
      "insight": "Strategic implication"
    }},
    "brand_challenges": [
      {{
        "title": "[CHALLENGE 1 STATEMENT IN CAPS]",
        "bullets": ["2-3 sentence point", "2-3 sentence point", "2-3 sentence point"],
        "insight": "Strategic implication"
      }},
      {{
        "title": "[CHALLENGE 2 STATEMENT IN CAPS]",
        "bullets": ["2-3 sentence point", "2-3 sentence point", "2-3 sentence point"],
        "insight": "Strategic implication"
      }},
      {{
        "title": "[CHALLENGE 3 STATEMENT IN CAPS]",
        "bullets": ["2-3 sentence point", "2-3 sentence point", "2-3 sentence point"],
        "insight": "Strategic reframe — path forward"
      }}
    ],
    "capabilities_summary": "Flowing paragraph 3-5 sentences: execution strengths + brand gaps + what needs to happen next",
    "claims_vs_perception": {{
      "brand_claims": ["Specific claim from website/listings"],
      "customer_perception": ["What customers say in reviews"],
      "alignment": "Where they match",
      "gaps": "Where they diverge — cite evidence"
    }}
  }},

  "competition": {{
    "market_overview": {{
      "title": "A [ADJ], [ADJ] [CATEGORY] MARKET",
      "competitor_names": ["Brand1", "Brand2", "Brand3", "Brand4", "Brand5", "Brand6"],
      "bullets": ["2-3 sentence market structure", "2-3 sentence trends", "2-3 sentence brand position"],
      "insight": "Competitive reality sentence"
    }},
    "focused_competitors": ["Brand A", "Brand B", "Brand C", "Brand D"],
    "competitor_analyses": [
      {{
        "name": "Competitor Name",
        "banner_description": "Strategic 1-line role framing (e.g., 'Design-led steam specialist positioning as minimalist premium alternative')",
        "positioning": [
          {{"label": "3-5 word strategic theme", "detail": "1-2 sentences with specific evidence — cite product claims, prices, visual identity"}},
          {{"label": "Another strategic theme", "detail": "1-2 sentences. Be specific about HOW this positioning manifests"}},
          {{"label": "Third strategic theme", "detail": "1-2 sentences. What emotional or functional territory does this claim?"}}
        ],
        "key_learnings": [
          {{"label": "Strategic principle (e.g., 'Design creates permission')", "detail": "1-2 sentences. What can {brand_name} learn, borrow, or challenge?"}},
          {{"label": "Another principle (e.g., 'Longevity is the promise')", "detail": "1-2 sentences. Where is this competitor vulnerable?"}},
          {{"label": "Third principle (e.g., 'Premium invites challenge')", "detail": "1-2 sentences. Concrete takeaway for {brand_name}."}}
        ]
      }}
    ],
    "landscape_summary": {{
      "market_roles": [
        {{"role": "Role Name", "brands": ["Brand1", "Brand2"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand3"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand4"], "description": "What defines this role"}},
        {{"role": "Role Name", "brands": ["Brand5", "Brand6"], "description": "What defines this role"}}
      ],
      "white_space": "Specific unclaimed positioning territory",
      "category_norms": ["Shared norm 1", "Shared norm 2", "Shared norm 3"]
    }},
    "competition_summary": "Flowing paragraph 3-5 sentences synthesizing competitive landscape and opportunity"
  }},

  "consumer": {{
    "overview": "2-3 sentence consumer landscape summary — who buys in this category and what matters to them",
    "research_approach": [
      {{"label": "Format", "detail": "e.g. Review analysis + e-commerce data mining + secondary research"}},
      {{"label": "Data Sources", "detail": "e.g. Amazon reviews (N=XXX), brand website, competitor listings"}},
      {{"label": "Participants", "detail": "Description of the consumer base analyzed"}},
      {{"label": "Analysis", "detail": "Method used — sentiment analysis, theme extraction, segmentation"}},
      {{"label": "Timing", "detail": "{date}"}}
    ],
    "charts": [
      // SECTION: Demographics (4-5 charts) — divider auto-inserted
      {{
        "chart_type": "vbar",
        "title": "RESPONDENT GENERATION PROFILE",
        "subtitle": "Generation distribution of survey respondents",
        "categories": ["Gen Z (18-27)", "Millennial (28-43)", "Gen X (44-59)", "Boomer (60+)"],
        "values": [15, 45, 30, 10]
      }},
      {{
        "chart_type": "dual",
        "title": "GENDER AND ETHNICITY BREAKDOWN",
        "subtitle": "Respondent demographic composition",
        "left_type": "donut", "left_title": "Gender",
        "left_categories": ["Female", "Male", "Non-binary"],
        "left_values": [70, 28, 2],
        "right_type": "hbar", "right_title": "Race / Ethnicity",
        "right_categories": ["White/Caucasian", "Black/African American", "Hispanic/Latino", "Asian/Pacific Islander"],
        "right_values": [52, 22, 15, 11]
      }},
      {{
        "chart_type": "hbar",
        "title": "HOUSEHOLD INCOME DISTRIBUTION",
        "subtitle": "Annual household income brackets",
        "categories": ["Under $25K", "$25K-$49K", "$50K-$74K", "$75K-$99K", "$100K-$149K", "$150K+"],
        "values": [8, 18, 24, 22, 18, 10]
      }},
      {{
        "chart_type": "hbar",
        "title": "SOCIAL MEDIA PLATFORMS USED",
        "subtitle": "Which social media platforms respondents frequently use",
        "categories": ["YouTube", "Instagram", "Facebook", "TikTok", "Pinterest", "X/Twitter", "Reddit"],
        "values": [78, 65, 62, 48, 35, 28, 22]
      }},
      // SECTION: Shopping Habits (6-8 charts) — divider auto-inserted
      {{
        "chart_type": "dual",
        "title": "PURCHASE FREQUENCY AND ANNUAL SPEND",
        "subtitle": "How often and how much respondents spend on [category]",
        "left_type": "donut", "left_title": "Purchase frequency (past 12 months)",
        "left_categories": ["Monthly+", "Every 2-3 months", "2-3x/year", "Once/year", "When needed"],
        "left_values": [18, 42, 27, 7, 6],
        "right_type": "hbar", "right_title": "Annual spend on [category]",
        "right_categories": ["Under $50", "$50-$99", "$100-$199", "$200-$499", "$500+"],
        "right_values": [12, 22, 30, 25, 11]
      }},
      {{
        "chart_type": "hbar",
        "title": "WHERE CONSUMERS PURCHASE [CATEGORY]",
        "subtitle": "Primary purchase channels (select all that apply)",
        "categories": ["Amazon", "Brand website (DTC)", "Walmart", "Specialty stores", "Target", "Other"],
        "values": [59, 41, 38, 35, 26, 15]
      }},
      {{
        "chart_type": "hbar",
        "title": "WHEN AND WHY CONSUMERS USE [CATEGORY]",
        "subtitle": "Usage occasions (select all that apply)",
        "categories": ["Occasion1", "Occasion2", "Occasion3", "Occasion4", "Occasion5"],
        "values": [72, 55, 42, 35, 28]
      }},
      {{
        "chart_type": "hbar",
        "title": "PRE-PURCHASE ACTIVITIES",
        "subtitle": "Steps taken before buying [category]",
        "categories": ["Read online reviews", "Compare prices", "Visit brand website", "Ask friends/family", "Watch video reviews", "Try in store", "Check social media"],
        "values": [78, 65, 48, 42, 38, 32, 28]
      }},
      // SECTION: Purchase Drivers (3-4 charts)
      {{
        "chart_type": "hbar",
        "title": "TOP PURCHASE DRIVERS",
        "subtitle": "Most important factors when buying [category] (select top 3)",
        "categories": ["Driver1", "Driver2", "Driver3", "Driver4", "Driver5", "Driver6", "Driver7", "Driver8"],
        "values": [65, 52, 48, 42, 38, 35, 28, 22]
      }},
      {{
        "chart_type": "hbar",
        "title": "WHAT DOES 'PREMIUM' MEAN IN [CATEGORY]?",
        "subtitle": "Consumer definition of premium (select all that apply)",
        "categories": ["Premium1", "Premium2", "Premium3", "Premium4", "Premium5", "Premium6"],
        "values": [55, 48, 42, 35, 30, 25]
      }},
      {{
        "chart_type": "dual",
        "title": "WILLINGNESS TO PAY FOR QUALITY",
        "subtitle": "Price sensitivity and premium willingness",
        "left_type": "donut", "left_title": "Willing to pay more for quality",
        "left_categories": ["Strongly agree", "Somewhat agree", "Neutral", "Disagree"],
        "left_values": [35, 40, 15, 10],
        "right_type": "hbar", "right_title": "Expected price range for quality [category]",
        "right_categories": ["Under $25", "$25-$49", "$50-$99", "$100-$199", "$200+"],
        "right_values": [8, 25, 38, 22, 7]
      }},
      {{
        "chart_type": "wordcloud",
        "title": "WHAT CONSUMERS SAY ABOUT [CATEGORY]",
        "subtitle": "Word frequency from open-ended responses and reviews",
        "words": {{"comfortable": 85, "durable": 72, "affordable": 60, "quality": 55, "stretchy": 48, "soft": 45, "professional": 42, "breathable": 38, "pockets": 35, "stylish": 32, "lightweight": 30, "flattering": 28, "modern": 25, "sustainable": 22, "innovative": 20}}
      }},
      // SECTION: Brand Evaluation (4-5 charts) — divider auto-inserted
      {{
        "chart_type": "grouped_bar",
        "title": "BRAND METRICS — AWARENESS TO ADVOCACY",
        "subtitle": "Brand performance across key metrics",
        "horizontal": true,
        "categories": ["Brand1", "Brand2", "Brand3", "Brand4", "Brand5"],
        "groups": [
          {{"name": "Awareness", "values": [85, 72, 60, 45, 38]}},
          {{"name": "Purchase", "values": [55, 40, 30, 20, 15]}},
          {{"name": "Satisfaction", "values": [80, 65, 55, 50, 42]}},
          {{"name": "Recommend", "values": [60, 45, 35, 30, 22]}}
        ]
      }},
      {{
        "chart_type": "donut",
        "title": "FAVORITE BRAND REGARDLESS OF PRICE",
        "subtitle": "Which brand is your favorite?",
        "center_text": "N=200",
        "categories": ["Brand1", "Brand2", "Brand3", "Brand4", "Brand5", "No favorite"],
        "values": [28, 22, 18, 12, 8, 12]
      }},
      {{
        "chart_type": "hbar",
        "title": "LIKELIHOOD TO TRY A NEW BRAND",
        "subtitle": "How open are consumers to switching?",
        "categories": ["Very likely", "Somewhat likely", "Neutral", "Somewhat unlikely", "Very unlikely"],
        "values": [22, 35, 25, 12, 6]
      }},
      {{
        "chart_type": "matrix",
        "title": "BRAND ASSOCIATION MATRIX",
        "subtitle": "Which brand best fits each description?",
        "row_labels": ["High quality", "Good value", "Innovative", "Trustworthy", "Stylish", "Premium"],
        "col_labels": ["Brand1", "Brand2", "Brand3", "Brand4"],
        "values": [
          [45, 30, 20, 15],
          [25, 40, 35, 50],
          [30, 25, 15, 10],
          [40, 35, 25, 20],
          [20, 15, 35, 10],
          [35, 20, 15, 10]
        ]
      }}
    ],
    "verbatim_quotes": [
      {{"theme": "Theme name (e.g., Comfort)", "quotes": ["Direct quote from review 1", "Direct quote from review 2", "Direct quote from review 3"]}},
      {{"theme": "Another theme", "quotes": ["Quote 1", "Quote 2", "Quote 3"]}}
    ],
    "segments": [
      {{
        "name": "Evocative 2-word name (e.g., Endurance First, Smart Shopper, Tender Caregiver, Polished Pro, Vivid Collector, Mindful Sustainer)",
        "tagline": "I want/need [what this segment prioritizes] — one sentence, first person, sounds like something they'd actually say",
        "size_pct": 27,
        "narrative": "Meet the [Segment Name]: Picture a [specific role/person] [in a specific situation that reveals their relationship to the category]. [2-3 sentences about who they are: demographics, income, lifestyle]. [1-2 sentences about how they shop: channels, frequency, research behavior]. [1-2 sentences about what matters most and what frustrates them]. [1 sentence about what premium/quality means to them specifically]. For example: 'Meet the Endurance First Professional: Picture a Nurse Practitioner halfway through a 12-hour shift in a busy hospital ER. Her scrubs have been through patient lifts, medication rounds, and three coffee spills. She needs fabric that moves with her, breathes through pressure, and still looks professional at hour eleven.'",
        "demographics": {{
          "primary_role": "Most common role/profession",
          "age_skew": "e.g., 58% Millennial, 23% Gen X",
          "income": "e.g., 51% upper-middle income",
          "gender_split": "e.g., 67% female, 33% male"
        }},
        "shopping_behavior": {{
          "annual_spend": "$XXX median",
          "primary_channel": "Where they buy most",
          "purchase_frequency": "How often they buy",
          "brand_loyalty": "High/Medium/Low — with reasoning"
        }},
        "top_needs": ["Need 1 with percentage if available", "Need 2", "Need 3"],
        "pain_points": ["Pain point 1 with percentage if available", "Pain point 2", "Pain point 3"],
        "what_premium_means": "What this segment considers premium — e.g., fabric tech, design, durability",
        "lifestyle_signals": [
          {{"category": "Social Media", "detail": "e.g., 78% use YouTube more than any other platform"}},
          {{"category": "Music", "detail": "e.g., 37% prefer R&B / Soul music"}},
          {{"category": "Car Brand", "detail": "e.g., 25% said Mercedes-Benz best captures their style"}},
          {{"category": "Key Stat", "detail": "e.g., 71% prefer brands with a sustainability commitment"}}
        ],
        "mini_tables": {{
          "social_media": [{{"item": "YouTube", "pct": 78}}, {{"item": "Instagram", "pct": 65}}, {{"item": "TikTok", "pct": 45}}],
          "purchase_drivers": [{{"item": "Comfort", "pct": 72}}, {{"item": "Durability", "pct": 58}}, {{"item": "Value", "pct": 51}}],
          "pain_points": [{{"item": "Inconsistent sizing", "pct": 45}}, {{"item": "Poor fabric quality", "pct": 32}}, {{"item": "Limited styles", "pct": 28}}],
          "pre_purchase": [{{"item": "Read reviews", "pct": 82}}, {{"item": "Compare prices", "pct": 65}}, {{"item": "Visit brand site", "pct": 48}}]
        }}
      }}
    ],
    "target_recommendation": {{
      "primary_segment": "Name of recommended primary target segment",
      "title": "PRIMARY TARGET: [SEGMENT NAME] IN CAPS",
      "rationale_bullets": [
        "Reason 1 why this segment should be the primary target — with data",
        "Reason 2 — connect to brand strengths",
        "Reason 3 — connect to market opportunity",
        "Reason 4 — connect to channel fit"
      ],
      "insight": "For this segment, [specific reframe of what premium/quality/value means to them]",
      "enables": ["What targeting this segment unlocks — strategic benefit 1", "Strategic benefit 2", "Strategic benefit 3"],
      "does_not_decide": ["What this choice does NOT determine yet", "Another open question", "Third open question"]
    }},
    "deprioritized_segments": [
      {{
        "name": "Segment Name",
        "size_pct": 17,
        "reason": "Specific reason this segment is not the primary target — e.g., 'Promotion-driven, more price-sensitive, competing here risks compressing margins'"
      }}
    ],
    "competitive_fares": {{
      "brand_strengths": "What each leading competitor wins on — e.g., 'Lululemon → Lifestyle, FIGS → Premium, Cherokee → Heritage'",
      "category_compromise": "What the category forces buyers to compromise on — no brand combines [X] and [Y]",
      "strategic_opportunity": "The specific combination of strengths no brand currently owns",
      "strategic_question": "What would it look like to build a brand that didn't force that compromise?"
    }},
    "consumer_summary": "Flowing paragraph 3-5 sentences. Name the recommended segment, state why they matter, and connect to the brand's capabilities and competitive position. End with a forward-looking statement.",
    "key_insights": [
      {{
        "title": "KEY CONSUMER INSIGHT HEADLINE IN CAPS",
        "bullets": [
          "2-3 sentence insight about purchase behavior with evidence",
          "2-3 sentence insight about unmet needs",
          "2-3 sentence insight about brand perception or willingness to pay",
          "2-3 sentence insight about channel or influence patterns"
        ],
        "insight": "Single sentence strategic reframe of consumer opportunity"
      }}
    ]
  }},

  "summary_and_next_steps": {{
    "capabilities_column": "2-3 sentence paragraph summarizing Step 1 findings. Name the brand and its core strength. State the key gap. Example: 'CozyFit is an execution-driven brand with competitive products and strong Amazon performance, now facing the need to clarify its naming and brand structure to support long-term growth.'",
    "competition_column": "2-3 sentence paragraph summarizing Step 2 findings. Name specific competitors and their roles. State the white space. Example: 'The scrubs market is well established, with leading brands succeeding by owning a clear and focused role—such as lifestyle identity, medical authority, or comfort—rather than trying to compete across everything at once.'",
    "consumer_column": "2-3 sentence paragraph summarizing Step 3 findings. Name the target segment and why they matter. Example: 'Endurance First professionals spend the most, set the highest performance standards, and define what quality means in scrubs—making them the most valuable and influential segment in the market.'",
    "closing_insight": "1-2 sentence forward-looking statement connecting all three pillars. Example: 'Building on these insights, we will define a clear and differentiated brand position—one that resonates with its most demanding customers and scales credibly across the broader market.'"
  }},

  "next_steps": [
    "Specific action 1 tied to capabilities findings — what to fix or build",
    "Specific action 2 tied to competitive positioning — how to differentiate",
    "Specific action 3 tied to consumer targeting — how to activate the target segment",
    "Specific action 4 tied to brand building — the next phase of work"
  ]
}}

CRITICAL RULES:
- This is a COMPREHENSIVE report. Every section must be thorough and evidence-based.
- segments MUST contain 4-5 entries. Each needs:
  * An evocative 2-word name (GOOD: "Endurance First", "Polished Pro", "Tender Caregiver", "Vivid Collector")
  * A first-person tagline that sounds authentic, not corporate
  * A "Meet the [Name]" narrative (5-7 sentences) that OPENS with a vivid character scene
  * Specific what_premium_means (cite attributes and percentages, not generic "quality")
  * 4 lifestyle_signals (social media, music, car brand, key stat) for cultural profiling
  * mini_tables with item+pct data for purchase_drivers, pain_points, pre_purchase, social_media
- brand_challenges MUST contain exactly 3 entries, each with Format A bullets (2-4 sentence paragraphs).
- competitor_analyses MUST contain 6-10 entries (real cases average 8 competitors).
  Each must use Format B (bold-label: detail) for both positioning and key_learnings.
  Labels must be STRATEGIC THEMES, not generic labels like "Target Audience" or "What works".
- All content bullets must be 2-4 sentence paragraphs with specific evidence (Format A).
- All titles must be ALL CAPS and state a finding, not a generic topic.
- All summary fields must be flowing paragraphs connecting strength → gap → next step.
- deprioritized_segments: for EACH non-primary segment, state the specific strategic risk
  (e.g., "Promotion-driven, competing here risks compressing margins and weakening premium positioning")
- competitive_fares must name specific competitors and what they win on (e.g., "Lululemon → Lifestyle, FIGS → Premium")
- Generate 15-20 charts organized in 4 sections (real cases average 22-29 chart slides):
  * Demographics (4-5): generation vbar, gender+ethnicity dual, income hbar, social media hbar
  * Shopping Habits (5-7): purchase frequency+spend dual, channels hbar, occasions hbar, pre-purchase hbar
  * Purchase Drivers (3-4): top drivers hbar, premium definition hbar, willingness-to-pay dual, wordcloud (MUST include 40-60 words with varied frequencies from 5 to 100)
  * Brand Evaluation (4-5): brand metrics grouped_bar (brands on Y, Awareness/Purchase/Satisfaction/Recommend as groups), favorite brand donut, brand switching hbar, brand association matrix
  Use plausible percentages grounded in review/e-commerce evidence. Values must sum logically (donut/pie slices should total ~100).
  Valid chart_type values: "hbar", "dual", "donut", "pie", "vbar", "stacked", "grouped_bar", "wordcloud", "matrix", "table".
- If the language is "zh" or "en+zh", add "_zh" suffixed fields for all text.
- Output ONLY the JSON object, nothing else."""


# ── Analysis Functions ────────────────────────────────────────

async def analyze_brand(
    brand_name: str,
    brand_url: str,
    scrape_data: dict,
    document_data: list[dict],
    competitors: list[str],
    language: str = "en",
    phase: str = "full",
    ecommerce_data: dict = None,
    review_data: dict = None,
    competitor_data: list[dict] = None,
    desktop_research: dict = None,
) -> dict:
    """Run Claude AI analysis on brand data and return structured JSON.

    Args:
        phase: "brand_reality" | "market_structure" | "full"
        desktop_research: Output from 3-session research pipeline
            {"brand_context": {...}, "competitor_profiles": [...], "consumer_landscape": {...}}
    """
    if not client:
        return _mock_analysis(brand_name, phase)

    # Format inputs
    scrape_text = _format_scrape_data(scrape_data)
    doc_text = _format_documents(document_data)
    comp_text = ", ".join(competitors) if competitors else "Not specified — identify key competitors"
    comp_detail_text = _format_competitor_data(competitor_data) if competitor_data else "No competitor discovery data"
    ecom_text = _format_ecommerce(ecommerce_data) if ecommerce_data else "No e-commerce data collected"
    review_text = _format_reviews(review_data) if review_data else "No review data collected"
    research_text = _format_desktop_research(desktop_research) if desktop_research else ""

    import datetime
    date_str = datetime.datetime.now().strftime("%B %Y").upper()

    if phase == "full":
        # Split into 3 sequential calls to avoid token limits
        # Phase 1: Capabilities
        # Inject desktop research into scrape/doc sections for richer context
        brand_research_block = ""
        if research_text:
            brand_research_block = f"\n\n## Desktop Research (Web Search Findings)\n{research_text}\n"

        p1_prompt = BRAND_REALITY_PROMPT.format(
            brand_name=brand_name,
            brand_name_upper=brand_name.upper(),
            brand_url=brand_url,
            language=language,
            scrape_data=(scrape_text or "No website data available") + brand_research_block,
            document_data=doc_text or "No documents uploaded",
            ecommerce_data=ecom_text,
            review_data=review_text,
            date=date_str,
        )
        p1_result = _call_claude(p1_prompt, max_tokens=8000)

        # Phase 2: Competition (feed Phase 1 summary as context)
        p1_context = ""
        if isinstance(p1_result, dict):
            cap = p1_result.get("capabilities", {})
            p1_context = cap.get("capabilities_summary", "")

        # Enrich competitor data with desktop research profiles
        comp_enriched = comp_detail_text
        if desktop_research and desktop_research.get("competitor_profiles"):
            profiles = desktop_research["competitor_profiles"]
            profile_lines = ["\n### Web-Researched Competitor Profiles"]
            for cp in profiles:
                profile_lines.append(
                    f"\n**{cp.get('name', 'Unknown')}** ({cp.get('category_role', 'direct')})\n"
                    f"  Products: {cp.get('product_range', 'N/A')}\n"
                    f"  Pricing: {cp.get('price_range', 'N/A')} ({cp.get('price_positioning', 'N/A')})\n"
                    f"  Target: {cp.get('target_audience', 'N/A')}\n"
                    f"  Differentiator: {cp.get('key_differentiator', 'N/A')}\n"
                    f"  Channels: {cp.get('channel_strategy', 'N/A')}\n"
                    f"  Strengths: {', '.join(cp.get('strengths', []))}\n"
                    f"  Vulnerabilities: {', '.join(cp.get('vulnerabilities', []))}\n"
                    f"  Amazon: {cp.get('amazon_stats', 'N/A')}\n"
                    f"  Learning: {cp.get('key_learning', 'N/A')}"
                )
            comp_enriched = comp_detail_text + "\n".join(profile_lines)

        p2_prompt = MARKET_STRUCTURE_PROMPT.format(
            brand_name=brand_name,
            brand_url=brand_url,
            competitors=comp_text,
            competitor_scrape_data=comp_enriched,
            competitor_ecommerce_data=comp_enriched,
            competitor_review_data=comp_enriched,
            phase1_context=p1_context or "Phase 1 analysis completed — assess competition independently",
        )
        p2_result = _call_claude(p2_prompt, max_tokens=8000)

        # Phase 3: Consumer (feed Phase 1+2 summaries as context)
        p2_context = ""
        if isinstance(p2_result, dict):
            comp_section = p2_result.get("competition", {})
            p2_context = comp_section.get("competition_summary", "")

        p3_prompt = FULL_ANALYSIS_PROMPT.format(
            brand_name=brand_name,
            brand_name_upper=brand_name.upper(),
            brand_url=brand_url,
            language=language,
            scrape_data="[See Phase 1 for website data — focus on consumer analysis]",
            document_data=doc_text or "No documents uploaded",
            ecommerce_data=ecom_text,
            review_data=review_text,
            competitors=comp_text,
            competitor_data=comp_detail_text,
            date=date_str,
        )
        # Build consumer research context from desktop research
        consumer_research_block = ""
        if desktop_research and desktop_research.get("consumer_landscape"):
            cl = desktop_research["consumer_landscape"]
            consumer_research_block = "\n\n## Consumer Research (Web Search Findings)\n"
            consumer_research_block += json.dumps(cl, indent=2, default=str)[:4000]

        # Override the full prompt to only request consumer + summary sections
        consumer_only_prompt = f"""Based on the following Phase 1 and Phase 2 findings, produce the CONSUMER section and final summary.

## Phase 1 Summary (Capabilities)
{p1_context}

## Phase 2 Summary (Competition)
{p2_context}

## E-Commerce Data
{ecom_text}

## Customer Reviews
{review_text}

## Competitor Data
{comp_detail_text}
{consumer_research_block}

## Uploaded Documents
{doc_text or "No documents uploaded"}

Produce the consumer analysis for {brand_name} ({brand_url}).
Language: {language}. Date: {date_str}.

Return this JSON structure:
{{
  "consumer": {{... the full consumer section as specified in the system prompt ...}},
  "summary_and_next_steps": {{
    "capabilities_column": "Paragraph summarizing Step 1 findings",
    "competition_column": "Paragraph summarizing Step 2 findings",
    "consumer_column": "Paragraph summarizing Step 3 findings",
    "closing_insight": "Single sentence tying all three together"
  }},
  "next_steps": ["Action 1", "Action 2", "Action 3", "Action 4"]
}}

CRITICAL RULES:
- Generate 15-20 charts with plausible data organized in 4 sections: Demographics (4-5 charts: generation vbar, gender+ethnicity dual, income hbar, social media hbar), Shopping Habits (5-7: frequency+spend dual, channels hbar, occasions hbar, pre-purchase hbar), Purchase Drivers (3-4: top drivers hbar, premium definition hbar, WTP dual, wordcloud with 40-60 words), Brand Evaluation (4-5: grouped_bar brand metrics, favorite brand donut, switching hbar, association matrix). MUST include at least one "grouped_bar" and one "matrix" chart.
- Generate 4-5 consumer segments, each with:
  * Evocative 2-word name (GOOD: "Endurance First", "Vivid Collector", "Tender Caregiver")
  * First-person tagline that sounds authentic, not corporate
  * "Meet the [Name]" narrative (5-7 sentences) OPENING with a vivid character scene
    Example: "Meet the Endurance First Professional: Picture a Nurse Practitioner halfway through a 12-hour shift in a busy hospital ER..."
  * Specific what_premium_means (cite attributes + percentages)
  * 4 lifestyle_signals for cultural profiling (social media, music, car brand, key stat)
  * mini_tables with item+pct data for chart rendering
- MUST include "deprioritized_segments" array: for EACH non-primary segment, state the specific
  strategic risk (e.g., "Promotion-driven, competing here risks compressing margins and weakening
  premium positioning. Too narrow to build long-term brand authority around.")
- MUST include "competitive_fares" object: brand_strengths (name competitors and what they win on,
  e.g., "Lululemon → Lifestyle, FIGS → Premium, Cherokee → Heritage"), category_compromise,
  strategic_opportunity, strategic_question.
- Output ONLY JSON."""
        p3_result = _call_claude(consumer_only_prompt, max_tokens=10000)

        # Merge all three phases
        merged = {"brand_name": brand_name, "date": date_str}
        if isinstance(p1_result, dict):
            merged["capabilities"] = p1_result.get("capabilities", {})
            merged["next_steps"] = p1_result.get("next_steps", [])
        if isinstance(p2_result, dict):
            merged["competition"] = p2_result.get("competition", {})
        if isinstance(p3_result, dict):
            merged["consumer"] = p3_result.get("consumer", {})
            merged["summary_and_next_steps"] = p3_result.get("summary_and_next_steps", {})
            if p3_result.get("next_steps"):
                merged["next_steps"] = p3_result["next_steps"]
        return merged

    elif phase == "brand_reality":
        prompt = BRAND_REALITY_PROMPT.format(
            brand_name=brand_name,
            brand_name_upper=brand_name.upper(),
            brand_url=brand_url,
            language=language,
            scrape_data=scrape_text or "No website data available",
            document_data=doc_text or "No documents uploaded",
            ecommerce_data=ecom_text,
            review_data=review_text,
            date=date_str,
        )
        return _call_claude(prompt, max_tokens=8000)

    else:  # market_structure
        prompt = MARKET_STRUCTURE_PROMPT.format(
            brand_name=brand_name,
            brand_url=brand_url,
            competitors=comp_text,
            competitor_scrape_data=comp_detail_text,
            competitor_ecommerce_data=comp_detail_text,
            competitor_review_data=comp_detail_text,
            phase1_context="[Phase 1 results would go here]",
        )
        return _call_claude(prompt, max_tokens=8000)


def _call_claude(prompt: str, max_tokens: int = 8000) -> dict:
    """Call Claude API and parse JSON response. Retries on rate limits."""
    for attempt in range(4):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except RateLimitError:
            if attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"[analyzer] Rate limited, waiting {wait}s (attempt {attempt + 1}/4)")
                time.sleep(wait)
            else:
                raise

    text = response.content[0].text
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            return result
    except json.JSONDecodeError:
        pass

    return {"raw_analysis": text}


# ── Input Formatters ──────────────────────────────────────────

def _format_scrape_data(scrape_data: dict) -> str:
    if not scrape_data or not scrape_data.get("pages"):
        return ""
    parts = []
    for page in scrape_data["pages"]:
        parts.append(f"\n### {page.get('title', 'Page')} ({page.get('url', '')})\n{page.get('text', '')[:3000]}\n")
    return "".join(parts)


def _format_documents(documents: list[dict]) -> str:
    if not documents:
        return ""
    parts = []
    for doc in documents:
        parts.append(f"\n### {doc.get('filename', 'Document')}\n{doc.get('text', '')[:5000]}\n")
    return "".join(parts)


def _format_competitor_data(data: list[dict]) -> str:
    if not data:
        return "No competitor discovery data"
    parts = [f"### Auto-Discovered Competitors ({len(data)} found)"]
    for c in data:
        source = c.get("source", "unknown")
        confidence = c.get("confidence", 0)
        role = c.get("category_role", "")
        reason = c.get("reason", "")
        line = f"- {c['name']} (source: {source}, confidence: {confidence:.0%}"
        if role:
            line += f", role: {role}"
        line += ")"
        if reason:
            line += f"\n  {reason}"
        parts.append(line)
    return "\n".join(parts)


def _format_ecommerce(data: dict) -> str:
    if not data:
        return "No e-commerce data"
    parts = []
    if data.get("price_range"):
        pr = data["price_range"]
        parts.append(f"Price Range: ${pr.get('min', 'N/A')} - ${pr.get('max', 'N/A')} (avg ${pr.get('avg', 'N/A')})")
    if data.get("rating_summary"):
        rs = data["rating_summary"]
        parts.append(f"Rating Summary: {rs.get('average', 'N/A')}/5 across {rs.get('total_products', 0)} products ({rs.get('total_reviews', 0)} total reviews)")
    parts.append(f"\n### Products ({len(data.get('products', []))} found)")
    for product in data.get("products", [])[:20]:
        name = product.get("name", "Product")
        price = product.get("price", "N/A")
        rating = product.get("rating", "N/A")
        reviews = product.get("review_count", 0)
        desc = product.get("description", "")[:300]
        features = ", ".join(product.get("features", [])[:5])
        line = f"- {name}: ${price} | {rating}★ ({reviews} reviews)"
        if desc:
            line += f"\n  Description: {desc}"
        if features:
            line += f"\n  Features: {features}"
        parts.append(line)
    return "\n".join(parts) if parts else "No e-commerce data"


def _format_reviews(data: dict) -> str:
    if not data:
        return "No reviews"
    parts = []
    if data.get("summary"):
        s = data["summary"]
        parts.append(f"### Review Summary")
        parts.append(f"Average Rating: {s.get('average_rating', 'N/A')}/5 ({s.get('total_reviews', 0)} reviews)")
        if s.get("rating_distribution"):
            parts.append(f"Rating Distribution: {s['rating_distribution']}")
    if data.get("sentiment"):
        sent = data["sentiment"]
        parts.append(f"\n### Sentiment Analysis")
        parts.append(f"Positive: {sent.get('positive', 0)}% | Neutral: {sent.get('neutral', 0)}% | Negative: {sent.get('negative', 0)}%")
    if data.get("themes"):
        parts.append(f"\n### Top Themes from Reviews")
        themes = data["themes"]
        if isinstance(themes, dict):
            for sentiment_type in ("positive", "negative"):
                for theme in themes.get(sentiment_type, [])[:5]:
                    name = theme.get("theme", theme.get("name", "Theme"))
                    count = theme.get("count", 0)
                    parts.append(f"- {name} ({sentiment_type}): {count} mentions")
                    for quote in theme.get("examples", theme.get("sample_quotes", []))[:2]:
                        parts.append(f'  "{quote}"')
        else:
            for theme in list(themes)[:10]:
                parts.append(f"- {theme.get('theme', 'Theme')}: {theme.get('count', 0)} mentions ({theme.get('sentiment', 'mixed')} sentiment)")
                for quote in theme.get("sample_quotes", [])[:2]:
                    parts.append(f'  "{quote}"')
    parts.append(f"\n### Individual Reviews ({len(data.get('reviews', []))} collected)")
    for review in data.get("reviews", [])[:40]:
        stars = review.get("rating", "")
        title = review.get("title", "")
        text = review.get("text", "")[:300]
        line = f"  [{stars}★]"
        if title:
            line += f" {title} —"
        line += f" {text}"
        parts.append(line)
    return "\n".join(parts) if parts else "No reviews"


def _format_desktop_research(data: dict) -> str:
    """Format desktop research data (from 3-session pipeline) for the analyzer."""
    if not data:
        return ""

    parts = []

    # Brand context (Session 1)
    bc = data.get("brand_context", {})
    if bc and not bc.get("raw_text"):
        bp = bc.get("brand_profile", {})
        if bp:
            parts.append("### Brand Profile (from web research)")
            if bp.get("founding_story"):
                parts.append(f"Founding: {bp['founding_story']}")
            if bp.get("founders"):
                parts.append(f"Founders: {bp['founders']}")
            if bp.get("year_founded"):
                parts.append(f"Founded: {bp['year_founded']}")
            if bp.get("headquarters"):
                parts.append(f"HQ: {bp['headquarters']}")
            milestones = bp.get("key_milestones", [])
            if milestones:
                parts.append(f"Milestones: {'; '.join(milestones[:5])}")
            if bp.get("funding"):
                parts.append(f"Funding: {bp['funding']}")

        op = bc.get("online_presence", {})
        if op:
            parts.append("\n### Online Presence")
            if op.get("website_summary"):
                parts.append(f"Website: {op['website_summary']}")
            sm = op.get("social_media", {})
            for platform in ("instagram", "tiktok", "youtube", "facebook"):
                if sm.get(platform):
                    parts.append(f"  {platform.title()}: {sm[platform]}")
            if op.get("amazon_presence"):
                parts.append(f"Amazon: {op['amazon_presence']}")
            if op.get("other_channels"):
                parts.append(f"Other channels: {op['other_channels']}")

        pos = bc.get("brand_positioning", {})
        if pos:
            parts.append("\n### Brand Positioning Signals")
            if pos.get("target_audience"):
                parts.append(f"Target: {pos['target_audience']}")
            if pos.get("price_positioning"):
                parts.append(f"Price position: {pos['price_positioning']}")
            claims = pos.get("key_claims", [])
            if claims:
                parts.append(f"Key claims: {'; '.join(claims[:5])}")
            diffs = pos.get("differentiators", [])
            if diffs:
                parts.append(f"Differentiators: {'; '.join(diffs[:5])}")
            if pos.get("brand_voice"):
                parts.append(f"Brand voice: {pos['brand_voice']}")

        cat = bc.get("category_landscape", {})
        if cat:
            parts.append("\n### Category Landscape")
            if cat.get("category_name"):
                parts.append(f"Category: {cat['category_name']}")
            if cat.get("market_size"):
                parts.append(f"Market size: {cat['market_size']}")
            if cat.get("growth_rate"):
                parts.append(f"Growth: {cat['growth_rate']}")
            dynamics = cat.get("key_dynamics", [])
            if dynamics:
                parts.append(f"Key dynamics: {'; '.join(dynamics[:5])}")
            trends = cat.get("consumer_trends", [])
            if trends:
                parts.append(f"Consumer trends: {'; '.join(trends[:5])}")

        press = bc.get("press_coverage", [])
        if press:
            parts.append("\n### Press Coverage")
            for article in press[:5]:
                parts.append(f"- {article.get('source', '')}: {article.get('headline', '')} — {article.get('summary', '')}")

        rep = bc.get("reputation_signals", {})
        if rep:
            parts.append(f"\n### Reputation: {rep.get('sentiment', 'unknown')}")
            strengths = rep.get("strengths_mentioned", [])
            if strengths:
                parts.append(f"Praised for: {'; '.join(strengths[:5])}")
            concerns = rep.get("concerns_mentioned", [])
            if concerns:
                parts.append(f"Criticized for: {'; '.join(concerns[:5])}")

    return "\n".join(parts) if parts else ""


# ── Mock Analysis ─────────────────────────────────────────────

def _mock_analysis(brand_name: str, phase: str = "full") -> dict:
    """Return mock analysis for development/testing."""
    bn = brand_name
    BN = brand_name.upper()

    capabilities = {
        "execution_summary": {
            "title": f"HOW {BN} WAS BUILT: EXECUTION FIRST",
            "bullets": [
                f"{bn} prioritized product quality and pricing over brand building. Messaging is purely functional.",
                f"Amazon-first launch with product iteration over brand — a founder-led, execution-first approach.",
                f"Built sales velocity and reviews, but deferred brand definition — gaps that now limit growth.",
            ],
            "insight": f"{bn}'s success was execution-driven — but execution alone cannot sustain premium growth.",
            "has_image": True,
        },
        "product_offer": {
            "title": "A FUNCTIONAL, FEATURE-LED, VALUE-FOCUSED OFFER",
            "bullets": [
                f"{bn} emphasizes comfort, fit, and affordability. Product pages list functional benefits only.",
                "No aspirational imagery or lifestyle positioning. Communication is purely rational, not emotional.",
                f"Easy to compare on Amazon — drives conversion but positions {bn} as interchangeable.",
            ],
            "insight": f"{bn} presents as a practical solution — a strong product, but not yet a brand.",
            "has_image": True,
        },
        "product_fundamentals": {
            "title": f"PRODUCT FUNDAMENTALS ARE STRONG",
            "bullets": [
                f"{bn}'s fabric tech — 4-way stretch, moisture-wicking — matches premium competitors at lower prices.",
                "Competitive features: 5-7 pockets, jogger pants, modern tops, growing color range.",
                "Core categories covered (tops, pants, jackets) but no accessories — limiting loyalty drivers.",
            ],
            "insight": f"The product is {bn}'s strongest asset — competitive enough for a premium position.",
        },
        "pricing_position": {
            "title": f"PRICE-PERFORMANCE DEFINES {BN}'S POSITION",
            "bullets": [
                f"{bn} at $28-$42/piece sits below FIGS ($38-$90) with comparable performance. Strong value.",
                "Promotional language (deals, bundles) anchors the brand in accessible tier, not premium.",
                "Drives volume but limits premium perception. Moving up requires brand story, not just price.",
            ],
            "insight": f"{bn}'s role is defined by value, not brand — solid base, but a ceiling if not evolved.",
        },
        "channel_analysis": {
            "title": f"AMAZON DRIVES GROWTH AND TRUST",
            "bullets": [
                f"Primary channel: Amazon with 2,000+ reviews and 4.3+ rating. Amazon's trust does the work.",
                "Brand website (Shopify) is a store, not a brand experience. Minimal lifestyle content.",
                "Social media lacks consistent cadence, engagement strategy, or ambassador programs.",
            ],
            "insight": f"Amazon builds Amazon's brand, not {bn}'s. Equity requires owning the relationship.",
        },
        "brand_challenges": [
            {
                "title": f"THE {BN} NAME CREATES A CHALLENGE",
                "bullets": [
                    "The name signals comfort but may not convey professional credibility or performance.",
                    "FIGS and Cherokee carry clear positioning — a comfort name risks pigeonholing.",
                    "The name shapes Amazon search impressions and CTR — structural, not cosmetic.",
                ],
                "insight": "A brand name is the first promise — and it may be making the wrong one.",
            },
            {
                "title": "BRAND NARRATIVE AND EMOTIONAL CONNECTION ABSENT",
                "bullets": [
                    "No origin story or mission messaging. The brand says what it sells, not why.",
                    "FIGS builds community, Cherokee has heritage. Even value brands tell a story.",
                    f"Without narrative, {bn} competes on features and price — most vulnerable position.",
                ],
                "insight": "A brand without a story is a commodity — or a canvas waiting to be defined.",
            },
            {
                "title": "THE NEXT STEP IS RESEARCH-LED CLARITY",
                "bullets": [
                    f"{bn} has reached an inflection point: execution alone won't drive next-stage growth.",
                    "Positioning and audience decisions require consumer research, not intuition.",
                    "Strong fundamentals + channel traction = foundation. Delay risks losing territory.",
                ],
                "insight": f"{bn} has built the engine — now it needs a destination.",
            },
        ],
        "capabilities_summary": (
            f"{bn} is execution-driven with strong products and Amazon traction, "
            "but lacks brand narrative and emotional positioning. "
            "Product fundamentals can support a premium position — the brand just hasn't been built yet. "
            "Next steps: consumer insight and competitive clarity."
        ),
        "claims_vs_perception": {
            "brand_claims": [
                "Premium comfort and stretch for healthcare professionals",
                "High-quality fabric technology at accessible prices",
            ],
            "customer_perception": [
                "Comfortable and good value for the price — strong functional satisfaction",
                "Not seen as a 'brand' — viewed as a good Amazon product, not a lifestyle choice",
            ],
            "alignment": "Customers confirm the comfort and value claims — the product delivers on its functional promises.",
            "gaps": "The brand claims 'premium' but customers perceive 'good value' — there is a credibility gap between aspiration and perception that must be closed through brand building, not just product quality.",
        },
    }

    result = {
        "brand_name": bn,
        "date": "APRIL 2026",
        "capabilities": capabilities,
        "next_steps": [
            "Define a clear brand narrative and origin story that goes beyond functional benefits.",
            "Clarify brand architecture — establish the relationship between parent brand and product lines.",
            "Develop emotional positioning that complements existing functional strengths.",
            "Audit visual identity consistency across Amazon, website, and social channels.",
        ],
    }

    if phase == "brand_reality":
        return result

    # Add competition for market_structure and full
    result["competition"] = {
        "market_overview": {
            "title": "A MATURE, WELL-ESTABLISHED MEDICAL APPAREL MARKET",
            "competitor_names": ["FIGS", "Cherokee", "Carhartt", "Med Couture", "Healing Hands", "Dickies", "Jaanuu", "Barco", "WonderWink", "Dagacci"],
            "bullets": [
                "US scrubs market exceeds $10B with clear roles: premium (FIGS), heritage (Cherokee), fashion (Med Couture).",
                "Key shifts: wholesale to DTC, Amazon as discovery channel, demand for modern fits and athletic silhouettes.",
                f"Top brands own a clear market role. {bn} competes on features and price — no distinct brand identity yet.",
            ],
            "insight": "Winning brands own a clear role — not by trying to be everything to everyone.",
        },
        "focused_competitors": ["FIGS", "Cherokee", "Carhartt", "Med Couture", "Healing Hands", "Jaanuu"],
        "competitor_analyses": [
            {
                "name": "FIGS",
                "banner_description": "Premium lifestyle pioneer proving scrubs buyers will pay for brand",
                "positioning": [
                    {"label": "Target Audience", "detail": "Young pros (25-40) who see scrubs as lifestyle. Skews female, urban."},
                    {"label": "Price Point", "detail": "$38-$90/piece, firmly premium. Price signals quality."},
                    {"label": "Key Differentiator", "detail": "Created fashion-forward medical apparel. Strong DTC + community."},
                ],
                "key_learnings": [
                    {"label": "Brand-led growth works", "detail": "Proved scrubs buyers pay premium for brand, not just function."},
                    {"label": "Ambassador model scales", "detail": "Influencer program drives acquisition. Community = switching costs."},
                    {"label": "Premium fatigue", "detail": "Some buyers seek FIGS quality at lower prices. Territory is open."},
                ],
            },
            {
                "name": "Cherokee",
                "banner_description": "Heritage authority — decades of trust, slow to modernize",
                "positioning": [
                    {"label": "Target Audience", "detail": "Broad workforce, value-conscious. Skews older, less brand-sensitive."},
                    {"label": "Price Point", "detail": "$18-$45/piece, accessible mid-market with frequent promos."},
                    {"label": "Key Differentiator", "detail": "84% brand awareness + widest distribution in the category."},
                ],
                "key_learnings": [
                    {"label": "Trust via longevity", "detail": "Decades of credibility newer brands can't easily replicate."},
                    {"label": "Distribution depth", "detail": "Available everywhere but inconsistent brand experience."},
                    {"label": "Slow to modernize", "detail": "Website and social lag behind DTC competitors. Vulnerable."},
                ],
            },
            {
                "name": "Carhartt",
                "banner_description": "Durability icon crossing from workwear into healthcare",
                "positioning": [
                    {"label": "Target Audience", "detail": "Workers who value 'hard work' culture. Strong male appeal."},
                    {"label": "Price Point", "detail": "$25-$55/piece, mid-to-premium. Heritage brand pricing."},
                    {"label": "Key Differentiator", "detail": "Iconic 'built to last' credibility transfers to scrubs."},
                ],
                "key_learnings": [
                    {"label": "Brand transfer works", "detail": "Adjacent category credibility creates instant trust."},
                    {"label": "Limited depth", "detail": "Narrower range — scrubs are an extension, not core business."},
                    {"label": "Gender gap", "detail": "Masculine brand limits appeal to 70% female scrubs market."},
                ],
            },
            {
                "name": "Med Couture",
                "banner_description": "Fashion-forward scrubs with modern fits and bold patterns",
                "positioning": [
                    {"label": "Target Audience", "detail": "Style-conscious pros wanting good-looking scrubs. Young, female."},
                    {"label": "Price Point", "detail": "$30-$55/piece, mid-to-premium for design quality."},
                    {"label": "Key Differentiator", "detail": "Bold prints, modern silhouettes, trend-responsive collections."},
                ],
                "key_learnings": [
                    {"label": "Style drives loyalty", "detail": "Buyers choose on style as much as function. High repeat rate."},
                    {"label": "Niche limits scale", "detail": "Fashion-forward appeals to one segment but not mass market."},
                    {"label": "Pattern over platform", "detail": "Innovates on color, not fabric tech. Style+substance gap open."},
                ],
            },
        ],
        "landscape_summary": {
            "market_roles": [
                {"role": "Premium Lifestyle", "brands": ["FIGS", "Jaanuu"], "description": "Brand-led, DTC, aspirational. Highest prices + loyalty."},
                {"role": "Heritage Authority", "brands": ["Cherokee", "Dickies"], "description": "Decades of trust, wide distribution, but not modern."},
                {"role": "Performance Crossover", "brands": ["Carhartt"], "description": "Adjacent category equity. Durable but limited depth."},
                {"role": "Fashion-Forward", "brands": ["Med Couture", "Healing Hands"], "description": "Style-first with modern fits and bold patterns."},
            ],
            "white_space": f"No brand owns 'real performance at accessible price.' {bn}'s fundamentals could fill this gap with a clear brand story.",
            "category_norms": [
                "Comfort/stretch are table stakes — every brand offers 4-way stretch",
                "Color variety expected (20+ colors) and growing",
                "Pocket count/design are key Amazon differentiators",
            ],
        },
        "competition_summary": (
            f"Leading scrubs brands win by owning a clear role — lifestyle, heritage, durability, or style. "
            f"The white space for {bn} is premium product performance at accessible pricing. "
            "Claiming this requires a defined brand strategy, target audience, and consistent execution."
        ),
    }

    if phase == "market_structure":
        return result

    # Add consumer for full
    result["consumer"] = {
        "overview": "Healthcare professionals who purchase their own scrubs represent a diverse but segmentable market. Primarily female (70%), Millennial-dominated (55%), and increasingly willing to invest in quality scrubs — 88% agree they'd pay more for scrubs that clearly deliver on what matters to them.",
        "research_approach": [
            {"label": "Format", "detail": "Review analysis + e-commerce data mining + secondary research"},
            {"label": "Data Sources", "detail": "Amazon reviews, brand website content, competitor listings, industry reports"},
            {"label": "Participants", "detail": "Healthcare professionals: nurses, medical assistants, technicians, physicians; primary/shared purchase decision-makers"},
            {"label": "Analysis", "detail": "Sentiment analysis, theme extraction, behavioral clustering, competitive benchmarking"},
            {"label": "Timing", "detail": "APRIL 2026"},
        ],
        "charts": [
            # ── Demographics (4 charts) ──
            {
                "chart_type": "vbar",
                "title": "RESPONDENT GENERATION PROFILE",
                "subtitle": "Generation distribution of survey respondents",
                "categories": ["Gen Z (18-27)", "Millennial (28-43)", "Gen X (44-59)", "Boomer (60+)"],
                "values": [12, 55, 25, 8],
            },
            {
                "chart_type": "dual",
                "title": "GENDER AND ETHNICITY BREAKDOWN",
                "subtitle": "Respondent demographic composition",
                "left_type": "donut", "left_title": "Gender",
                "left_categories": ["Female", "Male", "Non-binary"],
                "left_values": [70, 28, 2],
                "right_type": "hbar", "right_title": "Race / Ethnicity",
                "right_categories": ["White/Caucasian", "Black/African American", "Hispanic/Latino", "Asian/Pacific Islander", "Other"],
                "right_values": [48, 24, 16, 8, 4],
            },
            {
                "chart_type": "hbar",
                "title": "HOUSEHOLD INCOME DISTRIBUTION",
                "subtitle": "Annual household income brackets",
                "categories": ["Under $25K", "$25K-$49K", "$50K-$74K", "$75K-$99K", "$100K-$149K", "$150K+"],
                "values": [6, 15, 22, 24, 21, 12],
            },
            {
                "chart_type": "hbar",
                "title": "SOCIAL MEDIA PLATFORMS USED",
                "subtitle": "Which social media platforms respondents frequently use",
                "categories": ["YouTube", "Instagram", "Facebook", "TikTok", "Pinterest", "X/Twitter", "Reddit"],
                "values": [78, 65, 62, 48, 35, 28, 22],
            },
            # ── Shopping Habits (5 charts) ──
            {
                "chart_type": "dual",
                "title": "PURCHASE FREQUENCY AND ANNUAL SPEND",
                "subtitle": "How often and how much respondents spend on scrubs",
                "left_type": "donut", "left_title": "Purchase frequency (past 12 months)",
                "left_categories": ["Monthly+", "Every 2-3 months", "2-3x/year", "Once/year", "When needed"],
                "left_values": [18, 42, 27, 7, 6],
                "right_type": "hbar", "right_title": "Annual spend on scrubs",
                "right_categories": ["Under $100", "$100-$199", "$200-$299", "$300-$499", "$500+"],
                "right_values": [10, 22, 30, 25, 13],
            },
            {
                "chart_type": "hbar",
                "title": "WHERE CONSUMERS PURCHASE SCRUBS",
                "subtitle": "Primary purchase channels (select all that apply)",
                "categories": ["Amazon", "Specialty uniform stores", "Walmart", "Brand websites (DTC)", "Target", "Employer-provided"],
                "values": [59, 51, 38, 41, 26, 25],
            },
            {
                "chart_type": "hbar",
                "title": "WHEN AND WHY CONSUMERS PURCHASE SCRUBS",
                "subtitle": "Usage occasions and triggers",
                "categories": ["Regular replacement cycle", "Worn out / damaged", "New job / role change", "Seasonal refresh", "Sale / promotion", "Gift"],
                "values": [65, 52, 38, 28, 22, 8],
            },
            {
                "chart_type": "hbar",
                "title": "PRE-PURCHASE ACTIVITIES",
                "subtitle": "Steps taken before buying scrubs",
                "categories": ["Read online reviews", "Compare prices across sites", "Visit brand website", "Ask coworkers", "Watch YouTube reviews", "Try in store", "Check social media"],
                "values": [78, 62, 45, 42, 35, 30, 25],
            },
            # ── Purchase Drivers (4 charts) ──
            {
                "chart_type": "hbar",
                "title": "WHAT MATTERS MOST IN SCRUBS",
                "subtitle": "Top purchase drivers (select top 3)",
                "categories": ["All-day comfort", "Stretch and flexibility", "Durability after washing", "Breathability", "Easy care", "Pockets / storage", "Fluid resistance", "Soft hand feel", "Consistent sizing"],
                "values": [61, 42, 40, 28, 27, 23, 18, 17, 15],
            },
            {
                "chart_type": "hbar",
                "title": "WHAT DOES 'PREMIUM' MEAN IN SCRUBS?",
                "subtitle": "Consumer definition of premium (select all that apply)",
                "categories": ["Superior fabric technology", "Professional brand reputation", "Modern design / flattering fit", "Longer lasting durability", "Sustainable / ethical materials", "Endorsed by medical pros"],
                "values": [52, 38, 35, 32, 28, 22],
            },
            {
                "chart_type": "dual",
                "title": "WILLINGNESS TO PAY FOR QUALITY",
                "subtitle": "Price sensitivity and premium willingness",
                "left_type": "donut", "left_title": "Willing to pay more\nfor quality scrubs",
                "left_categories": ["Strongly agree", "Somewhat agree", "Neutral", "Disagree"],
                "left_values": [35, 40, 15, 10],
                "right_type": "hbar", "right_title": "Expected price per piece\nfor quality scrubs",
                "right_categories": ["Under $25", "$25-$39", "$40-$59", "$60-$89", "$90+"],
                "right_values": [8, 28, 35, 22, 7],
            },
            {
                "chart_type": "wordcloud",
                "title": "WHAT CONSUMERS SAY ABOUT SCRUBS",
                "subtitle": "Word frequency from open-ended responses and reviews",
                "words": {
                    "comfortable": 100, "durable": 90, "stretchy": 85, "soft": 82,
                    "pockets": 78, "breathable": 75, "professional": 70, "affordable": 68,
                    "quality": 65, "lightweight": 62, "flattering": 58, "modern": 55,
                    "wrinkle-free": 52, "moisture-wicking": 50, "sizing": 48, "colors": 45,
                    "wash well": 42, "value": 40, "stylish": 38, "fade-resistant": 35,
                    "jogger": 33, "athletic": 30, "sustainable": 28, "innovative": 25,
                    "fit": 95, "price": 88, "material": 72, "design": 60, "functional": 55,
                    "reliable": 50, "versatile": 48, "practical": 45, "trendy": 40,
                    "performance": 38, "easy care": 35, "true to size": 32, "color options": 30,
                    "well made": 28, "great fabric": 25, "love it": 22, "recommend": 20,
                    "worth it": 18, "everyday wear": 15, "work approved": 12, "long lasting": 10,
                    "good pockets": 8, "nice feel": 7, "runs small": 6, "great value": 5,
                },
            },
            # ── Brand Evaluation (5 charts) ──
            {
                "chart_type": "grouped_bar",
                "title": "BRAND METRICS — AWARENESS TO ADVOCACY",
                "subtitle": "Brand performance across key metrics",
                "horizontal": True,
                "categories": ["Dickies", "Cherokee", "FIGS", "Carhartt", "Med Couture", f"{bn}", "Healing Hands", "Jaanuu"],
                "groups": [
                    {"name": "Awareness", "values": [84, 78, 65, 62, 42, 38, 28, 16]},
                    {"name": "Purchase", "values": [52, 48, 35, 30, 22, 18, 15, 8]},
                    {"name": "Satisfaction", "values": [72, 68, 82, 75, 70, 78, 65, 72]},
                    {"name": "Recommend", "values": [55, 50, 72, 58, 52, 65, 48, 55]},
                ],
            },
            {
                "chart_type": "donut",
                "title": "FAVORITE SCRUBS BRAND REGARDLESS OF PRICE",
                "subtitle": "Which brand is your absolute favorite?",
                "center_text": "N=200",
                "categories": ["FIGS", "Cherokee", "Dickies", "Carhartt", f"{bn}", "Med Couture", "No favorite"],
                "values": [24, 18, 16, 12, 10, 8, 12],
            },
            {
                "chart_type": "hbar",
                "title": "LIKELIHOOD TO TRY A NEW SCRUBS BRAND",
                "subtitle": "How open are consumers to switching brands?",
                "categories": ["Very likely", "Somewhat likely", "Neutral", "Somewhat unlikely", "Very unlikely"],
                "values": [22, 35, 25, 12, 6],
            },
            {
                "chart_type": "matrix",
                "title": "BRAND ASSOCIATION MATRIX",
                "subtitle": "Which brand best fits each description?",
                "row_labels": ["Best quality", "Best value", "Most innovative", "Most trustworthy", "Most stylish", "Would recommend"],
                "col_labels": ["FIGS", "Cherokee", "Dickies", "Carhartt", f"{bn}", "Med Couture"],
                "values": [
                    [42, 18, 15, 22, 20, 12],
                    [12, 35, 42, 28, 38, 15],
                    [38, 8, 10, 15, 22, 28],
                    [35, 42, 32, 38, 18, 12],
                    [45, 10, 8, 12, 15, 35],
                    [40, 22, 18, 25, 28, 15],
                ],
            },
        ],
        "verbatim_quotes": [
            {
                "theme": "Comfort & Durability",
                "quotes": [
                    "I need the right kind of comfort to last all shift",
                    "They don't last long, not durable",
                    "The material changes over time washing them",
                ],
            },
            {
                "theme": "Fit & Sizing",
                "quotes": [
                    "Sizing doesn't always fit — I have to get medium bottoms and large tops",
                    "I wish they scrubs were more durable with colors lasting longer",
                    "The drawstring tie on most pants is unusable",
                ],
            },
            {
                "theme": "Value & Price",
                "quotes": [
                    "I think that they should be more affordable regardless of quality",
                    "The cost is a bit high for the quality",
                    "Don't mind paying more for a durable, fashionable sharp looking professional scrub",
                ],
            },
        ],
        "segments": [
            {
                "name": "Endurance First",
                "tagline": "I want scrubs that perform as hard as I do",
                "size_pct": 27,
                "narrative": (
                    f"Meet the Endurance First buyer: a Nurse Practitioner or Physician Assistant pulling 10-12 hour shifts "
                    "in a hospital environment, where every piece of clothing is tested by constant movement, fluid exposure, "
                    "and repeated washing. This segment (73% under 45, 36% household income over $100K) views scrubs as "
                    "essential performance equipment — not uniforms, not fashion. They spend the most annually ($393 median) "
                    "and buy every 2-3 months, driven by replacement cycles rather than impulse. What matters: durability that "
                    "survives 100+ wash cycles, stretch that doesn't lose shape, and comfort that holds up from hour 1 to hour 12. "
                    "They research heavily on Amazon (27% default to Amazon for speed and reviews) and are willing to pay more — "
                    "58% strongly agree they'd pay more for scrubs that deliver. Their frustration: too many brands promise "
                    "performance but can't survive the reality of a demanding healthcare shift."
                ),
                "demographics": {
                    "primary_role": "Nurse Practitioner (NP) / Physician Assistant (PA)",
                    "age_skew": "73% under 45 — predominantly Millennial with significant Gen X presence",
                    "income": "36% household income over $100K — highest earning segment",
                    "gender_split": "65% female, 35% male",
                },
                "shopping_behavior": {
                    "annual_spend": "$393 median — highest of all segments",
                    "primary_channel": "Amazon (27%) and brand websites (20%) — product-dependent shoppers (38%)",
                    "purchase_frequency": "71% buy every 2-3 months or more — highest frequency",
                    "brand_loyalty": "Medium — loyal to performance, not brand name. Will switch if quality drops.",
                },
                "top_needs": ["Longer-lasting durability (51%)", "Better fabric performance (49%)", "More consistent fit (40%)"],
                "pain_points": ["Inconsistent sizing between brands (35%)", "Scrubs lose shape over time (29%)", "Insufficient pockets (24%)"],
                "what_premium_means": "Evidence of superior fabric technology (42%), professional brand name (27%), and endorsements from medical professionals (24%). Premium = proof of performance.",
                "lifestyle_signals": [
                    {"category": "Social Media", "detail": "78% use YouTube more than any other social media platform"},
                    {"category": "Music Preference", "detail": "45% like Rock music with 41% who like Hip-Hop/Rap"},
                    {"category": "Wishlist", "detail": "Better fit & sizing as well as fabric quality & durability"},
                ],
            },
            {
                "name": "Fit Focused",
                "tagline": "I want scrubs that look as good as they feel",
                "size_pct": 25,
                "narrative": (
                    "Meet the Fit Focused buyer: a Medical Assistant or Technician in her late 20s to early 30s, scrolling "
                    "through scrubs on her phone between patients, looking for that perfect combination of professional fit "
                    "and personal style. This segment (45% under 45, primarily Millennial) cares deeply about how scrubs look "
                    "AND feel — they want modern silhouettes, flattering cuts, and colors that express personality while "
                    "maintaining professionalism. At $245 median annual spend, they're price-conscious but willing to invest "
                    "in the right piece. Their biggest frustration: length issues (41%) and inconsistent sizing (25%) turn "
                    "online shopping into a gamble. They want longer-lasting durability (75%) and better fabric performance (45%), "
                    "but they won't sacrifice fit for function. If a brand can solve the sizing problem AND deliver on style, "
                    "this segment becomes fiercely loyal."
                ),
                "demographics": {
                    "primary_role": "Medical Assistant / Technician",
                    "age_skew": "45% under 45 — more evenly distributed across generations",
                    "income": "31% household income over $100K",
                    "gender_split": "70% female, 30% male",
                },
                "shopping_behavior": {
                    "annual_spend": "$245 median — lowest of active segments",
                    "primary_channel": "Amazon (33%) but also brand websites (16%) and value-seeking (25%)",
                    "purchase_frequency": "51% buy every 2-3 months or less — more deliberate purchases",
                    "brand_loyalty": "High once they find the right fit — switching cost is the hassle of re-sizing",
                },
                "top_needs": ["All-day comfort (57%)", "Durability after repeated washing (55%)", "Stretch and flexibility (33%)"],
                "pain_points": ["Length issues — too short or too long (41%)", "Insufficient pocket space (25%)", "Inconsistent sizing between brands (25%)"],
                "what_premium_means": "High-end modern design with flattering cuts (31%), superior fabric technology (41%), and a dedicated website beyond Amazon (24%). Premium = looking professional AND feeling good.",
                "lifestyle_signals": [
                    {"category": "Social Media", "detail": "YouTube is the dominant platform with strong Instagram usage"},
                    {"category": "Style Identity", "detail": "Values modern, flattering silhouettes that maintain professionalism"},
                    {"category": "Wishlist", "detail": "Better fit & sizing is the #1 priority, followed by fabric quality"},
                ],
            },
            {
                "name": "Value Hunter",
                "tagline": "I want the best quality I can get for the price",
                "size_pct": 21,
                "narrative": (
                    "Meet the Value Hunter: a Registered Nurse with her shopping cart open, calculator in hand, comparing "
                    "prices across three websites. She's not cheap, she's strategic. This segment (58% Millennial, split between "
                    "married and single) earns mostly upper-middle income (51%) with 30% low-middle. At $294 spent annually, they "
                    "demand the best quality for every dollar. They shop Amazon (63%), specialty uniform stores (50%), and brand "
                    "websites (44%) hunting for deals. 'Premium' must prove itself: superior fabric technology (40%) and a "
                    "professional brand experience beyond Amazon (30%). Their biggest headache: inconsistent sizing (40%) turns "
                    "online shopping into a gamble. They want brands to deliver fair value and stop forcing them to choose "
                    "between budget and scrubs that actually work."
                ),
                "demographics": {
                    "primary_role": "Medical Assistant / Technician (44%), Registered Nurse (28%)",
                    "age_skew": "58% Millennial, 23% Gen X — core working-age",
                    "income": "51% upper-middle income, 30% low-middle",
                    "gender_split": "67% female, 33% male",
                },
                "shopping_behavior": {
                    "annual_spend": "$294 median",
                    "primary_channel": "Amazon (63%) and specialty stores (50%) — comparison shoppers (37% choose best value)",
                    "purchase_frequency": "63% buy every 2-3 months or more",
                    "brand_loyalty": "Low — loyalty goes to value, not brand name. Will switch for a better deal.",
                },
                "top_needs": ["All-day comfort (72%)", "Stretch and flexibility (44%)", "Durability after repeated washing (35%)"],
                "pain_points": ["Inconsistent sizing between brands (40%)", "Scrubs lose shape over time (26%)", "Tightness in hips or thighs (26%)"],
                "what_premium_means": "Evidence of superior fabric technology (40%), a dedicated website with professional brand experience beyond Amazon (30%), higher pricing that signals quality (26%). Premium = proven performance at fair price.",
                "lifestyle_signals": [
                    {"category": "Social Media", "detail": "88% use Facebook more than any other social media platform"},
                    {"category": "Music Preference", "detail": "53% prefer Hip-Hop/Rap with 51% who like R&B/Soul"},
                    {"category": "Wishlist", "detail": "Better price / affordability and better fit & sizing"},
                ],
            },
            {
                "name": "Polished Pro",
                "tagline": "I want scrubs that make me look polished and confident",
                "size_pct": 18,
                "narrative": (
                    "Meet the Polished Pro: a physician adjusting her scrubs before rounds, ensuring every detail projects "
                    "confidence. Appearance isn't vanity, it's professional presence. This segment (53% Millennial, 64% married) "
                    "is the highest earner with 47% high income, 31% upper-middle. At $294 spent annually, they invest in scrubs "
                    "that look as capable as they are. The most clinically advanced segment (42% RNs, 19% Medical Assistants, "
                    "14% Physicians/Surgeons). Image-conscious and quality-driven: Amazon (64%), specialty stores (61%), Walmart (47%). "
                    "'Premium' means superior fabric technology (39%) plus high-end, modern design with flattering cuts (36%). "
                    "81% use Instagram more than any other segment — they're visually engaged and style-aware. They'll pay premium "
                    "but only if scrubs deliver both professionalism and performance."
                ),
                "demographics": {
                    "primary_role": "Registered Nurse (42%), Medical Assistant (19%), Physician/Surgeon (14%)",
                    "age_skew": "53% Millennial, 25% Gen X, 17% Gen Z",
                    "income": "47% high income, 31% upper-middle — highest income segment",
                    "gender_split": "69% female, 31% male",
                },
                "shopping_behavior": {
                    "annual_spend": "$294 median",
                    "primary_channel": "Amazon (64%) and specialty stores (61%), brand websites (33%) — highest DTC affinity",
                    "purchase_frequency": "61% buy every 2-3 months or more",
                    "brand_loyalty": "High — invest in brands that reflect their professional image. Highest brand awareness overall.",
                },
                "top_needs": ["All-day comfort (50%)", "Stretch and flexibility (50%)", "Durability after repeated washing (39%)"],
                "pain_points": ["Inconsistent sizing between brands (40%)", "Scrubs lose shape over time (26%)", "Tightness in hips or thighs (26%)"],
                "what_premium_means": "Superior fabric technology (39%), high-end modern design with flattering cuts (36%), dedicated website with professional brand experience (31%), sustainable materials (33% — highest of any segment). Premium = looking sharp AND performing well.",
                "lifestyle_signals": [
                    {"category": "Social Media", "detail": "81% use Instagram more than any other segment — visually engaged and style-aware"},
                    {"category": "Style Identity", "detail": "Professional, polished appearance is central to identity"},
                    {"category": "Wishlist", "detail": "Better fit & sizing as well as fabric quality & durability"},
                ],
            },
            {
                "name": "Basic Buyer",
                "tagline": "I just need scrubs that work",
                "size_pct": 8,
                "narrative": (
                    "Meet the Basic Buyer: a healthcare worker who views scrubs as a necessary uniform, not a category worth "
                    "investing thought or money into. This smallest segment treats scrubs as purely functional — whatever is cheapest, "
                    "most available, and good enough will do. They buy infrequently, spend the least, and have minimal brand awareness "
                    "or loyalty. They are not a viable target for any brand seeking to build premium positioning, but they represent "
                    "the floor of the market and help define what 'commodity scrubs' looks like — the position every brand should "
                    "want to avoid."
                ),
                "demographics": {
                    "primary_role": "Mixed — various entry-level healthcare roles",
                    "age_skew": "Broadly distributed across generations",
                    "income": "Predominantly low to low-middle income",
                    "gender_split": "60% female, 40% male",
                },
                "shopping_behavior": {
                    "annual_spend": "Under $150 median — lowest of all segments",
                    "primary_channel": "Walmart and employer-provided — convenience-driven",
                    "purchase_frequency": "Only when items wear out",
                    "brand_loyalty": "None — purely price and availability driven",
                },
                "top_needs": ["Low price", "Availability", "Basic comfort"],
                "pain_points": ["Having to buy scrubs at all", "Price of quality scrubs"],
                "what_premium_means": "Not relevant — this segment does not engage with premium concepts",
                "lifestyle_signals": [],
            },
        ],
        "target_recommendation": {
            "primary_segment": "Endurance First",
            "title": "PRIMARY TARGET: ENDURANCE FIRST PROFESSIONALS",
            "rationale_bullets": [
                f"Defines quality: If scrubs perform for the most demanding shifts, they earn trust across the market. Endurance First professionals set the performance standard for the category — winning them validates the product for everyone else.",
                f"Highest value: Spend $393 annually (highest of all segments) and 58% strongly agree they'd pay more for scrubs that deliver. They are willing to invest in proven performance.",
                f"Strong product fit: Their unmet needs — durability, fabric performance, consistent fit — align directly with {bn}'s execution strengths. The product already delivers what they want; the brand just needs to communicate it.",
                f"Natural channel fit: Already research and shop heavily on Amazon (27% default channel), where {bn} has established traction. The path to reach them is already built.",
            ],
            "insight": "For this segment, 'premium' means proof that the product works — not image or prestige. This is a credibility path, not a lifestyle play.",
            "enables": [
                "A clear decision filter for product performance and quality standards",
                f"A credible path to brand elevation without lifestyle positioning or premium pricing",
                "Natural spillover to adjacent segments who value durability and fit",
            ],
            "does_not_decide": [
                "Final brand positioning or tone",
                f"The future role of {bn}'s current brand name versus a new brand",
                "Pricing architecture or promotional strategy",
            ],
        },
        "deprioritized_segments": [
            {"name": "Fit Focused", "size_pct": 25,
             "reason": "Comfort-first, lower spend. Strong secondary target but not the right anchor for premium positioning."},
            {"name": "Value Hunter", "size_pct": 21,
             "reason": "Price-driven, promotion-sensitive. Competing here risks compressing margins and weakening brand perception."},
            {"name": "Polished Pro", "size_pct": 18,
             "reason": "Style-first, high expectations. Requires visual brand assets not yet built — strong future target after brand elevation."},
        ],
        "competitive_fares": {
            "brand_strengths": "FIGS → Lifestyle & Premium, Cherokee → Heritage & Trust, Dickies → Durability, Carhartt → Workwear Authority",
            "category_compromise": "The category forces buyers to choose between affordable performance and premium brand experience. No brand combines both.",
            "strategic_opportunity": f"A brand that delivers proven performance at accessible prices with a credible, modern identity — {bn}'s execution strengths point directly here.",
            "strategic_question": f"What would it look like to build a brand that earns the trust of the most demanding professionals — and grows from there?",
        },
        "consumer_summary": (
            "Endurance First professionals spend the most and define what quality means in scrubs. "
            f"Their needs align with {bn}'s product strengths and Amazon presence. "
            "Next: define a brand position that resonates with performance-first buyers."
        ),
        "key_insights": [
            {
                "title": "KEY CONSUMER INSIGHTS",
                "bullets": [
                    "Comfort is the #1 driver (50-72%) across all segments. Functional excellence is the entry ticket.",
                    "Amazon dominates (59-64%) but DTC shows traction (16-33%). Consumers are open to buying direct.",
                    "88% would pay more for scrubs that deliver. Willingness exists — a clear brand reason is missing.",
                ],
                "insight": "Consumers will pay for proven performance — they just need a reason to believe.",
            },
        ],
    }

    # Add summary & next steps for full report
    result["summary_and_next_steps"] = {
        "capabilities_column": (
            f"{bn} is an execution-driven brand with competitive products and strong Amazon performance, "
            "now facing the need to clarify its naming and brand structure — including the role of its "
            "current brand name — to support long-term growth."
        ),
        "competition_column": (
            "The scrubs market is well-established, with leading brands succeeding by owning a clear and "
            "focused role — such as lifestyle identity, medical authority, durability, value, style, or "
            "comfort — rather than trying to compete across everything at once."
        ),
        "consumer_column": (
            "Endurance First professionals spend the most, set the highest performance standards, and define "
            "what quality means in scrubs — making them the most valuable and influential segment in the market."
        ),
        "closing_insight": (
            f"Building on these insights, we will define a clear and differentiated brand position for {bn} — "
            "one that resonates with its most demanding customers and scales credibly across the broader market."
        ),
    }

    return result
