#!/usr/bin/env python3
"""Create sample LLM usage data for analytics."""

from pymongo import MongoClient
from datetime import datetime, timedelta
import random

def create_llm_usage_data():
    """Create sample LLM usage data."""

    client = MongoClient('mongodb://localhost:27017/')
    db = client.zerodha_trading
    col = db.llm_usage

    # Clear existing data
    col.delete_many({})
    print("Cleared existing LLM usage data")

    # Create sample LLM usage over the last 30 days
    usage_records = []
    base_date = datetime.now() - timedelta(days=30)

    providers = ['groq', 'openai', 'anthropic', 'cohere']
    models = ['llama-3.1-8b-instant', 'gpt-4', 'claude-3-haiku', 'command-r']

    print("Generating LLM usage records...")
    for i in range(150):  # 150 API calls
        call_date = base_date + timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

        provider = random.choice(providers)
        model = random.choice(models)

        # Simulate different usage patterns
        tokens_used = random.randint(100, 2000)
        cost = tokens_used * random.uniform(0.0001, 0.002)  # Cost per token

        record = {
            'timestamp': call_date.isoformat(),
            'provider': provider,
            'model': model,
            'tokens_used': tokens_used,
            'cost': round(cost, 6),
            'endpoint': random.choice(['chat/completions', 'completions', 'embeddings']),
            'status': 'success' if random.random() > 0.05 else 'error',  # 95% success rate
            'response_time_ms': random.randint(200, 3000),
            'user_type': random.choice(['agent', 'dashboard', 'api'])
        }
        usage_records.append(record)

    # Insert usage records
    if usage_records:
        result = col.insert_many(usage_records)
        print(f'Successfully inserted {len(result.inserted_ids)} LLM usage records')

        # Calculate summary
        total_tokens = sum(r['tokens_used'] for r in usage_records)
        total_cost = sum(r['cost'] for r in usage_records)
        avg_response_time = sum(r['response_time_ms'] for r in usage_records) / len(usage_records)

        print("\n=== LLM USAGE SUMMARY ===")
        print(f'Total tokens used: {total_tokens:,}')
        print(f'Total cost: ${total_cost:.4f}')
        print(f'Average response time: {avg_response_time:.0f}ms')

        # Provider breakdown
        provider_usage = {}
        for record in usage_records:
            provider = record['provider']
            if provider not in provider_usage:
                provider_usage[provider] = {'calls': 0, 'tokens': 0, 'cost': 0}
            provider_usage[provider]['calls'] += 1
            provider_usage[provider]['tokens'] += record['tokens_used']
            provider_usage[provider]['cost'] += record['cost']

        print("\n=== PROVIDER BREAKDOWN ===")
        for provider, stats in provider_usage.items():
            print(f'{provider}: {stats["calls"]} calls, {stats["tokens"]:,} tokens, ${stats["cost"]:.4f}')

if __name__ == '__main__':
    create_llm_usage_data()