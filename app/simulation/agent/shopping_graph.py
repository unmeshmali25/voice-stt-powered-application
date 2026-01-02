"""
LangGraph StateGraph for shopping agent simulation.

This module defines the shopping workflow as a graph:
1. decide_shop - Should agent shop today?
2. browse_products - View products based on preferences
3. add_to_cart - Add items based on impulsivity
4. view_coupons - Check available coupons
5. decide_checkout - Complete or abandon?
6. complete_checkout / abandon_session - Final actions
"""

import random
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langsmith import traceable

from .state import AgentState
from .actions import get_actions

logger = logging.getLogger(__name__)


# =============================================================================
# Shopping Probability Constants
# =============================================================================

FREQUENCY_PROBABILITY = {
    "frequent": 0.70,  # 2-3x per week
    "regular": 0.40,  # weekly
    "occasional": 0.20,  # biweekly
    "rare": 0.05,  # monthly
}


# =============================================================================
# Node Functions (each decorated with @traceable for LangSmith)
# =============================================================================


@traceable(name="decide_shop")
def decide_shop_node(state: AgentState) -> dict:
    """
    Decide if agent should shop today based on persona attributes.

    Uses:
    - shopping_frequency for base probability
    - Day-of-week preferences as modifiers

    Returns:
        Updated state with 'should_shop' decision
    """
    # Base probability from shopping frequency
    frequency = state.get("shopping_frequency", "regular")
    base_prob = FREQUENCY_PROBABILITY.get(frequency, 0.30)

    # Day-of-week modifier
    simulated_date = state.get("simulated_date")
    if simulated_date:
        day_of_week = simulated_date.weekday()  # 0=Monday, 6=Sunday

        if day_of_week == 5:  # Saturday
            day_modifier = float(state.get("pref_day_saturday", 0.5))
        elif day_of_week == 6:  # Sunday
            day_modifier = float(state.get("pref_day_sunday", 0.5))
        else:  # Weekday
            day_modifier = float(state.get("pref_day_weekday", 0.5))
    else:
        day_modifier = 0.5

    # Final probability (day_modifier normalized around 1.0)
    # Modifier of 0.5 = no change, 1.0 = double, 0.0 = zero
    final_prob = base_prob * (day_modifier * 2)
    final_prob = min(final_prob, 0.95)  # Cap at 95%

    should_shop = random.random() < final_prob

    logger.debug(
        f"Agent {state.get('agent_id', '?')}: "
        f"shop decision = {should_shop} "
        f"(base={base_prob:.2f}, modifier={day_modifier:.2f}, final={final_prob:.2f})"
    )

    return {"should_shop": should_shop}


@traceable(name="browse_products")
def browse_products_node(state: AgentState) -> dict:
    """
    Create shopping session and browse products.

    Selects products based on preferred_categories.
    Creates view_product events for each.

    Returns:
        Updated state with session_id and products_viewed
    """
    actions = get_actions()

    # Create session
    session_id = actions.create_session(
        user_id=state["user_id"],
        store_id=state["store_id"],
        simulated_timestamp=state["simulated_timestamp"],
    )

    # Browse products - number based on avg_cart_value
    avg_cart = float(state.get("avg_cart_value", 30.0))
    max_products = max(3, min(10, int(avg_cart / 10)))  # 3-10 products

    products = actions.browse_products(
        session_id=session_id,
        user_id=state["user_id"],
        preferred_categories=state.get("preferred_categories", []),
        simulated_timestamp=state["simulated_timestamp"],
        max_products=max_products,
    )

    return {
        "session_id": session_id,
        "products_viewed": [p["id"] for p in products],
        "products_data": products,
        "events_created": state.get("events_created", 0) + len(products),
    }


