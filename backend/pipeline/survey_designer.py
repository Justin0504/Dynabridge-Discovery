"""Survey/Questionnaire design module.

Generates a customized consumer survey questionnaire for a brand,
based on DynaBridge's standard Discovery methodology learned from
8 real client deliverables (CozyFit, AEKE, EcoBags, Glacier Fresh,
GOATClean, Mama Land, RSLove, Yoofoss).

Standard survey structure:
  Section 1: Screener & Demographics (5-8 questions)
  Section 2: Category Usage & Shopping Habits (5-7 questions)
  Section 3: Purchase Drivers & Barriers (3-5 questions)
  Section 4: Brand Evaluation (4-6 questions)
  Section 5: Lifestyle & Psychographics (3-5 questions)
  Section 6: Open-ended (2-3 questions)

Total: 22-34 questions, targeting 10-15 minute completion.
"""
import json
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY

client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SURVEY_SYSTEM = """You are a quantitative market research expert at DynaBridge, a brand consulting firm.

You design consumer surveys for brand discovery projects. Your surveys follow a proven structure
used across dozens of real engagements for Chinese brands entering Western markets.

## Survey Design Principles
- 10-15 minutes total, 22-30 questions
- Unbranded survey (don't reveal which brand commissioned it)
- Online panel format (Prolific, MTurk, or similar)
- Mix of question types: single-select, multi-select, Likert scale, open-ended
- Every question must serve the analysis: demographics for cross-tabs, behavior for segmentation,
  attitudes for positioning, brand metrics for competitive benchmarking

## Standard Sections (from real DynaBridge projects)

### Section 1: Screener & Demographics
Purpose: Qualify respondents and enable cross-tabulation
Standard questions:
- Age/year of birth (single-select, generational brackets)
- Gender (single-select)
- Race/ethnicity (multi-select)
- Household income (single-select, brackets)
- Geographic region (single-select)
- Category-specific screener (e.g., "Do you purchase [category] at least once per year?")

### Section 2: Category Usage & Shopping Habits
Purpose: Understand current behavior for segmentation
Standard questions:
- Purchase frequency ("In the past 12 months, how often have you purchased [category]?")
- Spend amount ("Approximately how much have you spent on [category] in the past 12 months?")
- Purchase channels ("Where have you purchased [category]?" — multi-select)
- Occasion/usage ("When/why do you typically use [category]?" — multi-select)
- Social media usage ("Which social media platforms do you frequently use?" — multi-select)

### Section 3: Purchase Drivers & Barriers
Purpose: Identify what matters most and what creates friction
Standard questions:
- Top purchase factors ("Which factors are MOST important when buying [category]?" — select top 3-5)
- Driver deep-dive ("You said [factor] is important. Which specific aspects matter most?" — multi-select)
- Pre-purchase activities ("Which steps do you typically take before buying [category]?" — multi-select)
- Challenges/pain points ("What challenges or issues have you experienced?" — open-ended + multi-select)
- Premium definition ("When it comes to [category], what does 'premium' mean to you?" — multi-select)

### Section 4: Brand Evaluation
Purpose: Map competitive landscape from consumer perspective
Standard questions:
- Aided brand awareness ("Which of these [category] brands have you heard of?" — multi-select)
- Brand purchase ("Which have you purchased in the past 12 months?" — multi-select)
- Brand satisfaction ("How satisfied were you?" — Likert per brand)
- Brand recommendation ("How likely to recommend?" — NPS scale per brand)
- Favorite brand ("Which is your favorite, regardless of price?" — single-select)
- Brand association matrix ("Which brand best fits each description?" — grid)

### Section 5: Lifestyle & Psychographics
Purpose: Enable rich segment profiles
Standard questions:
- Style/identity ("Which best describes your personal style?" — single-select)
- Values ("Which values are most important to you?" — select top 3)
- Information sources ("Where do you get recommendations for [category]?" — multi-select)
- Music genre preference (single-select)
- Car brand that captures your style (single-select)

### Section 6: Open-ended
Purpose: Capture verbatim insights for quotes
Standard questions:
- Category wish ("If you could change ONE thing about [category], what would it be?")
- Brand perception ("What comes to mind when you think of [brand]?" — for top brands)
- General feedback ("Is there anything else you'd like to share about your experience?")
"""

