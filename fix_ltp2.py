with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'r') as f:
    content = f.read()

# Find and replace just the main function
start = content.find('def main():')
end = content.find('if __name__ == "__main__":', start)

main_func = content[start:end]

# Comment out the market_memory initialization
main_func = main_func.replace('    try:', '    # try:')
main_func = main_func.replace('        if redis:', '        # if redis:')
main_func = main_func.replace('            redis_config = config.get_redis_config() if config else {', '            # redis_config = config.get_redis_config() if config else {')
main_func = main_func.replace('                "host": os.getenv("REDIS_HOST", "localhost"),', '                # "host": os.getenv("REDIS_HOST", "localhost"),')
main_func = main_func.replace('                "port": int(os.getenv("REDIS_PORT", "6379")),', '                # "port": int(os.getenv("REDIS_PORT", "6379")),')
main_func = main_func.replace('                "db": 0,', '                # "db": 0,')
main_func = main_func.replace('                "decode_responses": True', '                # "decode_responses": True')
main_func = main_func.replace('            }', '            # }')
main_func = main_func.replace('            redis_client = redis.Redis(**redis_config)', '            # redis_client = redis.Redis(**redis_config)')
main_func = main_func.replace('            from market_data.api import build_store', '            # from market_data.api import build_store')
main_func = main_func.replace('            market_memory = build_store(redis_client=redis_client)', '            # market_memory = build_store(redis_client=redis_client)')
main_func = main_func.replace('            print("[ltp] Initialized Redis-backed market store")', '            # print("[ltp] Initialized Redis-backed market store")')
main_func = main_func.replace('    except Exception as e:', '    # except Exception as e:')
main_func = main_func.replace('        print(f"[ltp] Failed to initialize market store: {e}")', '        # print(f"[ltp] Failed to initialize market store: {e}")')
main_func = main_func.replace('        market_memory = None', '        # market_memory = None')

content = content[:start] + main_func + content[end:]

with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'w') as f:
    f.write(content)

print('Main function updated')