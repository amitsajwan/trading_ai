"""
Usage Monitor for Multi-Provider LLM System
Monitors and reports API usage statistics
"""

import logging
from datetime import datetime
from typing import Optional
from scripts.utils.request_router import RequestRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UsageMonitor:
    """Monitor and report API usage statistics"""
    
    def __init__(self):
        self.router = RequestRouter()
    
    def print_usage_report(self, avg_tokens_per_day: int = 10000):
        """Print detailed usage report"""
        stats = self.router.get_stats()
        estimates = self.router.estimate_lifespan(avg_tokens_per_day)
        
        print("\n" + "="*70)
        print(f"📊 API USAGE REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Separate providers with and without keys
        active_providers = {}
        inactive_providers = {}
        
        for provider, info in stats.items():
            if info['has_key']:
                active_providers[provider] = info
            else:
                inactive_providers[provider] = info
        
        # Display active providers
        if active_providers:
            print("\n🟢 ACTIVE PROVIDERS (with API keys):")
            print("-" * 70)
            
            for provider, info in sorted(active_providers.items(), key=lambda x: x[1]['priority']):
                status = self._get_status_emoji(info['usage_percent'])
                print(f"\n{status} {provider.upper()} (Priority: {info['priority']}) - Model: {info['model']}")
                print(f"   Usage: {info['usage']:,} / {info['limit']:,} tokens")
                print(f"   Remaining: {info['remaining']:,} tokens ({100 - info['usage_percent']:.1f}% left)")
                print(f"   Reset Period: {info['reset_period']}")
                print(f"   Estimate: {estimates.get(provider, 'N/A')}")
                
                # Progress bar
                bar_length = 50
                filled = int(bar_length * info['usage_percent'] / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"   [{bar}] {info['usage_percent']:.1f}%")
        
        # Display inactive providers
        if inactive_providers:
            print("\n🔴 INACTIVE PROVIDERS (no API keys):")
            print("-" * 70)
            for provider in sorted(inactive_providers.keys()):
                print(f"   ❌ {provider.upper()}")
        
        # Display total estimate
        total_estimate = estimates.get("TOTAL_ESTIMATED_DAYS", "N/A")
        print("\n" + "="*70)
        print(f"   {total_estimate}")
        print(f"   (Based on {avg_tokens_per_day:,} tokens/day usage)")
        print("="*70 + "\n")
    
    def _get_status_emoji(self, usage_percent: float) -> str:
        """Get status emoji based on usage percentage"""
        if usage_percent >= 90:
            return "🔴"
        elif usage_percent >= 75:
            return "🟡"
        elif usage_percent >= 50:
            return "🟠"
        else:
            return "🟢"
    
    def check_alerts(self) -> list:
        """Check for usage alerts"""
        stats = self.router.get_stats()
        alerts = []
        
        for provider, info in stats.items():
            if not info['has_key']:
                continue
                
            if info['usage_percent'] >= 95:
                alerts.append(f"🚨 CRITICAL: {provider} usage at {info['usage_percent']:.1f}%!")
            elif info['usage_percent'] >= 90:
                alerts.append(f"⚠️  WARNING: {provider} usage at {info['usage_percent']:.1f}%")
            elif info['usage_percent'] >= 75:
                alerts.append(f"⚡ NOTICE: {provider} usage at {info['usage_percent']:.1f}%")
        
        if alerts:
            print("\n🔔 USAGE ALERTS:")
            print("-" * 70)
            for alert in alerts:
                print(f"   {alert}")
            print("-" * 70 + "\n")
        
        return alerts
    
    def print_compact_report(self):
        """Print a compact one-line report for each provider"""
        stats = self.router.get_stats()
        
        print("\n📊 Quick Status:")
        for provider, info in sorted(stats.items(), key=lambda x: x[1]['priority']):
            if info['has_key']:
                status = self._get_status_emoji(info['usage_percent'])
                print(f"   {status} {provider:12s} | {info['usage_percent']:5.1f}% | "
                      f"{info['remaining']:>10,} tokens left | {info['reset_period']}")
        print()
    
    def get_best_provider(self) -> Optional[str]:
        """Get the name of the best available provider"""
        try:
            available = self.router.api_manager.get_available_providers("llm")
            if available:
                return available[0][0]  # Return name of first (highest priority) provider
        except Exception as e:
            logger.error(f"Error getting best provider: {e}")
        return None
    
    def export_usage_report(self, filename: str = "usage_report.txt"):
        """Export usage report to a file"""
        import sys
        from io import StringIO
        
        # Capture print output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        self.print_usage_report()
        self.check_alerts()
        
        report = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Write to file
        try:
            with open(filename, 'w') as f:
                f.write(report)
            print(f"✅ Usage report exported to {filename}")
        except Exception as e:
            logger.error(f"❌ Error exporting report: {e}")


def main():
    """Main function for standalone usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor API usage")
    parser.add_argument(
        "--avg-tokens", 
        type=int, 
        default=10000,
        help="Average tokens used per day (for estimation)"
    )
    parser.add_argument(
        "--compact", 
        action="store_true",
        help="Show compact report"
    )
    parser.add_argument(
        "--export", 
        type=str,
        help="Export report to file"
    )
    
    args = parser.parse_args()
    
    monitor = UsageMonitor()
    
    if args.compact:
        monitor.print_compact_report()
    else:
        monitor.print_usage_report(args.avg_tokens)
    
    monitor.check_alerts()
    
    if args.export:
        monitor.export_usage_report(args.export)


if __name__ == "__main__":
    main()

