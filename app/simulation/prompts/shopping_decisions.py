"""
Prompt templates for LLM shopping decisions.

Optimized for qwen3:4b with concise context and clear JSON output schemas.
Each prompt includes few-shot examples for different shopping personas.
"""

# JSON output schema for shopping decisions
SHOP_DECISION_SCHEMA = """
{
  "decision": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "urgency": 0.0-1.0
}
"""

# JSON output schema for checkout decisions
CHECKOUT_DECISION_SCHEMA = """
{
  "decision": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "urgency": 0.0-1.0
}
"""

# Shop decision prompt template
SHOP_DECISION_PROMPT = """You are a shopping behavior simulator. Decide if this agent should shop today based on their profile and context.

AGENT PROFILE:
- Shopping Frequency: {shopping_frequency}
- Impulsivity: {impulsivity}/1.0
- Price Sensitivity: {price_sensitivity}/1.0
- Coupon Affinity: {coupon_affinity}/1.0
- Preferred Categories: {preferred_categories}
- Preferred Shopping Days: {pref_days}
- Weekly Budget: ${weekly_budget}
- Average Cart Value: ${avg_cart_value}

CURRENT CONTEXT:
- Date: {current_date} ({current_day_of_week})
- Active Events: {active_events}
- Days Since Last Shop: {days_since_last_shop}
- Recent Orders: {recent_orders}
- Monthly Spend So Far: ${monthly_spend}

DECISION FACTORS:
- Consider shopping frequency and days since last shop
- Factor in preferred shopping days vs current day
- Account for active seasonal events (e.g., Black Friday increases likelihood)
- Respect budget constraints (high monthly spend = less likely)
- Higher impulsivity = more spontaneous shopping

EXAMPLES:

Example 1 (Frequent Shopper + Weekend):
Agent: frequent, impulsivity 0.7, pref_days: Saturday, today: Saturday, events: none
Decision: {{
  "decision": true,
  "confidence": 0.85,
  "reasoning": "Frequent shopper on preferred day with high impulsivity",
  "urgency": 0.4
}}

Example 2 (Budget Conscious + High Monthly Spend):
Agent: occasional, price_sensitivity 0.8, monthly_spend: $380, weekly_budget: $100
Decision: {{
  "decision": false,
  "confidence": 0.75,
  "reasoning": "Already near monthly budget limit, price sensitive",
  "urgency": 0.1
}}

Example 3 (Black Friday Event):
Agent: regular, coupon_affinity 0.9, events: Black Friday
Decision: {{
  "decision": true,
  "confidence": 0.90,
  "reasoning": "Deal hunter motivated by major sales event",
  "urgency": 0.8
}}

YOUR DECISION (respond ONLY with JSON):
{json_schema}
""".format(
    persona_name="{persona_name}",
    shopping_frequency="{shopping_frequency}",
    impulsivity="{impulsivity}",
    price_sensitivity="{price_sensitivity}",
    budget_sensitivity="{budget_sensitivity}",
    coupon_affinity="{coupon_affinity}",
    preferred_categories="{preferred_categories}",
    pref_days="{pref_days}",
    weekly_budget="{weekly_budget}",
    avg_cart_value="{avg_cart_value}",
    current_date="{current_date}",
    current_day_of_week="{current_day_of_week}",
    active_events="{active_events}",
    days_since_last_shop="{days_since_last_shop}",
    recent_orders="{recent_orders}",
    monthly_spend="{monthly_spend}",
    json_schema=SHOP_DECISION_SCHEMA,
)

