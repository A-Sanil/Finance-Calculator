"""
Trading Dashboard Route

Provides a live trading dashboard showing account, positions, and trade execution.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard")
def trading_dashboard():
    """Serve the trading dashboard HTML."""
    return {
        "message": "Navigate to /trading-dashboard.html in the browser",
        "api_endpoints": {
            "account": "/trading/account",
            "positions": "/trading/positions",
            "orders": "/trading/orders",
            "trades": "/trading/trades",
            "scheduler_status": "/trading/scheduler/status",
        }
    }
