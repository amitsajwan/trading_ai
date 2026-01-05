"""Cleanup stale paper trading positions and data."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from datetime import datetime, timedelta
import argparse

def cleanup_paper_trades(days_old: int = None, all_trades: bool = False):
    """
    Clean up paper trading positions.
    
    Args:
        days_old: Remove positions older than this many days (default: all CLOSED)
        all_trades: If True, remove ALL paper trades (use with caution!)
    """
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        print("=" * 60)
        print("Paper Trading Cleanup")
        print("=" * 60)
        
        if all_trades:
            # Remove ALL paper trades
            print("\n⚠️  WARNING: This will remove ALL paper trading positions!")
            response = input("Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
            
            result = trades_collection.delete_many({"paper_trading": True})
            print(f"\n✅ Removed {result.deleted_count} paper trading positions")
            
        elif days_old is not None:
            # Remove positions older than N days
            cutoff_date = datetime.now() - timedelta(days=days_old)
            query = {
                "paper_trading": True,
                "entry_timestamp": {"$lt": cutoff_date.isoformat()}
            }
            
            # Count first
            count = trades_collection.count_documents(query)
            if count == 0:
                print(f"\n✅ No paper trades older than {days_old} days found")
                return
            
            print(f"\n⚠️  Found {count} paper trades older than {days_old} days")
            response = input("Remove them? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
            
            result = trades_collection.delete_many(query)
            print(f"\n✅ Removed {result.deleted_count} paper trading positions")
            
        else:
            # Default: Remove CLOSED paper trades only
            query = {
                "paper_trading": True,
                "status": "CLOSED"
            }
            
            count = trades_collection.count_documents(query)
            if count == 0:
                print("\n✅ No closed paper trades to clean up")
                return
            
            print(f"\n⚠️  Found {count} CLOSED paper trades")
            response = input("Remove them? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
            
            result = trades_collection.delete_many(query)
            print(f"\n✅ Removed {result.deleted_count} closed paper trading positions")
        
        # Show remaining paper trades
        remaining = trades_collection.count_documents({"paper_trading": True})
        print(f"\n📊 Remaining paper trades: {remaining}")
        
        if remaining > 0:
            open_count = trades_collection.count_documents({"paper_trading": True, "status": "OPEN"})
            closed_count = trades_collection.count_documents({"paper_trading": True, "status": "CLOSED"})
            print(f"   - OPEN: {open_count}")
            print(f"   - CLOSED: {closed_count}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()


def list_paper_trades():
    """List all paper trading positions."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        trades = list(trades_collection.find({"paper_trading": True}).sort("entry_timestamp", -1))
        
        if not trades:
            print("\n✅ No paper trades found")
            return
        
        print("=" * 60)
        print(f"Paper Trading Positions ({len(trades)} total)")
        print("=" * 60)
        
        for trade in trades:
            trade_id = trade.get("trade_id", "Unknown")
            status = trade.get("status", "Unknown")
            signal = trade.get("signal", "Unknown")
            entry_price = trade.get("entry_price", 0)
            quantity = trade.get("quantity", 0)
            entry_time = trade.get("entry_timestamp", "Unknown")
            
            # Truncate timestamp
            if isinstance(entry_time, str) and len(entry_time) > 19:
                entry_time = entry_time[:19]
            
            status_icon = "🟢" if status == "OPEN" else "🔴"
            signal_icon = "📈" if signal == "BUY" else "📉" if signal == "SELL" else "📊"
            
            print(f"\n{status_icon} {trade_id}")
            print(f"   Status: {status}")
            print(f"   Signal: {signal_icon} {signal}")
            print(f"   Entry: ${entry_price:,.2f} x {quantity}")
            print(f"   Time: {entry_time}")
            
            if status == "CLOSED":
                exit_price = trade.get("exit_price", 0)
                pnl = trade.get("pnl", 0)
                pnl_icon = "✅" if pnl >= 0 else "❌"
                print(f"   Exit: ${exit_price:,.2f}")
                print(f"   P&L: {pnl_icon} ${pnl:,.2f}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error listing trades: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup paper trading data")
    parser.add_argument("--list", action="store_true", help="List all paper trades")
    parser.add_argument("--clean-closed", action="store_true", help="Remove CLOSED paper trades")
    parser.add_argument("--clean-old", type=int, metavar="DAYS", help="Remove trades older than N days")
    parser.add_argument("--clean-all", action="store_true", help="Remove ALL paper trades (use with caution!)")
    
    args = parser.parse_args()
    
    if args.list:
        list_paper_trades()
    elif args.clean_all:
        cleanup_paper_trades(all_trades=True)
    elif args.clean_old:
        cleanup_paper_trades(days_old=args.clean_old)
    elif args.clean_closed:
        cleanup_paper_trades()
    else:
        # Default: list trades
        print("Usage examples:")
        print("  python scripts/cleanup_paper_trades.py --list          # List all paper trades")
        print("  python scripts/cleanup_paper_trades.py --clean-closed  # Remove closed trades")
        print("  python scripts/cleanup_paper_trades.py --clean-old 2   # Remove trades older than 2 days")
        print("  python scripts/cleanup_paper_trades.py --clean-all     # Remove ALL paper trades")
        print()
        list_paper_trades()
