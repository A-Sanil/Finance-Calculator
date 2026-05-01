from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from typing import Optional

from quant_agent.recommendations import RecommendationEngine
from quant_agent.sector_recommendations import SectorRecommendationEngine
from quant_agent.sectors import DEFAULT_SECTOR_UNIVERSE
from quant_agent.schemas import BacktestRequest, BacktestResponse, FusedRecommendation, IngestRequest, IngestResponse, SignalRequest
from quant_agent.services import AgentService
from quant_agent.web.app import router as web_router
from quant_agent.trading import AlpacaClient, TradingExecutor, RecommendationScheduler

app = FastAPI(title="Agentic Traversal of Unstructured Data", version="0.1.0")
service = AgentService()
recommendation_engine = RecommendationEngine()
sector_recommendation_engine = SectorRecommendationEngine()

# Initialize trading components (optional - only if Alpaca API keys are set)
alpaca_client = None
trading_executor = None
scheduler = None

try:
    alpaca_client = AlpacaClient(paper_trading=True)
    trading_executor = TradingExecutor(alpaca_client)
    scheduler = RecommendationScheduler(
        alpaca_client=alpaca_client,
        recommendation_engine=sector_recommendation_engine,
        trading_executor=trading_executor,
        auto_execute=False,  # Start with manual control
    )
except Exception as e:
    print(f"Warning: Trading features disabled ({e}). Set APCA_API_KEY_ID and APCA_API_SECRET_KEY to enable.")

app.include_router(web_router)


class RecommendationRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    sec_ciks: dict[str, str] = Field(default_factory=dict)
    live_sources: bool = Field(default=False)

Optional[str]
class SectorRecommendationRequest(BaseModel):
    sector: str = Field(..., min_length=2)
    subsector: Optional[str] = None
    live_sources: bool = Field(default=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest_document(request: IngestRequest) -> IngestResponse:
    return service.ingest(request)


@app.post("/signals", response_model=FusedRecommendation)
def generate_signals(request: SignalRequest) -> FusedRecommendation:
    response = service.generate_signal(request)
    if response.recommendation == "insufficient evidence":
        raise HTTPException(status_code=409, detail="insufficient evidence to generate recommendation")
    return response


@app.post("/backtest", response_model=BacktestResponse)
def run_backtest(request: BacktestRequest) -> BacktestResponse:
    return service.backtest(request)


@app.post("/recommendations/markdown")
def build_recommendation_markdown(request: RecommendationRequest) -> dict[str, str]:
    report = recommendation_engine.build_report(request.tickers, request.sec_ciks, live_sources=request.live_sources)
    return {"markdown": report.to_markdown()}


@app.get("/sectors")
def list_sectors() -> dict[str, list[str]]:
    return {"sectors": DEFAULT_SECTOR_UNIVERSE.sector_names()}


@app.post("/sector/recommendations/markdown")
def build_sector_recommendation_markdown(request: SectorRecommendationRequest) -> dict[str, str]:
    result = sector_recommendation_engine.build_sector_report(
        request.sector,
        request.subsector,
        live_sources=request.live_sources,
    )
    return {"markdown": result.to_markdown()}


# ==================== Trading Endpoints ====================

@app.get("/trading/account")
def get_trading_account() -> dict:
    """Get Alpaca account information."""
    if not alpaca_client:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        account = alpaca_client.get_account()
        return {
            "account_number": account.account_number,
            "status": account.status,
            "equity": account.portfolio_value,
            "cash": account.cash,
            "buying_power": account.buying_power,
            "cash_pct": account.cash_pct,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/positions")
def get_trading_positions() -> dict:
    """Get current open positions."""
    if not alpaca_client:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        positions = alpaca_client.get_positions()
        return {
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "avg_fill_price": p.avg_fill_price,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "cost_basis": p.cost_basis,
                    "gain_loss": p.gain_loss,
                    "gain_loss_pct": p.gain_loss_pct,
                }
                for p in positions
            ],
            "total_positions": len(positions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/orders")
def get_trading_orders(status: str = "all") -> dict:
    """Get order history. Status: 'all', 'open', 'closed'."""
    if not alpaca_client:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        orders = alpaca_client.get_orders(status=status)
        return {
            "orders": [
                {
                    "order_id": o.order_id,
                    "symbol": o.symbol,
                    "qty": o.qty,
                    "side": o.side,
                    "status": o.status,
                    "filled_qty": o.filled_qty,
                    "filled_avg_price": o.filled_avg_price,
                    "created_at": o.created_at,
                    "filled_at": o.filled_at,
                }
                for o in orders
            ],
            "total_orders": len(orders),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PlaceOrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str  # "buy" or "sell"
    reason: Optional[str] = None


@app.post("/trading/place-order")
def place_trading_order(request: PlaceOrderRequest) -> dict:
    """Manually place a BUY or SELL order."""
    if not alpaca_client or not trading_executor:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    if request.side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")
    
    try:
        order = alpaca_client.place_order(request.symbol, request.qty, request.side)
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "qty": order.qty,
            "side": order.side,
            "status": order.status,
            "filled_qty": order.filled_qty,
            "filled_avg_price": order.filled_avg_price,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/trades")
def get_trade_history() -> dict:
    """Get trade execution history from the log."""
    if not trading_executor:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        trades = trading_executor.get_trade_history()
        summary = trading_executor.get_summary()
        return {
            "trades": trades,
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trading/scheduler/status")
def get_scheduler_status() -> dict:
    """Get scheduler status and last recommendations."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        status = scheduler.get_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/scheduler/start")
def start_scheduler(cron: str = "0 * * * *") -> dict:
    """Start the recommendation scheduler. Cron format: '0 * * * *' = every hour."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        scheduler.start(cron_expression=cron)
        return {"status": "started", "cron": cron}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trading/scheduler/stop")
def stop_scheduler() -> dict:
    """Stop the recommendation scheduler."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Trading features disabled. Set Alpaca API keys.")
    
    try:
        scheduler.stop()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
