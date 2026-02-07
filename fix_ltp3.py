with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'r') as f:
    content = f.read()

# Replace the main function
old_main = '''def main():
    """Main entry point for LTP processor."""
    print("[ltp] Starting LTP Data Processor...")

    # Initialize market memory
    market_memory = None
    # try:
        if redis:
            redis_config = config.get_redis_config() if config else {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": 0,
                "decode_responses": True
            }
            redis_client = redis.Redis(**redis_config)
            from market_data.api import build_store
            market_memory = build_store(redis_client=redis_client)
            print("[ltp] Initialized Redis-backed market store")
    except Exception as e:
        print(f"[ltp] Failed to initialize market store: {e}")
        market_memory = None

    processor = LTPDataProcessor(market_memory)
    processor.start_processing()'''

new_main = '''def main():
    """Main entry point for LTP processor."""
    print("[ltp] Starting LTP Data Processor...")

    # Initialize market memory - disabled to prevent RedisMarketStore errors
    market_memory = None

    processor = LTPDataProcessor(market_memory)
    processor.start_processing()'''

content = content.replace(old_main, new_main)

with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'w') as f:
    f.write(content)

print('Main function simplified')