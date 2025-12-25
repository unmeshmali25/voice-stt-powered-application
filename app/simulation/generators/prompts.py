"""
Prompt templates for LLM-based persona generation.

These templates guide the LLM to generate diverse, realistic personas
with consistent attributes across demographics, behavior, and shopping patterns.
"""

# Available product categories for retail simulation
AVAILABLE_CATEGORIES = [
    "Vitamins",
    "Supplements",
    "Skincare",
    "Beauty",
    "Haircare",
    "PersonalCare",
    "Household",
    "Groceries",
    "Snacks",
    "Beverages",
    "Healthcare",
    "Wellness",
    "Fitness",
    "Baby",
    "Pet",
    "Electronics",
]

# CVS Health Front Store Categories - pharmacy retail focused
CVS_CATEGORIES = [
    # Pharmacy/Health
    "Vitamins",
    "Supplements",
    "Medicine",
    "Healthcare",
    "Wellness",
    # Beauty/Personal Care
    "Skincare",
    "Beauty",
    "Haircare",
    "PersonalCare",
    "Cosmetics",
    # Household
    "Household",
    "Cleaning",
    "PaperProducts",
    # Groceries/Snacks
    "Groceries",
    "Snacks",
    "Beverages",
    # Seasonal
    "Seasonal",
    "Holiday",
]

# US regions for location diversity
US_REGIONS = [
    "Northeast",
    "Midwest",
    "South",
    "Southwest",
    "West",
    "Pacific Northwest",
]

# Base template for persona generation
PERSONA_GENERATION_PROMPT = """
You are generating a realistic retail shopping persona for a simulation system.

Generate a unique, detailed persona with the following JSON structure:

{{
  "agent_id": "{agent_id}",
  "backstory": "A 2-3 paragraph narrative about this person's life, shopping habits, and motivations. The backstory should explain WHY they have their specific preferences and behavioral traits.",
  "demographics": {{
    "age": 28,
    "age_group": "25-34",
    "gender": "female",
    "income_bracket": "medium",
    "household_size": 2,
    "has_children": false,
    "location_region": "Northeast"
  }},
  "behavioral_traits": {{
    "price_sensitivity": 0.65,
    "brand_loyalty": 0.40,
    "impulsivity": 0.55,
    "tech_savviness": 0.75
  }},
  "shopping_preferences": {{
    "preferred_categories": ["Beauty", "Skincare", "Vitamins"],
    "weekly_budget": 75.00,
    "shopping_frequency": "regular",
    "avg_cart_value": 45.00
  }},
  "temporal_patterns": {{
    "preferred_days": {{"weekday": 0.35, "saturday": 0.40, "sunday": 0.25}},
    "preferred_times": {{"morning": 0.20, "afternoon": 0.35, "evening": 0.45}}
  }},
  "coupon_behavior": {{
    "coupon_affinity": 0.70,
    "deal_seeking_behavior": "active_hunter"
  }},
  "sample_shopping_patterns": [
    "Browses skincare aisle for 15 minutes, compares 3-4 products before selecting",
    "Always checks for applicable coupons before checkout",
    "Prefers trying new products over established brands"
  ]
}}

REQUIREMENTS:

1. **Make each persona UNIQUE and REALISTIC**: Vary age, income, location, family status, and lifestyle.

2. **Ensure INTERNAL CONSISTENCY**:
   - age_group must match age (18-24, 25-34, 35-44, 45-54, 55-64, 65+)
   - Income should align with age and lifestyle
   - Household size should be realistic for the demographics
   - Behavioral traits should align with backstory

3. **Demographics**:
   - age: 18-80 (varied distribution)
   - gender: male, female, other, prefer_not_to_say
   - income_bracket: low, medium, high, affluent
   - household_size: 1-6 people
   - location_region: {us_regions}

4. **Behavioral traits (0.0 to 1.0)**:
   - price_sensitivity: How price-conscious (0=indifferent, 1=extremely_sensitive)
   - brand_loyalty: Brand attachment (0=switcher, 1=loyalist)
   - impulsivity: Impulse buying (0=planned_shopper, 1=very_impulsive)
   - tech_savviness: Tech comfort (0=traditional, 1=early_adopter)

5. **Shopping preferences**:
   - preferred_categories: 2-4 categories from: {categories}
   - weekly_budget: $20-$300 (realistic for the income_bracket)
   - shopping_frequency: frequent, regular, occasional, rare
   - avg_cart_value: $15-$150 (should align with budget and frequency)

6. **Temporal patterns** (probabilities that sum to ~1.0):
   - preferred_days: weekday, saturday, sunday (e.g., {{"weekday": 0.4, "saturday": 0.35, "sunday": 0.25}})
   - preferred_times: morning, afternoon, evening (e.g., {{"morning": 0.2, "afternoon": 0.4, "evening": 0.3}})

7. **Coupon behavior**:
   - coupon_affinity: 0.0-1.0 (likelihood to use coupons)
   - deal_seeking_behavior: passive, observer, active_hunter, extreme

8. **Sample shopping patterns**: 3-5 specific behaviors that reflect their quantitative traits

9. **Backstory**:
   - 2-3 paragraphs explaining life situation, shopping motivations, and preferences
   - Should account for WHY they have these specific behavioral scores
   - Make it feel like a real person with authentic motivations

Return ONLY valid JSON, no additional text.
""".replace(
    "{us_regions}", ", ".join(US_REGIONS)
).replace(
    "{categories}", ", ".join(AVAILABLE_CATEGORIES)
)

