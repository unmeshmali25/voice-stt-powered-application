"""
Agent state schema for LangGraph shopping simulation.

This TypedDict defines the state that flows through the shopping graph,
containing agent identity, persona attributes, session state, and outcomes.
"""

from typing import TypedDict, List, Optional, Literal, Any
from datetime import date, datetime


class AgentState(TypedDict, total=False):
    """
    State schema for shopping agent graph.

    All fields marked total=False to allow partial state updates.
    """

    # --- Agent Identity ---
    agent_id: str
    user_id: str

    # --- Persona Attributes (read from database) ---
    shopping_frequency: str  # 'frequent', 'regular', 'occasional', 'rare'
    impulsivity: float  # 0.0-1.0
    price_sensitivity: float  # 0.0-1.0
    coupon_affinity: float  # 0.0-1.0
    preferred_categories: List[str]
    pref_day_weekday: float  # 0.0-1.0
    pref_day_saturday: float  # 0.0-1.0
    pref_day_sunday: float  # 0.0-1.0
    pref_time_morning: float  # 0.0-1.0
    pref_time_afternoon: float  # 0.0-1.0
    pref_time_evening: float  # 0.0-1.0
    weekly_budget: float
    avg_cart_value: float
    brand_loyalty: float  # 0.0-1.0
    deal_seeking_behavior: str  # 'passive', 'observer', 'active_hunter', 'extreme'

    # --- Simulation Context ---
    simulated_date: date
    simulated_timestamp: datetime
    store_id: str

    # --- Session State (updated during graph execution) ---
    session_id: Optional[str]
    products_viewed: List[str]  # Product IDs
    products_data: List[dict]  # Full product data from browse step
    cart_items: List[dict]  # [{"product_id": str, "quantity": int, "price": float}]
    cart_total: float
    coupons_available: List[dict]  # [{"id": str, "type": str, "discount": str}]
    coupons_applied: List[str]  # Coupon IDs

    # --- Decision Outcomes ---
    should_shop: bool
    checkout_decision: Literal["complete", "abandon", "pending"]
    order_id: Optional[str]

    # --- Tracking Metrics ---
    events_created: int
    errors: List[str]

    # --- Database Session (injected at runtime) ---
    db: Any  # SQLAlchemy Session - not serializable, injected per-run


def create_initial_state(
    agent: dict, simulated_date: date, store_id: str, db: Any
) -> AgentState:
    """
    Create initial AgentState from database agent record.

    Args:
        agent: Dictionary from agents table
        simulated_date: Current simulated date
        store_id: Store ID for this shopping session
        db: SQLAlchemy Session

    Returns:
        AgentState ready for graph execution
    """
    # Parse preferred_categories - could be string or list
    preferred_categories = agent.get("preferred_categories", [])
    if isinstance(preferred_categories, str):
        preferred_categories = [
            c.strip() for c in preferred_categories.split(",") if c.strip()
        ]

    return AgentState(
        # Identity
        agent_id=str(agent.get("agent_id", "")),
        user_id=str(agent.get("user_id", "")),
        # Persona attributes
        shopping_frequency=agent.get("shopping_frequency", "regular"),
        impulsivity=float(agent.get("impulsivity", 0.5)),
        price_sensitivity=float(agent.get("price_sensitivity", 0.5)),
        coupon_affinity=float(agent.get("coupon_affinity", 0.5)),
        preferred_categories=preferred_categories,
        pref_day_weekday=float(agent.get("pref_day_weekday", 0.5)),
        pref_day_saturday=float(agent.get("pref_day_saturday", 0.5)),
        pref_day_sunday=float(agent.get("pref_day_sunday", 0.5)),
        pref_time_morning=float(agent.get("pref_time_morning", 0.33)),
        pref_time_afternoon=float(agent.get("pref_time_afternoon", 0.33)),
        pref_time_evening=float(agent.get("pref_time_evening", 0.33)),
        weekly_budget=float(agent.get("weekly_budget", 100.0)),
        avg_cart_value=float(agent.get("avg_cart_value", 30.0)),
        brand_loyalty=float(agent.get("brand_loyalty", 0.5)),
        deal_seeking_behavior=agent.get("deal_seeking_behavior", "observer"),
        # Simulation context
        simulated_date=simulated_date,
        simulated_timestamp=datetime.combine(simulated_date, datetime.now().time()),
        store_id=store_id,
        # Session state (empty initially)
        session_id=None,
        products_viewed=[],
        products_data=[],
        cart_items=[],
        cart_total=0.0,
        coupons_available=[],
        coupons_applied=[],
        # Decision outcomes (pending initially)
        should_shop=False,
        checkout_decision="pending",
        order_id=None,
        # Tracking
        events_created=0,
        errors=[],
        # Database session
        db=db,
    )