SURVEY_PROMPT = """Design a complete consumer survey questionnaire for this brand discovery project.

Brand: {brand_name}
Category: {category}
Brand URL: {brand_url}
Competitors: {competitors}
Language: {language}

Based on our findings so far:
{context}

Generate a survey with 22-30 questions following DynaBridge's standard methodology.

## IMPORTANT: Category-Specific Customization Rules
- Adapt "premium" definition options to the category (e.g., "fabric tech" for apparel, "filtration performance" for water filters, "ingredient safety" for baby products)
- Include 8-12 competitor brands in the aided awareness question (include {brand_name} + major competitors)
- Brand association matrix should use 6-8 attributes relevant to the category
- Lifestyle questions (music, car brand, personal style) are ALWAYS included — they're used for segment profiling, not category analysis
- The purchase driver options should match real category concerns (check the analysis context for themes)
- Include at least one "willingness to pay" or "price sensitivity" question
- Screener must verify the respondent actually purchases in this category

## Cross-Tabulation Plan (MUST include these variables)
Every survey must enable these standard cross-tabs:
- Segment (derived from clustering purchase drivers + lifestyle)
- Generation (Gen Z / Millennial / Gen X / Boomer)
- Gender
- Income bracket
- Purchase frequency (heavy / medium / light buyer)

Return ONLY a JSON object:
{{
  "survey_title": "Consumer [Category] Survey",
  "estimated_duration": "12 minutes",
  "target_sample_size": 200,
  "target_audience": "Description of who should take this survey",
  "screener_criteria": ["Criterion 1", "Criterion 2"],
  "sections": [
    {{
      "name": "Section Name",
      "purpose": "Why this section exists",
      "questions": [
        {{
          "id": "Q1",
          "text": "Full question text",
          "type": "single_select|multi_select|likert|open_ended|grid|ranking|numeric",
          "required": true,
          "options": ["Option 1", "Option 2", "Option 3"],
          "max_select": 3,
          "logic": "Optional skip/display logic",
          "analysis_use": "How this data will be used in the analysis"
        }}
      ]
    }}
  ],
  "cross_tab_variables": ["Q1 - Age", "Q2 - Gender", "Q4 - Income", "Q5 - Purchase Frequency", "Segment"],
  "segmentation_variables": ["Q5 - Purchase frequency", "Q6 - Spend", "Q9 - Top drivers", "Q17 - Style identity"],
  "notes": "Any additional survey design notes"
}}
"""


