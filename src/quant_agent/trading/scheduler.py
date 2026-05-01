"""
Recommendation Scheduler

Runs the recommendation engine on a schedule and auto-executes signals.
"""

import logging
from typing import Optional, Dict
from datetime import datetime, time

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    BackgroundScheduler = None
    CronTrigger = None

from quant_agent.sector_recommendations import SectorRecommendationEngine
from quant_agent.trading.alpaca_client import AlpacaClient
from quant_agent.trading.trading_executor import TradingExecutor


logger = logging.getLogger(__name__)


class RecommendationScheduler:
    """
    Schedules hourly recommendation generation and auto-execution.
    
    Runs every hour during market hours (9:30 AM - 4:00 PM ET).
    Generates sector recommendations and auto-executes strong signals.
    """
    
    def __init__(
        self,
        alpaca_client: Optional[AlpacaClient] = None,
        recommendation_engine: Optional[SectorRecommendationEngine] = None,
        trading_executor: Optional[TradingExecutor] = None,
        auto_execute: bool = True,
        min_confidence: float = 0.80,
    ):
        """
        Initialize the scheduler.
        
        Args:
            alpaca_client: Alpaca API client (initialized if None)
            recommendation_engine: Recommendation engine (initialized if None)
            trading_executor: Trading executor (initialized if None)
            auto_execute: Whether to auto-execute signals (default: True)
            min_confidence: Minimum confidence to execute trades (default: 0.80)
        """
        if BackgroundScheduler is None:
            raise RuntimeError("apscheduler not installed. Run: pip install apscheduler")
        
        self.alpaca_client = alpaca_client or AlpacaClient(paper_trading=True)
        self.recommendation_engine = recommendation_engine or SectorRecommendationEngine()
        self.trading_executor = trading_executor or TradingExecutor(self.alpaca_client)
        self.auto_execute = auto_execute
        self.min_confidence = min_confidence
        
        self.scheduler = BackgroundScheduler()
        self.last_run: Optional[datetime] = None
        self.last_recommendations: Dict = {}
    
    def _is_market_open(self) -> bool:
        """Check if stock market is currently open (9:30 AM - 4:00 PM ET)."""
        now = datetime.now()
        # Simple check: weekday and between 9:30 AM and 4:00 PM
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        
        return market_open <= current_time < market_close
    
    def run_recommendations(self) -> Dict:
        """
        Generate sector recommendations and optionally execute trades.
        
        Returns:
            Dict with recommendations and execution summary.
        """
        if not self._is_market_open():
            logger.info("Market is closed. Skipping recommendations.")
            return {"status": "market_closed"}
        
        try:
            logger.info("Generating sector recommendations...")
            
            # Generate recommendations for top sectors
            sectors_to_analyze = [
                ("technology", "semiconductors"),
                ("financials", "banks"),
                ("healthcare", "pharma"),
            ]
            
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "recommendations": [],
                "trades_executed": [],
            }
            
            for sector, subsector in sectors_to_analyze:
                try:
                    logger.info(f"Analyzing {sector}/{subsector}...")
                    
                    report = self.recommendation_engine.build_sector_report(
                        sector=sector,
                        subsector=subsector,
                        live_sources=False,  # Use cached data for speed
                    )
                    
                    if not report:
                        continue
                    
                    # Extract top stock pick if available
                    if report.stocks and len(report.stocks) > 0:
                        top_pick = report.stocks[0]
                        
                        rec = {
                            "sector": sector,
                            "subsector": subsector,
                            "ticker": top_pick.get("ticker"),
                            "signal": report.sector_thesis[:100],  # Summary
                        }
                        results["recommendations"].append(rec)
                        
                        # Auto-execute if confidence is high
                        if self.auto_execute and len(report.stocks) > 0:
                            ticker = top_pick.get("ticker")
                            if ticker:
                                # Simple logic: BUY if positive thesis
                                signal = "BUY" if "positive" in report.sector_thesis.lower() or "strength" in report.sector_thesis.lower() else "HOLD"
                                
                                if signal == "BUY" and self.min_confidence <= 0.8:
                                    order = self.trading_executor.execute_signal(
                                        ticker=ticker,
                                        signal=signal,
                                        confidence=self.min_confidence,
                                        reason=f"Automated signal from {subsector} sector analysis",
                                    )
                                    
                                    if order:
                                        results["trades_executed"].append({
                                            "ticker": ticker,
                                            "order_id": order.order_id,
                                            "side": order.side,
                                            "qty": order.qty,
                                        })
                
                except Exception as e:
                    logger.error(f"Error analyzing {sector}/{subsector}: {e}")
                    continue
            
            self.last_run = datetime.utcnow()
            self.last_recommendations = results
            logger.info(f"Recommendations generated: {len(results['recommendations'])} sectors analyzed")
            
            return results
        
        except Exception as e:
            logger.error(f"Error in recommendation generation: {e}")
            return {"status": "error", "error": str(e)}
    
    def start(self, cron_expression: str = "0 * * * *"):
        """
        Start the scheduler.
        
        Args:
            cron_expression: Cron schedule for recommendations (default: every hour)
                            "0 * * * *" = every hour at minute 0
                            "0 10-16 * * 1-5" = every hour 10am-4pm weekdays
        """
        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return
        
        # Schedule hourly recommendations during market hours
        self.scheduler.add_job(
            self.run_recommendations,
            trigger=CronTrigger.from_crontab(cron_expression),
            id="recommendation_job",
            name="Hourly sector recommendations",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info(f"Scheduler started with cron: {cron_expression}")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def get_status(self) -> Dict:
        """
        Get scheduler status and last recommendations.
        
        Returns:
            Dict with running status and recent recommendations.
        """
        return {
            "running": self.scheduler.running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "auto_execute": self.auto_execute,
            "min_confidence": self.min_confidence,
            "last_recommendations": self.last_recommendations,
        }
