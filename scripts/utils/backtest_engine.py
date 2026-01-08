"""Backtesting engine for strategy validation."""

import logging
import json
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from agents.state import AgentState
from trading_orchestration.trading_graph import TradingGraph
from core_kernel.mongodb_schema import get_mongo_client, get_collection
from core_kernel.config.settings import settings

logger = logging.getLogger(__name__)

try:
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available, visualization disabled")


class BacktestEngine:
    """Backtesting engine for validating strategies on historical data."""
    
    def __init__(self):
        """Initialize backtest engine."""
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.ohlc_collection = get_collection(self.db, "ohlc_history")
        self.results_collection = get_collection(self.db, "backtest_results")
    
    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        trading_graph: TradingGraph,
        initial_capital: float = 1000000
    ) -> Dict[str, Any]:
        """Run backtest on historical data."""
        logger.info(f"Running backtest from {start_date} to {end_date}")
        
        # Get historical OHLC data
        ohlc_data = list(self.ohlc_collection.find({
            "timestamp": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            },
            "timeframe": "5min"
        }).sort("timestamp", 1))
        
        if not ohlc_data:
            logger.warning("No historical data found for backtest")
            return {"error": "No historical data"}
        
        # Simulate trading
        capital = initial_capital
        positions = []
        trades = []
        
        for i, candle in enumerate(ohlc_data):
            # Create state from historical candle
            state = AgentState(
                current_price=candle["close"],
                current_time=datetime.fromisoformat(candle["timestamp"]),
                ohlc_5min=ohlc_data[max(0, i-100):i+1]  # Last 100 candles
            )
            
            # Run trading graph
            try:
                result = trading_graph.run(initial_state=state)
                
                # Execute trade if signal is BUY or SELL
                if result.final_signal.value in ["BUY", "SELL"]:
                    trade = self._simulate_trade(result, capital)
                    if trade:
                        trades.append(trade)
                        capital = trade["ending_capital"]
                        
            except Exception as e:
                logger.error(f"Error in backtest iteration: {e}")
                continue
        
        # Calculate performance metrics
        metrics = self._calculate_metrics(trades, initial_capital)
        
        # Store results
        backtest_id = f"BT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result_doc = {
            "backtest_id": backtest_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": initial_capital,
            "final_capital": capital,
            "trades": trades,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        self.results_collection.insert_one(result_doc)
        
        return result_doc
    
    def _simulate_trade(self, state: AgentState, capital: float) -> Optional[Dict[str, Any]]:
        """Simulate a trade execution."""
        if state.position_size <= 0:
            return None
        
        entry_price = state.entry_price
        quantity = state.position_size
        required_capital = entry_price * quantity
        
        if required_capital > capital:
            return None  # Insufficient capital
        
        # Simulate exit (simplified - in production, use actual exit logic)
        exit_price = state.take_profit  # Assume we hit take profit
        pnl = (exit_price - entry_price) * quantity if state.final_signal.value == "BUY" else (entry_price - exit_price) * quantity
        
        return {
            "trade_id": state.trade_id,
            "signal": state.final_signal.value,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "starting_capital": capital,
            "ending_capital": capital + pnl
        }
    
    def _calculate_metrics(self, trades: List[Dict[str, Any]], initial_capital: float) -> Dict[str, Any]:
        """Calculate comprehensive backtest performance metrics."""
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "return_pct": 0,
                "sharpe_ratio": 0,
                "calmar_ratio": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "max_drawdown_pct": 0
            }
        
        profitable_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        
        total_trades = len(trades)
        win_rate = (len(profitable_trades) / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t["pnl"] for t in trades)
        gross_profit = sum(t["pnl"] for t in profitable_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))
        
        final_capital = trades[-1]["ending_capital"] if trades else initial_capital
        return_pct = ((final_capital - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0
        
        # Profit factor
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        
        # Average win/loss
        avg_win = (gross_profit / len(profitable_trades)) if profitable_trades else 0
        avg_loss = (gross_loss / len(losing_trades)) if losing_trades else 0
        
        # Sharpe ratio (simplified - using returns)
        returns = [t["pnl"] / initial_capital for t in trades]
        if len(returns) > 1:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0  # Annualized
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        equity_curve = [initial_capital]
        for trade in trades:
            equity_curve.append(trade["ending_capital"])
        
        peak = equity_curve[0]
        max_drawdown = 0
        max_drawdown_pct = 0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        # Calmar ratio (annual return / max drawdown)
        # Assuming daily returns, annualize by multiplying by 252
        annual_return = return_pct * (252 / len(trades)) if trades else 0
        calmar_ratio = (annual_return / max_drawdown_pct) if max_drawdown_pct > 0 else 0
        
        return {
            "total_trades": total_trades,
            "profitable_trades": len(profitable_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "average_pnl": round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
            "average_win": round(avg_win, 2),
            "average_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "return_pct": round(return_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "final_capital": round(final_capital, 2),
            "equity_curve": equity_curve
        }
    
    def generate_equity_curve_plot(self, metrics: Dict[str, Any], output_path: Optional[str] = None) -> Optional[str]:
        """Generate equity curve visualization."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available, skipping visualization")
            return None
        
        equity_curve = metrics.get("equity_curve", [])
        if not equity_curve:
            logger.warning("No equity curve data available")
            return None
        
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(equity_curve, linewidth=2)
            plt.title("Backtest Equity Curve", fontsize=14, fontweight="bold")
            plt.xlabel("Trade Number", fontsize=12)
            plt.ylabel("Capital (₹)", fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Add metrics as text
            metrics_text = (
                f"Total Return: {metrics.get('return_pct', 0):.2f}%\n"
                f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}\n"
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%\n"
                f"Win Rate: {metrics.get('win_rate', 0):.2f}%"
            )
            plt.text(0.02, 0.98, metrics_text, transform=plt.gca().transAxes,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"Equity curve saved to {output_path}")
            else:
                # Return as base64 or save to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    plt.savefig(tmp.name, dpi=300, bbox_inches='tight')
                    output_path = tmp.name
            
            plt.close()
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating equity curve: {e}")
            return None
    
    def export_results(self, result_doc: Dict[str, Any], output_format: str = "json", output_path: Optional[str] = None) -> str:
        """Export backtest results to file."""
        backtest_id = result_doc.get("backtest_id", "backtest")
        
        if output_format == "json":
            if output_path is None:
                output_path = f"{backtest_id}_results.json"
            
            with open(output_path, 'w') as f:
                json.dump(result_doc, f, indent=2, default=str)
            
            logger.info(f"Results exported to {output_path}")
            return output_path
            
        elif output_format == "csv":
            if output_path is None:
                output_path = f"{backtest_id}_results.csv"
            
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write metrics
                writer.writerow(["Metric", "Value"])
                metrics = result_doc.get("metrics", {})
                for key, value in metrics.items():
                    if key != "equity_curve":  # Skip equity curve in CSV
                        writer.writerow([key, value])
                
                writer.writerow([])
                
                # Write trades
                writer.writerow(["Trade Details"])
                trades = result_doc.get("trades", [])
                if trades:
                    writer.writerow(list(trades[0].keys()))
                    for trade in trades:
                        writer.writerow([trade.get(k, "") for k in trades[0].keys()])
            
            logger.info(f"Results exported to {output_path}")
            return output_path
        
        else:
            raise ValueError(f"Unsupported output format: {output_format}")