@traceable(name="add_to_cart")
def add_to_cart_node(state: AgentState) -> dict:
    """
    Add products to cart based on impulsivity and price sensitivity.

    Higher impulsivity = more likely to add items
    Higher price sensitivity = less likely to add expensive items

    Returns:
        Updated state with cart_items and cart_total
    """
    actions = get_actions()
    cart_items = []
    cart_total = 0.0

    impulsivity = float(state.get("impulsivity", 0.5))
    price_sensitivity = float(state.get("price_sensitivity", 0.5))
    weekly_budget = float(state.get("weekly_budget", 100.0))

    # Get product data from previous node
    products_data = state.get("products_data", [])

    for product in products_data:
        price = float(product.get("price", 0.0))

        # Base add probability from impulsivity (0.3 to 0.8)
        # Increased base to ensure more realistic shopping behavior
        add_prob = 0.3 + (impulsivity * 0.5)

        # Reduce probability for expensive items based on price sensitivity
        if price > 0:
            price_factor = price / (weekly_budget / 4)  # Compare to 25% of budget
            add_prob *= 1 - price_sensitivity * min(price_factor, 0.5)

        # Budget constraint - less aggressive penalty
        if cart_total + price > weekly_budget:
            add_prob *= 0.5  # Less likely to exceed budget

        if random.random() < add_prob:
            quantity = 1
            # Slight chance of buying multiple (based on impulsivity)
            if random.random() < impulsivity * 0.3:
                quantity = random.choice([2, 3])

            actions.add_to_cart(
                session_id=state["session_id"],
                user_id=state["user_id"],
                store_id=state["store_id"],
                product_id=product["id"],
                product_name=product["name"],
                price=price,
                quantity=quantity,
                simulated_timestamp=state["simulated_timestamp"],
            )

            cart_items.append(
                {
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "price": price,
                    "quantity": quantity,
                    "category": product.get("category", ""),
                    "brand": product.get("brand", ""),
                }
            )
            cart_total += price * quantity

    return {
        "cart_items": cart_items,
        "cart_total": cart_total,
        "events_created": state.get("events_created", 0) + len(cart_items),
    }


@traceable(name="view_coupons")
def view_coupons_node(state: AgentState) -> dict:
    """
    View available coupons and check eligibility against cart.

    Higher coupon_affinity = more likely to apply coupons.

    Returns:
        Updated state with coupons_available and coupons_applied
    """
    actions = get_actions()

    # Get available coupons
    coupons = actions.view_coupons(
        session_id=state["session_id"],
        user_id=state["user_id"],
        simulated_timestamp=state["simulated_timestamp"],
    )

    # Get cart items with product details
    cart_items = state.get("cart_items", [])

    # Check eligibility
    coupons_applied = []
    coupon_affinity = float(state.get("coupon_affinity", 0.5))

    if cart_items and coupons:
        # Extract cart metadata
        categories = set()
        brands = set()
        for item in cart_items:
            # Get category/brand from item (already in products_data)
            categories.add(item.get("category", "").lower())
            brands.add(item.get("brand", "").lower())

        # Sort coupons by type - frontstore first
        sorted_coupons = sorted(
            coupons, key=lambda c: 0 if c["type"] == "frontstore" else 1
        )

        for coupon in sorted_coupons:
            # Check eligibility
            is_eligible = False

            if coupon["type"] == "frontstore":
                # Check min purchase
                min_amount = float(coupon.get("min_purchase_amount", 0) or 0)
                cart_total = state.get("cart_total", 0.0)
                if cart_total >= min_amount:
                    is_eligible = True

            elif coupon["type"] == "category":
                # Check if cart has matching category
                coupon_cat = (coupon.get("category_or_brand") or "").lower()
                if coupon_cat in categories:
                    is_eligible = True

            elif coupon["type"] == "brand":
                # Check if cart has matching brand
                coupon_brand = (coupon.get("category_or_brand") or "").lower()
                if coupon_brand in brands:
                    is_eligible = True

            # Apply if eligible and based on coupon_affinity
            if is_eligible:
                apply_prob = 0.3 + (coupon_affinity * 0.6)
                if random.random() < apply_prob:
                    actions.apply_coupon(
                        session_id=state["session_id"],
                        user_id=state["user_id"],
                        coupon_id=coupon["id"],
                        discount_details=coupon.get("discount_details", ""),
                        simulated_timestamp=state["simulated_timestamp"],
                    )
                    coupons_applied.append(coupon["id"])

    return {
        "coupons_available": coupons,
        "coupons_applied": coupons_applied,
        "events_created": state.get("events_created", 0) + 1,
    }


