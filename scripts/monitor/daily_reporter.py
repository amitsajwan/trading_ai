"""Automated daily reporting service that runs at market close."""

import logging
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, Any, List
from core_kernel.mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from monitoring.alerts import AlertSystem

logger = logging.getLogger(__name__)


class DailyReporter:
    """Daily reporting service that generates and sends trading metrics."""
    
    def __init__(self):
        """Initialize daily reporter."""
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.trades_collection = get_collection(self.db, "trades_executed")
        self.reports_collection = get_collection(self.db, "daily_reports")
        self.alert_system = AlertSystem()
    
    def generate_daily_report(self, report_date: datetime = None) -> Dict[str, Any]:
        """Generate daily trading report."""
        if report_date is None:
            report_date = datetime.now()
        
        # Get start and end of day
        start_of_day = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = report_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logger.info(f"Generating daily report for {report_date.date()}")
        
        # Get all trades for the day
        trades = list(self.trades_collection.find({
            "entry_timestamp": {
                "$gte": start_of_day.isoformat(),
                "$lte": end_of_day.isoformat()
            }
        }))
        
        # Get closed trades
        closed_trades = [t for t in trades if t.get("status") == "CLOSED"]
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        
        # Calculate metrics
        total_trades = len(closed_trades)
        profitable_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in closed_trades if t.get("pnl", 0) <= 0]
        
        win_rate = (len(profitable_trades) / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        gross_profit = sum(t.get("pnl", 0) for t in profitable_trades)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losing_trades))
        
        avg_win = (gross_profit / len(profitable_trades)) if profitable_trades else 0
        avg_loss = (gross_loss / len(losing_trades)) if losing_trades else 0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        
        # Calculate unrealized P&L for open positions
        unrealized_pnl = 0
        for trade in open_trades:
            entry_price = trade.get("entry_price") or trade.get("filled_price", 0)
            current_price = trade.get("current_price", entry_price)
            quantity = trade.get("quantity") or trade.get("filled_quantity", 0)
            signal = trade.get("signal", "BUY")
            
            if signal == "BUY":
                unrealized_pnl += (current_price - entry_price) * quantity
            else:  # SELL
                unrealized_pnl += (entry_price - current_price) * quantity
        
        # Calculate Sharpe ratio (simplified - using daily returns)
        returns = [t.get("pnl_percent", 0) / 100 for t in closed_trades if t.get("pnl_percent")]
        if returns:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate max drawdown
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        
        for trade in sorted(closed_trades, key=lambda x: x.get("entry_timestamp", "")):
            cumulative_pnl += trade.get("pnl", 0)
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        report = {
            "report_date": report_date.date().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "total_trades": total_trades,
            "profitable_trades": len(profitable_trades),
            "losing_trades": len(losing_trades),
            "open_positions": len(open_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "realized_pnl": round(total_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "average_win": round(avg_win, 2),
            "average_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "trades": closed_trades
        }
        
        # Store report in MongoDB
        try:
            self.reports_collection.insert_one(report.copy())
        except Exception as e:
            logger.error(f"Error storing report in MongoDB: {e}")
        
        return report
    
    def generate_csv_report(self, report: Dict[str, Any]) -> str:
        """Generate CSV report from daily report."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Daily Trading Report", report["report_date"]])
        writer.writerow([])
        
        # Write summary metrics
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Trades", report["total_trades"]])
        writer.writerow(["Profitable Trades", report["profitable_trades"]])
        writer.writerow(["Losing Trades", report["losing_trades"]])
        writer.writerow(["Win Rate (%)", f"{report['win_rate']:.2f}"])
        writer.writerow(["Total P&L", f"₹{report['total_pnl']:.2f}"])
        writer.writerow(["Realized P&L", f"₹{report['realized_pnl']:.2f}"])
        writer.writerow(["Unrealized P&L", f"₹{report['unrealized_pnl']:.2f}"])
        writer.writerow(["Gross Profit", f"₹{report['gross_profit']:.2f}"])
        writer.writerow(["Gross Loss", f"₹{report['gross_loss']:.2f}"])
        writer.writerow(["Average Win", f"₹{report['average_win']:.2f}"])
        writer.writerow(["Average Loss", f"₹{report['average_loss']:.2f}"])
        writer.writerow(["Profit Factor", f"{report['profit_factor']:.2f}"])
        writer.writerow(["Sharpe Ratio", f"{report['sharpe_ratio']:.2f}"])
        writer.writerow(["Max Drawdown", f"₹{report['max_drawdown']:.2f}"])
        writer.writerow([])
        
        # Write trade details
        writer.writerow(["Trade Details"])
        writer.writerow(["Trade ID", "Signal", "Entry Price", "Exit Price", "Quantity", "P&L", "P&L %", "Exit Reason"])
        
        for trade in report.get("trades", []):
            writer.writerow([
                trade.get("trade_id", ""),
                trade.get("signal", ""),
                trade.get("entry_price", ""),
                trade.get("exit_price", ""),
                trade.get("quantity", ""),
                f"₹{trade.get('pnl', 0):.2f}",
                f"{trade.get('pnl_percent', 0):.2f}%",
                trade.get("exit_reason", "")
            ])
        
        return output.getvalue()
    
    async def send_daily_report(self, report_date: datetime = None):
        """Generate and send daily report."""
        try:
            # Generate report
            report = self.generate_daily_report(report_date)
            
            # Format message for Slack
            message = (
                f"📊 Daily Trading Report - {report['report_date']}\n\n"
                f"Trades: {report['total_trades']} ({report['profitable_trades']}W/{report['losing_trades']}L)\n"
                f"Win Rate: {report['win_rate']:.1f}%\n"
                f"Total P&L: ₹{report['total_pnl']:.2f}\n"
                f"Realized: ₹{report['realized_pnl']:.2f} | Unrealized: ₹{report['unrealized_pnl']:.2f}\n"
                f"Profit Factor: {report['profit_factor']:.2f}\n"
                f"Sharpe Ratio: {report['sharpe_ratio']:.2f}\n"
                f"Max Drawdown: ₹{report['max_drawdown']:.2f}\n"
                f"Open Positions: {report['open_positions']}"
            )
            
            # Send to Slack
            await self.alert_system.send_slack_alert(message, "INFO")
            
            logger.info(f"Daily report sent for {report['report_date']}")
            
            return report
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}", exc_info=True)
            return None
    
    def get_recent_reports(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent daily reports."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return list(self.reports_collection.find({
            "timestamp": {"$gte": cutoff}
        }).sort("report_date", -1))

