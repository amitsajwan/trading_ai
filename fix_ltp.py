import re

with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'r') as f:
    content = f.read()

# Comment out the market_memory initialization
content = re.sub(r'    try:', '    # try:', content)
content = re.sub(r'        if redis:', '        # if redis:', content)
content = re.sub(r'            redis_config = config\.get_redis_config\(\) if config else \{', '            # redis_config = config.get_redis_config() if config else {', content)
content = re.sub(r'                "host": os\.getenv\("REDIS_HOST", "localhost"\),', '                # "host": os.getenv("REDIS_HOST", "localhost"),', content)
content = re.sub(r'                "port": int\(os\.getenv\("REDIS_PORT", "6379"\)\),', '                # "port": int(os.getenv("REDIS_PORT", "6379")),', content)
content = re.sub(r'                "db": 0,', '                # "db": 0,', content)
content = re.sub(r'                "decode_responses": True', '                # "decode_responses": True', content)
content = re.sub(r'            \}', '            # }', content)
content = re.sub(r'            redis_client = redis\.Redis\(\*\*redis_config\)', '            # redis_client = redis.Redis(**redis_config)', content)
content = re.sub(r'            from market_data\.api import build_store', '            # from market_data.api import build_store', content)
content = re.sub(r'            market_memory = build_store\(redis_client=redis_client\)', '            # market_memory = build_store(redis_client=redis_client)', content)
content = re.sub(r'            print\("\[ltp\] Initialized Redis-backed market store"\)', '            # print("[ltp] Initialized Redis-backed market store")', content)
content = re.sub(r'    except Exception as e:', '    # except Exception as e:', content)
content = re.sub(r'        print\(f"\[ltp\] Failed to initialize market store: \{e\}"\)', '        # print(f"[ltp] Failed to initialize market store: {e}")', content)
content = re.sub(r'        market_memory = None', '        # market_memory = None', content)

with open('/app/market_data/src/market_data/collectors/ltp_collector.py', 'w') as f:
    f.write(content)

print('File updated successfully')