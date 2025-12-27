"""
Offer Engine API Routes - B-7, S-1

API endpoints for offer management and simulation control.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import get_config, get_time_service, get_scheduler, is_simulation_mode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["offer-engine"])


# ============================================
# Request/Response Models
# ============================================

class StartSimulationRequest(BaseModel):
    calendar_start: str  # ISO date format: "2024-01-01"
    time_scale: Optional[float] = 168.0


class AdvanceTimeRequest(BaseModel):
    hours: float


class RefreshRequest(BaseModel):
    user_id: str


# ============================================
# Simulation Control Endpoints (S-1)
# ============================================

@router.post("/simulation/start")
async def start_simulation(request: StartSimulationRequest, db: Session = Depends(lambda: None)):
    """Start simulation with calendar alignment."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled. Set SIMULATION_MODE=true")

    try:
        calendar_start = date.fromisoformat(request.calendar_start)
    except ValueError:
        raise HTTPException(400, f"Invalid date format: {request.calendar_start}. Use YYYY-MM-DD")

    # Update time scale if provided
    if request.time_scale:
        config.time_scale = request.time_scale

    time_service = get_time_service(db)
    time_service.start_simulation(calendar_start)

    return {
        "success": True,
        "calendar_start": request.calendar_start,
        "current_simulated_date": time_service.get_simulated_date().isoformat(),
        "time_scale": config.time_scale,
    }


@router.post("/simulation/stop")
async def stop_simulation(db: Session = Depends(lambda: None)):
    """End active simulation, preserve state."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    time_service = get_time_service(db)
    if not time_service.is_simulation_active():
        raise HTTPException(400, "No active simulation to stop")

    result = time_service.stop_simulation()

    return {
        "success": True,
        "final_simulated_date": str(result["final_simulated_date"]) if result["final_simulated_date"] else None,
        "total_real_hours_elapsed": round(result["total_real_hours_elapsed"], 2),
    }


@router.post("/simulation/advance")
async def advance_time(request: AdvanceTimeRequest, db: Session = Depends(lambda: None)):
    """Advance simulation time by specified hours."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    if request.hours <= 0:
        raise HTTPException(400, "Hours must be positive")

    scheduler = get_scheduler(db)

    try:
        result = scheduler.advance_simulation_time(request.hours)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "success": True,
        "previous_date": result.previous_date,
        "new_date": result.new_date,
        "cycles_completed": result.cycles_completed,
        "users_refreshed": result.users_refreshed,
        "offers_assigned": result.offers_assigned,
        "real_hours_advanced": result.real_hours_advanced,
    }


@router.get("/simulation/status")
async def get_simulation_status(db: Session = Depends(lambda: None)):
    """Get current simulation state."""
    config = get_config()
    time_service = get_time_service(db)

    status = time_service.get_status()
    status["simulation_mode_enabled"] = config.simulation_mode

    # Add cycle info
    if config.simulation_mode and time_service.is_simulation_active():
        scheduler = get_scheduler(db)
        cycle = scheduler.cycle_manager.get_or_create_current_cycle()
        status["current_cycle"] = {
            "id": cycle.id,
            "number": cycle.cycle_number,
            "started_at": cycle.started_at.isoformat(),
            "ends_at": cycle.ends_at.isoformat(),
            "simulated_start_date": cycle.simulated_start_date,
            "simulated_end_date": cycle.simulated_end_date,
        }

    return status


@router.post("/simulation/reset")
async def reset_simulation(db: Session = Depends(lambda: None)):
    """Reset simulation to fresh state."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    time_service = get_time_service(db)

    # Stop simulation if active
    if time_service.is_simulation_active():
        time_service.stop_simulation()

    # Clear simulation data
    from . import get_scheduler
    db_session = db

    # Expire all simulation offers
    result = db_session.execute(text("""
        UPDATE user_coupons
        SET status = 'expired'
        WHERE is_simulation = true AND status = 'active'
    """))
    offers_expired = result.rowcount

    # Clear simulation cycles
    result = db_session.execute(text("""
        DELETE FROM offer_cycles WHERE is_simulation = true
    """))
    cycles_cleared = result.rowcount

    # Clear user cycle states
    db_session.execute(text("""
        DELETE FROM user_offer_cycles WHERE is_simulation = true
    """))

    db_session.commit()

    return {
        "success": True,
        "offers_expired": offers_expired,
        "cycles_cleared": cycles_cleared,
    }


# ============================================
# Offer Endpoints (B-7)
# ============================================

@router.get("/offers/wallet/{user_id}")
async def get_wallet(user_id: str, db: Session = Depends(lambda: None)):
    """Get user's current wallet with status filtering."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    time_service = get_time_service(db)

    # Get offers
    result = db.execute(text("""
        SELECT uc.id, uc.coupon_id, uc.status, uc.assigned_at, uc.eligible_until,
               c.type, c.discount_details, c.category_or_brand
        FROM user_coupons uc
        JOIN coupons c ON c.id = uc.coupon_id
        WHERE uc.user_id = :uid AND uc.is_simulation = true
        ORDER BY uc.status, uc.assigned_at DESC
    """), {"uid": user_id}).fetchall()

    offers = []
    active_count = 0
    expired_count = 0

    for row in result:
        offer = {
            "id": str(row.id),
            "coupon_id": str(row.coupon_id),
            "type": row.type,
            "discount_details": row.discount_details,
            "category_or_brand": row.category_or_brand,
            "status": row.status,
            "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
            "eligible_until": row.eligible_until.isoformat() if row.eligible_until else None,
        }
        offers.append(offer)
        if row.status == "active":
            active_count += 1
        elif row.status == "expired":
            expired_count += 1

    return {
        "user_id": user_id,
        "simulated_date": time_service.get_simulated_date().isoformat() if time_service.get_simulated_date() else None,
        "offers": offers,
        "active_count": active_count,
        "expired_count": expired_count,
    }