# Checkout decision prompt template
CHECKOUT_DECISION_PROMPT = """You are a shopping behavior simulator. Decide if this agent should complete their purchase or abandon the cart.

AGENT PROFILE:
- Impulsivity: {impulsivity}/1.0
- Price Sensitivity: {price_sensitivity}/1.0
- Brand Loyalty: {brand_loyalty}/1.0

CART CONTEXT:
- Items in Cart: {cart_items}
- Cart Total: {cart_total}
- Products Viewed Before Cart: {items_viewed}
- Coupons Available: {coupons_available}
- Weekly Budget: {weekly_budget}
- Monthly Spend So Far: {monthly_spend}
- Budget Status: {budget_status}

DECISION FACTORS:
- Higher cart total relative to budget = more hesitation
- High impulsivity = more likely to complete
- High price sensitivity = more likely to abandon if expensive
- Brand loyalty increases completion likelihood
- Many items viewed = deliberate shopper, likely to complete

EXAMPLES:

Example 1 (Impulsive + Small Cart):
Agent: impulsivity 0.8, cart: 2 items $35, budget: $100
Decision: {{
  "decision": true,
  "confidence": 0.85,
  "reasoning": "Impulsive buyer with affordable cart well under budget",
  "urgency": 0.6
}}

Example 2 (Price Sensitive + Large Cart):
Agent: price_sensitivity 0.9, cart: 8 items $145, budget: $100, status: approaching limit
Decision: {{
  "decision": false,
  "confidence": 0.70,
  "reasoning": "Price sensitive buyer exceeded budget comfort zone",
  "urgency": 0.2
}}

Example 3 (High Brand Loyalty):
Agent: brand_loyalty 0.8, cart: 3 items $78, viewed: 12 products
Decision: {{
  "decision": true,
  "confidence": 0.80,
  "reasoning": "Loyal customer who researched thoroughly before adding to cart",
  "urgency": 0.5
}}

YOUR DECISION (respond ONLY with JSON):
{json_schema}
""".format(
    persona_name="{persona_name}",
    impulsivity="{impulsivity}",
    price_sensitivity="{price_sensitivity}",
    budget_sensitivity="{budget_sensitivity}",
    brand_loyalty="{brand_loyalty}",
    cart_items="{cart_items}",
    cart_total="{cart_total}",
    items_viewed="{items_viewed}",
    coupons_available="{coupons_available}",
    weekly_budget="{weekly_budget}",
    monthly_spend="{monthly_spend}",
    budget_status="{budget_status}",
    json_schema=CHECKOUT_DECISION_SCHEMA,
)

# Template for few-shot examples by persona type
PERSONA_EXAMPLES = {
    "impulsive_shopper": {
        "shop": {
            "context": "Frequent shopper, high impulsivity (0.8), sees promotion",
            "decision": True,
            "reasoning": "Impulsive nature + promotional trigger = likely to shop",
        },
        "checkout": {
            "context": "Small cart, under budget",
            "decision": True,
            "reasoning": "Low friction purchase matches impulsive style",
        },
    },
    "careful_planner": {
        "shop": {
            "context": "Occasional shopper, low impulsivity (0.2), compares prices",
            "decision": False,
            "reasoning": "Planner needs more time to research before shopping",
        },
        "checkout": {
            "context": "Large cart, researched 15+ items",
            "decision": True,
            "reasoning": "Thorough research indicates purchase intent",
        },
    },
    "deal_hunter": {
        "shop": {
            "context": "High coupon affinity (0.9), Black Friday event",
            "decision": True,
            "reasoning": "Sales event is primary motivator for deal hunter",
        },
        "checkout": {
            "context": "Coupons applied, good savings",
            "decision": True,
            "reasoning": "Deal achieved, time-sensitive to complete",
        },
    },
    "budget_conscious": {
        "shop": {
            "context": "High price sensitivity (0.9), near monthly limit",
            "decision": False,
            "reasoning": "Budget constraints override shopping desire",
        },
        "checkout": {
            "context": "Cart exceeds weekly budget",
            "decision": False,
            "reasoning": "Budget exceeded, will likely abandon and wait",
        },
    },
}


def get_persona_example(persona_type: str, decision_type: str) -> dict:
    """
    Get example decision for a specific persona type.

    Args:
        persona_type: Type of persona (impulsive_shopper, careful_planner, etc.)
        decision_type: "shop" or "checkout"

    Returns:
        Example dict with context and expected decision
    """
    persona = PERSONA_EXAMPLES.get(persona_type, {})
    return persona.get(decision_type, {})


def format_decision_prompt(
    decision_type: str,
    context: dict,
    include_examples: bool = True,
) -> str:
    """
    Format a decision prompt with context.

    Args:
        decision_type: "shop" or "checkout"
        context: Context dictionary with agent data
        include_examples: Whether to include few-shot examples

    Returns:
        Formatted prompt string
    """
    if decision_type == "shop":
        template = SHOP_DECISION_PROMPT
    elif decision_type == "checkout":
        template = CHECKOUT_DECISION_PROMPT
    else:
        raise ValueError(f"Unknown decision type: {decision_type}")

    # Format the template with context
    prompt = template.format(**context)

    return prompt