# Template for adding diversity guidance
PERSONA_GENERATION_WITH_DIVERSITY_PROMPT = """
{base_prompt}

DIVERSITY GUIDANCE FOR THIS PERSONA:
{diversity_notes}

Ensure this persona is distinctly different from others in these aspects.
"""

# Predefined diversity notes to ensure variety
DIVERSITY_NOTES = [
    "Create a young professional (age 22-28) in an urban area, focused on fitness and wellness.",
    "Create a parent (age 30-45) with children, budget-conscious and shopping for family needs.",
    "Create a retiree (age 60+) on fixed income, price-sensitive and loyal to familiar brands.",
    "Create a high-income professional (age 35-50), brand-loyal and time-constrained.",
    "Create a student or early-career (age 18-25) on tight budget, deal-seeking and experimental.",
    "Create a suburban parent (age 35-50) with high household income, bulk-shopping focus.",
    "Create a health-conscious individual (any age) focused on vitamins, supplements, and wellness.",
    "Create a beauty and skincare enthusiast (age 25-45), brand-loyal and impulsive.",
    "Create a pragmatic utilitarian (age 40-60), low impulsivity, focused on essentials.",
    "Create a tech-savvy early adopter (age 25-40), researches products online before buying.",
]

# CVS Health diversity notes - pharmacy retail focused with gender balance
CVS_DIVERSITY_NOTES = [
    "Create a MALE caregiver (age 30-55) shopping for aging parents, focused on medications and healthcare essentials.",
    "Create a FEMALE beauty enthusiast (age 25-45) who visits CVS for cosmetics, skincare, and personal care products.",
    "Create a MALE health-conscious senior (age 65+) managing daily medications and seeking vitamin supplements.",
    "Create a NON-BINARY busy parent (age 28-45) picking up prescriptions while grabbing household essentials and snacks.",
    "Create a FEMALE young professional (age 22-30) focused on wellness, vitamins, and quick grab-and-go items.",
    "Create a MALE coupon-savvy shopper (age 35-60) who visits CVS specifically for advertised deals and ExtraCare rewards.",
    "Create a MALE student (age 18-25) buying snacks, personal care items, and occasional health supplements.",
    "Create a FEMALE seasonal shopper (age 30-50) who visits CVS for holiday items, gifts, and seasonal health needs (flu shots, etc.).",
    "Create a MALE brand-loyal customer (age 40-65) who consistently buys the same personal care and medication brands.",
    "Create a FEMALE convenience-focused shopper (age 25-45) making quick trips for immediate needs versus planned shopping.",
]