async def design_survey(
    brand_name: str,
    brand_url: str = "",
    competitors: list[str] = None,
    category: str = "",
    language: str = "en",
    analysis_context: str = "",
) -> dict:
    """Generate a customized survey questionnaire for a brand.

    Args:
        brand_name: Brand name
        brand_url: Brand website URL
        competitors: List of competitor names
        category: Product category (auto-detected if empty)
        language: "en" or "zh" or "en+zh"
        analysis_context: Summary of Phase 1-2 findings to inform questions

    Returns:
        Survey design as structured JSON
    """
    if not client:
        return _fallback_survey(brand_name, category, competitors or [])

    prompt = SURVEY_PROMPT.format(
        brand_name=brand_name,
        category=category or "consumer products",
        brand_url=brand_url,
        competitors=", ".join(competitors or []),
        language=language,
        context=analysis_context[:3000] if analysis_context else "No prior analysis available.",
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=SURVEY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass

    return _fallback_survey(brand_name, category, competitors or [])


def _fallback_survey(brand_name: str, category: str, competitors: list[str]) -> dict:
    """Generate a basic template survey when API is unavailable."""
    cat = category or "products"
    brands = [brand_name] + competitors[:5]

    return {
        "survey_title": f"Consumer {cat.title()} Survey",
        "estimated_duration": "12 minutes",
        "target_sample_size": 200,
        "target_audience": f"US adults who have purchased {cat} in the past 12 months",
        "screener_criteria": [
            f"Must have purchased {cat} in the past 12 months",
            "Must be 18+ years old",
            "Must reside in the United States",
        ],
        "sections": [
            {
                "name": "Demographics & Background",
                "purpose": "Respondent qualification and cross-tabulation",
                "questions": [
                    {"id": "Q1", "text": "What year were you born?", "type": "single_select",
                     "options": ["1997-2008 (Gen Z)", "1981-1996 (Millennial)", "1965-1980 (Gen X)", "1946-1964 (Boomer)", "Before 1946"],
                     "analysis_use": "Generation cross-tab"},
                    {"id": "Q2", "text": "What is your gender?", "type": "single_select",
                     "options": ["Male", "Female", "Non-binary", "Prefer not to say"],
                     "analysis_use": "Gender cross-tab"},
                    {"id": "Q3", "text": "Which best describes your race/ethnicity? (Select all that apply)", "type": "multi_select",
                     "options": ["White/Caucasian", "Black/African American", "Hispanic/Latino", "Asian/Pacific Islander", "Other"],
                     "analysis_use": "Ethnicity cross-tab"},
                    {"id": "Q4", "text": "What is your annual household income?", "type": "single_select",
                     "options": ["Under $25,000", "$25,000-$49,999", "$50,000-$74,999", "$75,000-$99,999", "$100,000-$149,999", "$150,000+"],
                     "analysis_use": "Income cross-tab"},
                ],
            },
            {
                "name": "Shopping Habits & Usage",
                "purpose": "Understand purchase behavior for segmentation",
                "questions": [
                    {"id": "Q5", "text": f"In the past 12 months, how often have you purchased {cat}?", "type": "single_select",
                     "options": ["Monthly or more", "Every 2-3 months", "2-3 times per year", "Once per year", "Less than once per year"],
                     "analysis_use": "Segmentation variable"},
                    {"id": "Q6", "text": f"Approximately how much have you spent on {cat} in the past 12 months?", "type": "single_select",
                     "options": ["Under $50", "$50-$99", "$100-$199", "$200-$499", "$500+"],
                     "analysis_use": "Spend segmentation"},
                    {"id": "Q7", "text": f"Where have you purchased {cat}? (Select all that apply)", "type": "multi_select",
                     "options": ["Amazon", "Brand website (DTC)", "Walmart", "Target", "Specialty stores", "Other online retailers"],
                     "analysis_use": "Channel analysis"},
                    {"id": "Q8", "text": "Which social media platforms do you frequently use? (Select all that apply)", "type": "multi_select",
                     "options": ["Instagram", "TikTok", "YouTube", "Facebook", "Pinterest", "X/Twitter", "Reddit"],
                     "analysis_use": "Lifestyle profiling"},
                ],
            },
            {
                "name": "Purchase Drivers & Barriers",
                "purpose": "Identify what drives purchase decisions",
                "questions": [
                    {"id": "Q9", "text": f"Which factors are MOST important when buying {cat}? (Select your top 3)", "type": "multi_select",
                     "max_select": 3,
                     "options": ["Quality/durability", "Price/value", "Comfort/fit", "Style/design", "Brand reputation", "Reviews/ratings", "Sustainability", "Innovation"],
                     "analysis_use": "Purchase driver ranking"},
                    {"id": "Q10", "text": f"What challenges or issues have you experienced when shopping for {cat}?", "type": "open_ended",
                     "analysis_use": "Pain point verbatims"},
                    {"id": "Q11", "text": f"Which steps do you typically take before buying {cat}? (Select all that apply)", "type": "multi_select",
                     "options": ["Read online reviews", "Compare prices", "Visit brand website", "Ask friends/family", "Watch YouTube reviews", "Try in store", "Check social media"],
                     "analysis_use": "Pre-purchase journey"},
                    {"id": "Q12", "text": f"When it comes to {cat}, what does 'premium' mean to you? (Select all that apply)", "type": "multi_select",
                     "options": ["Superior materials", "Better design", "Longer lasting", "Better fit", "Brand prestige", "Ethical/sustainable", "Innovation"],
                     "analysis_use": "Premium perception"},
                ],
            },
            {
                "name": "Brand Evaluation",
                "purpose": "Map competitive brand landscape",
                "questions": [
                    {"id": "Q13", "text": f"Which of these {cat} brands have you heard of? (Select all that apply)", "type": "multi_select",
                     "options": brands + ["None of these"],
                     "analysis_use": "Aided awareness"},
                    {"id": "Q14", "text": "Which have you purchased in the past 12 months? (Select all that apply)", "type": "multi_select",
                     "options": brands + ["None of these"],
                     "analysis_use": "Purchase incidence"},
                    {"id": "Q15", "text": "Which is your favorite, regardless of price?", "type": "single_select",
                     "options": brands + ["No favorite"],
                     "analysis_use": "Brand preference / favorite brand donut"},
                    {"id": "Q16", "text": "Which brand best fits each description?", "type": "grid",
                     "options": brands,
                     "rows": ["Best quality", "Best value", "Most innovative", "Most trustworthy", "Most stylish", "Would recommend"],
                     "analysis_use": "Brand association matrix"},
                    {"id": "Q17", "text": f"How likely are you to try a new brand for {cat}?", "type": "single_select",
                     "options": ["Very likely", "Somewhat likely", "Neutral", "Somewhat unlikely", "Very unlikely"],
                     "analysis_use": "Brand switching propensity"},
                ],
            },
            {
                "name": "Willingness to Pay",
                "purpose": "Understand price sensitivity and premium willingness",
                "questions": [
                    {"id": "Q18", "text": f"Please indicate how much you agree: 'I am willing to pay more for {cat} if they clearly deliver on what matters to me.'", "type": "likert",
                     "options": ["Strongly agree", "Somewhat agree", "Neutral", "Somewhat disagree", "Strongly disagree"],
                     "analysis_use": "Premium willingness by segment"},
                    {"id": "Q19", "text": f"What price range would you consider appropriate for a high-quality {cat.rstrip('s')}?", "type": "single_select",
                     "options": ["Under $25", "$25-$49", "$50-$99", "$100-$199", "$200+"],
                     "analysis_use": "Price range expectation"},
                ],
            },
            {
                "name": "Lifestyle & Values",
                "purpose": "Build rich segment profiles",
                "questions": [
                    {"id": "Q20", "text": "Which best describes your personal style?", "type": "single_select",
                     "options": ["Classic & timeless", "Trendy & fashion-forward", "Practical & functional", "Athletic & active", "Minimalist"],
                     "analysis_use": "Lifestyle segmentation"},
                    {"id": "Q21", "text": "Which are your favorite music genres? (Select up to 3)", "type": "multi_select",
                     "max_select": 3,
                     "options": ["Pop", "R&B/Soul", "Hip-Hop/Rap", "Rock", "Country", "Electronic/EDM", "Classical", "Latin"],
                     "analysis_use": "Lifestyle profiling"},
                    {"id": "Q22", "text": "Which of these car brands best captures your personal style?", "type": "single_select",
                     "options": ["Toyota", "Honda", "BMW", "Mercedes-Benz", "Tesla", "Jeep", "Subaru", "Other"],
                     "analysis_use": "Lifestyle profiling"},
                ],
            },
            {
                "name": "Open-ended Feedback",
                "purpose": "Capture verbatim insights for quotes",
                "questions": [
                    {"id": "Q23", "text": f"If you could change ONE thing about {cat} available today, what would it be?", "type": "open_ended",
                     "analysis_use": "Unmet needs"},
                    {"id": "Q24", "text": "Is there anything else you'd like to share about your experience?", "type": "open_ended",
                     "analysis_use": "General verbatims"},
                ],
            },
        ],
        "cross_tab_variables": ["Q1 - Generation", "Q2 - Gender", "Q4 - Income", "Segment"],
        "segmentation_variables": ["Q5 - Purchase frequency", "Q6 - Spend amount", "Q9 - Top drivers", "Q17 - Style identity"],
        "notes": f"Survey designed for {brand_name} brand discovery. Unbranded format.",
    }