@traceable(name="decide_checkout")
def decide_checkout_node(state: AgentState) -> dict:
    """
    Decide whether to complete checkout or abandon cart.

    Factors:
    - Must have items in cart
    - Higher impulsivity = more likely to complete
    - Lower price_sensitivity = more likely to complete
    - Having applied coupons = more likely to complete

    Returns:
        Updated state with checkout_decision
    """
    cart_items = state.get("cart_items", [])
    impulsivity = float(state.get("impulsivity", 0.5))
    price_sensitivity = float(state.get("price_sensitivity", 0.5))
    coupons_applied = state.get("coupons_applied", [])

    if not cart_items:
        # No items - abandon
        decision = "abandon"
    else:
        # Base completion rate
        complete_prob = 0.6

        # Impulsivity boost
        complete_prob += impulsivity * 0.2

        # Price sensitivity penalty
        complete_prob -= price_sensitivity * 0.15

        # Coupon bonus
        if coupons_applied:
            complete_prob += 0.15

        # Clamp
        complete_prob = max(0.2, min(0.95, complete_prob))

        decision = "complete" if random.random() < complete_prob else "abandon"

    logger.debug(
        f"Agent {state.get('agent_id', '?')}: "
        f"checkout decision = {decision} "
        f"(cart={len(cart_items)} items, coupons={len(coupons_applied)})"
    )

    return {"checkout_decision": decision}


@traceable(name="complete_checkout")
def complete_checkout_node(state: AgentState) -> dict:
    """
    Complete the transaction - create order record.

    Returns:
        Updated state with order_id
    """
    actions = get_actions()

    order_id = actions.complete_checkout(
        session_id=state["session_id"],
        user_id=state["user_id"],
        store_id=state["store_id"],
        simulated_timestamp=state["simulated_timestamp"],
    )

    return {"order_id": order_id, "events_created": state.get("events_created", 0) + 1}


@traceable(name="abandon_session")
def abandon_session_node(state: AgentState) -> dict:
    """
    Abandon the shopping session.

    Returns:
        Updated state (session marked as abandoned)
    """
    actions = get_actions()

    # Only record abandon if we had a session
    if state.get("session_id"):
        actions.abandon_session(
            session_id=state["session_id"],
            user_id=state["user_id"],
            cart_items=state.get("cart_items", []),
            cart_total=state.get("cart_total", 0.0),
            simulated_timestamp=state["simulated_timestamp"],
        )

    return {
        "checkout_decision": "abandon",
        "events_created": state.get("events_created", 0) + 1,
    }


# =============================================================================
# Router Functions
# =============================================================================


def should_shop_router(state: AgentState) -> Literal["browse", "end"]:
    """Route based on should_shop decision."""
    return "browse" if state.get("should_shop", False) else "end"


def checkout_router(state: AgentState) -> Literal["complete", "abandon"]:
    """Route based on checkout decision."""
    decision = state.get("checkout_decision", "abandon")
    return "complete" if decision == "complete" else "abandon"


# =============================================================================
# Graph Builder
# =============================================================================


def build_shopping_graph() -> StateGraph:
    """
    Build the shopping workflow StateGraph.

    Graph structure:
    ```
    [START] -> [decide_shop] -> (shop?) -> [browse_products]
                               (skip) -> [END]

    [browse_products] -> [add_to_cart] -> [view_coupons] -> [decide_checkout]

    [decide_checkout] -> (complete?) -> [complete_checkout] -> [END]
                        (abandon) -> [abandon_session] -> [END]
    ```

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph with AgentState schema
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("decide_shop", decide_shop_node)
    workflow.add_node("browse_products", browse_products_node)
    workflow.add_node("add_to_cart", add_to_cart_node)
    workflow.add_node("view_coupons", view_coupons_node)
    workflow.add_node("decide_checkout", decide_checkout_node)
    workflow.add_node("complete_checkout", complete_checkout_node)
    workflow.add_node("abandon_session", abandon_session_node)

    # Set entry point
    workflow.set_entry_point("decide_shop")

    # Add edges
    workflow.add_conditional_edges(
        "decide_shop", should_shop_router, {"browse": "browse_products", "end": END}
    )
    workflow.add_edge("browse_products", "add_to_cart")
    workflow.add_edge("add_to_cart", "view_coupons")
    workflow.add_edge("view_coupons", "decide_checkout")
    workflow.add_conditional_edges(
        "decide_checkout",
        checkout_router,
        {"complete": "complete_checkout", "abandon": "abandon_session"},
    )
    workflow.add_edge("complete_checkout", END)
    workflow.add_edge("abandon_session", END)

    # Compile and return
    return workflow.compile()


# Pre-compiled graph for reuse
_compiled_graph = None


def get_shopping_graph() -> StateGraph:
    """
    Get the compiled shopping graph (singleton).

    Returns:
        Compiled StateGraph
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_shopping_graph()
    return _compiled_graph
