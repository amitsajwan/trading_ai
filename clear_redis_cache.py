#!/usr/bin/env python3
"""Redis cache cleanup utility for mode switching.

This script clears market data from Redis to prevent contamination
between different runs, modes, or dates.

Usage:
    python clear_redis_cache.py --all              # Clear everything
    python clear_redis_cache.py --market-data      # Clear only market data
    python clear_redis_cache.py --keep-auth        # Clear all except auth
"""

import argparse
import redis
import sys
from datetime import datetime


class RedisCacheCleaner:
    """Clean Redis cache with different strategies."""
    
    def __init__(self, host='localhost', port=6379):
        """Initialize Redis connection."""
        try:
            self.redis = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            self.redis.ping()
            print(f"✅ Connected to Redis at {host}:{port}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            sys.exit(1)
    
    def clear_all(self):
        """Clear entire Redis database."""
        print("\n🧹 CLEARING ALL REDIS DATA...")
        try:
            self.redis.flushdb()
            print("✅ All data cleared")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def clear_market_data(self):
        """Clear only market data, keep system state."""
        print("\n🧹 CLEARING MARKET DATA...")
        
        patterns = [
            "ohlc:*",
            "ohlc_sorted:*",
            "depth:*",
            "indicators:*",
            "price:*",
            "volume:*",
            "tick:*",
            "options:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            keys = self.redis.keys(pattern)
            if keys:
                deleted = self.redis.delete(*keys)
                total_deleted += deleted
                print(f"  ✅ Deleted {deleted} keys matching '{pattern}'")
            else:
                print(f"  ℹ️  No keys found for '{pattern}'")
        
        print(f"\n✅ Total keys deleted: {total_deleted}")
        return True
    
    def clear_keep_auth(self):
        """Clear all data except authentication."""
        print("\n🧹 CLEARING ALL DATA (keeping auth)...")
        
        # Get auth keys first
        auth_keys = self.redis.keys("auth:*")
        cred_keys = self.redis.keys("credentials:*")
        keep_keys = set(auth_keys + cred_keys)
        
        print(f"ℹ️  Keeping {len(keep_keys)} authentication keys")
        
        # Get all keys
        all_keys = set(self.redis.keys("*"))
        
        # Delete everything except auth keys
        delete_keys = all_keys - keep_keys
        if delete_keys:
            deleted = self.redis.delete(*delete_keys)
            print(f"✅ Deleted {deleted} keys")
        else:
            print("ℹ️  No keys to delete")
        
        return True
    
    def clear_run_specific(self, run_id):
        """Clear data for specific run_id."""
        print(f"\n🧹 CLEARING DATA FOR RUN: {run_id}...")
        
        # This would require data to be tagged with run_id
        # For now, this is a placeholder
        print("ℹ️  Run-specific cleanup not yet implemented")
        print("   Data storage doesn't currently tag with run_id")
        return False
    
    def show_stats(self):
        """Show current Redis statistics."""
        print("\n📊 REDIS CACHE STATISTICS:")
        
        patterns = {
            "OHLC Data": "ohlc:*",
            "OHLC Sorted Sets": "ohlc_sorted:*",
            "Depth Data": "depth:*",
            "Indicators": "indicators:*",
            "Price Data": "price:*",
            "Volume Data": "volume:*",
            "Tick Data": "tick:*",
            "Options Data": "options:*",
            "Auth Data": "auth:*",
            "System State": "system:*"
        }
        
        total_keys = 0
        for name, pattern in patterns.items():
            count = len(self.redis.keys(pattern))
            total_keys += count
            if count > 0:
                print(f"  • {name}: {count} keys")
        
        print(f"\n  📦 Total Keys: {total_keys}")
        
        # Show current mode
        mode = self.redis.get("system:execution_mode")
        run_id = self.redis.get("system:run_id")
        if mode:
            print(f"  🔧 Current Mode: {mode}")
        if run_id:
            print(f"  🆔 Current Run ID: {run_id}")
        
        # Memory usage
        info = self.redis.info('memory')
        memory_mb = info.get('used_memory', 0) / (1024 * 1024)
        print(f"  💾 Memory Used: {memory_mb:.2f} MB")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean Redis cache for market data system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clear_redis_cache.py --stats              # Show current stats
  python clear_redis_cache.py --market-data        # Clear market data only
  python clear_redis_cache.py --keep-auth          # Clear all except auth
  python clear_redis_cache.py --all --yes          # Clear everything (no prompt)
  
  # Docker usage:
  docker exec zerodha-redis redis-cli FLUSHDB     # Clear all via Docker
        """
    )
    
    parser.add_argument('--host', default='localhost', help='Redis host (default: localhost)')
    parser.add_argument('--port', type=int, default=6379, help='Redis port (default: 6379)')
    
    # Cleanup options (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Clear entire Redis database')
    group.add_argument('--market-data', action='store_true', help='Clear only market data keys')
    group.add_argument('--keep-auth', action='store_true', help='Clear all except authentication')
    group.add_argument('--stats', action='store_true', help='Show cache statistics only')
    
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Initialize cleaner
    cleaner = RedisCacheCleaner(host=args.host, port=args.port)
    
    # Show stats first
    if args.stats:
        cleaner.show_stats()
        return
    
    # Show current state
    cleaner.show_stats()
    
    # Confirm before clearing
    if not args.yes:
        print("\n⚠️  WARNING: This will delete data from Redis!")
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled")
            return
    
    # Execute cleanup
    success = False
    if args.all:
        success = cleaner.clear_all()
    elif args.market_data:
        success = cleaner.clear_market_data()
    elif args.keep_auth:
        success = cleaner.clear_keep_auth()
    
    if success:
        print("\n" + "="*60)
        print("✅ CLEANUP COMPLETE")
        print("="*60)
        
        # Show new stats
        cleaner.show_stats()
    else:
        print("\n❌ Cleanup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
