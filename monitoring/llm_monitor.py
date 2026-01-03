"""LLM monitoring utilities: watches provider status and token usage and emits alerts."""

import logging
from typing import Dict, Any
from mongodb_schema import get_mongo_client, get_collection
from agents.llm_provider_manager import get_llm_manager
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMMonitor:
    """Simple monitor for LLM providers."""

    def __init__(self, db_name: str = None):
        self.manager = get_llm_manager()
        self.db_name = db_name or settings.mongodb_db_name

    def check(self):
        """Check provider statuses and emit alerts when something looks wrong."""
        status = self.manager.get_provider_status()
        mc = get_mongo_client()
        db = mc[self.db_name]
        alerts = get_collection(db, 'alerts')

        for name, info in status.items():
            # Skip multi_provider_fallback pseudo entry
            if name == 'multi_provider_fallback':
                continue

            # 1) Provider degraded/unavailable
            if info.get('status') != 'available':
                alerts.insert_one({
                    'type': 'llm_provider_unavailable',
                    'provider': name,
                    'status': info.get('status'),
                    'message': f"Provider {name} status: {info.get('status')}",
                    'timestamp': __import__('datetime').datetime.now().isoformat()
                })
                logger.warning(f"Alert: Provider {name} status {info.get('status')}")

            # 2) Token usage approaching quota
            tokens = info.get('tokens_today', 0)
            quota = info.get('daily_token_quota')
            if quota and quota > 0:
                pct = tokens / quota
                if pct >= 0.9:
                    alerts.insert_one({
                        'type': 'llm_token_quota_near',
                        'provider': name,
                        'tokens_today': tokens,
                        'quota': quota,
                        'percent': pct,
                        'message': f"Provider {name} tokens used {tokens}/{quota} ({pct:.2%})",
                        'timestamp': __import__('datetime').datetime.now().isoformat()
                    })
                    logger.warning(f"Alert: Provider {name} nearing token quota: {tokens}/{quota} ({pct:.2%})")

        return status