# CVS Health-specific prompt template
CVS_PERSONA_GENERATION_PROMPT = """
You are generating a realistic retail shopping persona for a CVS Health Pharmacy Retail Front Store simulation.

CVS Health Context:
- This is a pharmacy retail front store (NOT a full grocery store)
- Primary focus: Health, wellness, beauty, personal care, household essentials
- Customers range from quick pharmacy pick-ups to full shopping trips
- Many customers are picking up prescriptions and shopping while waiting
- Key shopper types: Caregivers, health-conscious individuals, beauty enthusiasts, seniors, convenience shoppers

Generate a unique, detailed persona with the following JSON structure:

{{
  "agent_id": "{agent_id}",
  "backstory": "A 2-3 paragraph narrative about this person's life, shopping habits, and motivations. The backstory should explain WHY they have their specific preferences and behavioral traits, including their relationship with CVS Health as their pharmacy/retail destination.",
  "demographics": {{
    "age": 28,
    "age_group": "25-34",
    "gender": "male",
    "income_bracket": "medium",
    "household_size": 2,
    "has_children": false,
    "location_region": "Northeast"
  }},
  "behavioral_traits": {{
    "price_sensitivity": 0.65,
    "brand_loyalty": 0.40,
    "impulsivity": 0.55,
    "tech_savviness": 0.75
  }},
  "shopping_preferences": {{
    "preferred_categories": ["Vitamins", "Medicine", "Healthcare"],
    "weekly_budget": 50.00,
    "shopping_frequency": "regular",
    "avg_cart_value": 35.00
  }},
  "temporal_patterns": {{
    "preferred_days": {{"weekday": 0.35, "saturday": 0.40, "sunday": 0.25}},
    "preferred_times": {{"morning": 0.20, "afternoon": 0.35, "evening": 0.45}}
  }},
  "coupon_behavior": {{
    "coupon_affinity": 0.70,
    "deal_seeking_behavior": "active_hunter"
  }},
  "sample_shopping_patterns": [
    "Visits CVS after work to pick up prescription and browses beauty aisle while waiting",
    "Uses CVS app to clip ExtraCare coupons before shopping trip",
    "Stocks up on favorite skincare brands during BOGO sales"
  ]
}}

REQUIREMENTS:

1. **Focus on CVS Health Product Categories**: Choose from: {categories}
   - Prioritize: Vitamins, Supplements, Medicine, Healthcare, Skincare, Beauty, PersonalCare
   - Include: Household essentials (Cleaning, PaperProducts)
   - Limited: Groceries, Snacks, Beverages (not full grocery shopping)

2. **CVS Shopping Behaviors**:
   - Consider pharmacy-related patterns (waiting for prescriptions, consulting pharmacist)
   - Include ExtraCare coupon/rewards behavior where relevant
   - Think about quick trips vs. planned shopping trips
   - Consider seasonal health needs (flu shots, allergy meds, etc.)

3. **Internal Consistency**:
   - age_group must match age (18-24, 25-34, 35-44, 45-54, 55-64, 65+)
   - Income should align with age and lifestyle
   - Household size should be realistic for the demographics
   - Behavioral traits should align with backstory

4. **Demographics**:
   - age: 18-80 (varied distribution, include more seniors for CVS context)
   - gender: male, female, other, prefer_not_to_say
   - income_bracket: low, medium, high, affluent
   - household_size: 1-6 people
   - location_region: {us_regions}

5. **Gender Balance**:
   - IMPORTANT: Aim for DIVERSE gender representation across personas
   - Do NOT default to "female" for beauty, caregiving, or household shopping
   - Include MALE personas interested in skincare, grooming, and health
   - Include NON-BINARY personas across all categories
   - Vary gender intentionally: male, female, and non-binary should all be represented
   - Break stereotypes: male caregivers, female tech shoppers, non-binary health enthusiasts

6. **Behavioral traits (0.0 to 1.0)**:
   - price_sensitivity: How price-conscious (0=indifferent, 1=extremely_sensitive)
   - brand_loyalty: Brand attachment (0=switcher, 1=loyalist)
   - impulsivity: Impulse buying (0=planned_shopper, 1=very_impulsive)
   - tech_savviness: Tech comfort (0=traditional, 1=early_adopter)

6. **Shopping preferences**:
   - preferred_categories: 2-4 categories from CVS Health categories
   - weekly_budget: $10-$100 (BIAS toward lower end: most personas should be $20-$50)
   - shopping_frequency: frequent, regular, occasional, rare
   - avg_cart_value: $8-$50 (smaller basket sizes for quick trips, most under $35)

7. **Temporal patterns** (probabilities that sum to ~1.0):
   - preferred_days: weekday, saturday, sunday (e.g., {{"weekday": 0.4, "saturday": 0.35, "sunday": 0.25}})
   - preferred_times: morning, afternoon, evening (e.g., {{"morning": 0.2, "afternoon": 0.4, "evening": 0.3}})

8. **Coupon behavior**:
   - coupon_affinity: 0.0-1.0 (likelihood to use coupons/ExtraCare rewards)
   - deal_seeking_behavior: passive, observer, active_hunter, extreme

9. **Sample shopping patterns**: 3-5 specific behaviors that reflect:
   - Pharmacy/health shopping patterns
   - CVS-specific behaviors (app usage, ExtraCare, prescriptions)
   - Quick trip vs. planned shopping patterns

10. **Backstory**:
    - 2-3 paragraphs explaining life situation, shopping motivations, and preferences
    - Should account for WHY they have these specific behavioral scores
    - Include their relationship with CVS Health as their pharmacy/retail destination
    - Make it feel like a real person with authentic motivations

Return ONLY valid JSON, no additional text.
""".replace(
    "{us_regions}", ", ".join(US_REGIONS)
).replace(
    "{categories}", ", ".join(CVS_CATEGORIES)
)