@router.post("/offers/refresh")
async def force_refresh(request: RefreshRequest, db: Session = Depends(lambda: None)):
    """Force refresh for user (simulation only)."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    scheduler = get_scheduler(db)
    result = scheduler.force_refresh_user(request.user_id)

    if not result.refreshed:
        raise HTTPException(400, f"Refresh failed: {result.reason}")

    return {
        "success": True,
        "user_id": result.user_id,
        "expired_count": result.expired_count,
        "assigned_count": result.assigned_count,
    }


@router.get("/offers/stats/{user_id}")
async def get_offer_stats(user_id: str, db: Session = Depends(lambda: None)):
    """Get offer statistics for a user."""
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    scheduler = get_scheduler(db)
    stats = scheduler.expiration_handler.get_expiration_stats(user_id)

    # Get cycle info
    state = scheduler.cycle_manager.get_user_cycle_state(user_id)

    return {
        "user_id": user_id,
        "offer_stats": stats,
        "last_refresh_at": state.last_refresh_at.isoformat() if state and state.last_refresh_at else None,
        "next_refresh_at": state.next_refresh_at.isoformat() if state and state.next_refresh_at else None,
    }


@router.get("/simulation/stats")
async def get_simulation_stats(db: Session = Depends(lambda: None)):
    """
    Get comprehensive simulation statistics from database.

    Returns counts of sessions, orders, events, offers, etc.
    """
    config = get_config()
    if not config.simulation_mode:
        raise HTTPException(400, "Simulation mode not enabled")

    stats = {}

    # Simulation state
    time_service = get_time_service(db)
    status = time_service.get_status()
    stats["simulated_date"] = str(status.get("current_simulated_date")) if status.get("current_simulated_date") else None
    stats["is_active"] = status.get("is_active", False)
    stats["time_scale"] = status.get("time_scale")

    # Agent counts
    result = db.execute(text("""
        SELECT COUNT(*) FROM agents WHERE is_active = true
    """))
    stats["agents_active"] = result.scalar() or 0

    # Session counts
    result = db.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'abandoned') as abandoned,
            COUNT(*) FILTER (WHERE status = 'active') as active
        FROM shopping_sessions
        WHERE is_simulated = true
    """))
    row = result.fetchone()
    stats["sessions"] = {
        "total": row[0] or 0,
        "completed": row[1] or 0,
        "abandoned": row[2] or 0,
        "active": row[3] or 0
    } if row else {"total": 0, "completed": 0, "abandoned": 0, "active": 0}

    # Order counts
    result = db.execute(text("""
        SELECT
            COUNT(*) as total,
            COALESCE(SUM(total), 0) as revenue
        FROM orders
        WHERE is_simulated = true
    """))
    row = result.fetchone()
    stats["orders"] = {
        "total": row[0] or 0,
        "revenue": float(row[1] or 0)
    } if row else {"total": 0, "revenue": 0.0}

    # Event counts by type
    result = db.execute(text("""
        SELECT event_type, COUNT(*)
        FROM shopping_session_events
        WHERE session_id IN (
            SELECT id FROM shopping_sessions WHERE is_simulated = true
        )
        GROUP BY event_type
    """))
    event_counts = {}
    for row in result.fetchall():
        event_counts[row[0]] = row[1]
    stats["events"] = event_counts
    stats["events"]["total"] = sum(event_counts.values())

    # Offer counts by status
    result = db.execute(text("""
        SELECT status, COUNT(*)
        FROM user_coupons
        WHERE is_simulation = true
        GROUP BY status
    """))
    offer_counts = {}
    for row in result.fetchall():
        offer_counts[row[0] or 'unknown'] = row[1]
    stats["offers"] = offer_counts

    # Cycle count
    result = db.execute(text("""
        SELECT COUNT(*) FROM offer_cycles WHERE is_simulation = true
    """))
    stats["cycles_completed"] = result.scalar() or 0

    return stats