# CVS template with diversity guidance
CVS_PERSONA_GENERATION_WITH_DIVERSITY_PROMPT = """
{base_prompt}

CVS DIVERSITY GUIDANCE FOR THIS PERSONA:
{diversity_notes}

Ensure this persona is distinctly different from others in these aspects.
"""


def get_persona_prompt(agent_id: str, diversity_index: int = None, use_cvs_context: bool = True) -> str:
    """
    Get the persona generation prompt for a specific agent.

    Args:
        agent_id: The agent identifier (e.g., "agent_001")
        diversity_index: Optional index to select diversity notes (0-9)
        use_cvs_context: Whether to use CVS Health-specific prompts (default: True)

    Returns:
        The formatted prompt string
    """
    # Choose template based on context
    if use_cvs_context:
        base_prompt = CVS_PERSONA_GENERATION_PROMPT
        diversity_notes = CVS_DIVERSITY_NOTES
        with_diversity_prompt = CVS_PERSONA_GENERATION_WITH_DIVERSITY_PROMPT
    else:
        base_prompt = PERSONA_GENERATION_PROMPT
        diversity_notes = DIVERSITY_NOTES
        with_diversity_prompt = PERSONA_GENERATION_WITH_DIVERSITY_PROMPT

    # Replace agent_id in base prompt
    prompt_with_agent = base_prompt.replace("{agent_id}", agent_id)

    # Add diversity notes if requested
    if diversity_index is not None and 0 <= diversity_index < len(diversity_notes):
        diversity_note = diversity_notes[diversity_index]
        return with_diversity_prompt.format(
            base_prompt=prompt_with_agent,
            diversity_notes=diversity_note,
        )
    else:
        return prompt_with_agent


# Category affinity prompt for specific use cases
CATEGORY_AFFINITY_PROMPT = """
Based on the following persona demographics and behavioral traits, suggest their
top 3 product categories from this list: {categories}

Persona:
- Age: {age}
- Gender: {gender}
- Income: {income}
- Has children: {has_children}
- Price sensitivity: {price_sensitivity}
- Brand loyalty: {brand_loyalty}
- Impulsivity: {impulsivity}

Return only a JSON array of category names.
"""


def validate_prompt_includes_categories() -> None:
    """Validate that all referenced categories exist in AVAILABLE_CATEGORIES."""
    # This is a placeholder for future validation
    pass
