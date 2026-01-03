"""
API Manager for Multi-Provider LLM System
Manages API keys, usage tracking, and automatic provider fallback
"""

import os
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIManager:
    """
    Manages multiple API providers with automatic fallback and usage tracking.
    Ensures efficient use of free-tier API limits.
    """
    
    def __init__(self, usage_file: str = "api_usage.json"):
        self.usage_file = Path(usage_file)
        
        # Helper function to clean API keys (remove quotes)
        def clean_key(key):
            if key:
                return key.strip().strip("'\"")
            return ""
        
        self.providers = {
            "cohere": {
                "key": clean_key(os.getenv("COHERE_API_KEY", "")),
                "limit": int(os.getenv("COHERE_LIMIT", 5000000)),  # tokens/month
                "usage": 0,
                "priority": 1,  # Highest priority (most generous free tier)
                "type": "llm",
                "cost_per_1k": 0,  # Free tier
                "reset_period": "monthly",
                "model": os.getenv("COHERE_MODEL", "command")
            },
            "ai21": {
                "key": clean_key(os.getenv("AI21_API_KEY", "")),
                "limit": int(os.getenv("AI21_LIMIT", 300000)),  # tokens/month
                "usage": 0,
                "priority": 2,
                "type": "llm",
                "cost_per_1k": 0,
                "reset_period": "monthly",
                "model": os.getenv("AI21_MODEL", "j2-mid")
            },
            "groq": {
                "key": clean_key(os.getenv("GROQ_API_KEY", "")),
                "limit": int(os.getenv("GROQ_LIMIT", 14400)),  # requests/day (free tier)
                "usage": 0,
                "priority": 3,
                "type": "llm",
                "cost_per_1k": 0,
                "reset_period": "daily",
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            },
            "huggingface": {
                "key": clean_key(os.getenv("HUGGINGFACE_API_KEY", "")),
                "limit": int(os.getenv("HUGGINGFACE_LIMIT", 30000)),  # tokens/month
                "usage": 0,
                "priority": 4,
                "type": "llm",
                "cost_per_1k": 0,
                "reset_period": "monthly",
                "model": "gpt2"
            },
            "openai": {
                "key": clean_key(os.getenv("OPENAI_API_KEY", "")),
                "limit": int(os.getenv("OPENAI_LIMIT", 5000)),  # tokens (free credit)
                "usage": 0,
                "priority": 5,  # Use last due to limited free credits
                "type": "llm",
                "cost_per_1k": 0.002,
                "reset_period": "once",
                "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            },
            "google": {
                "key": clean_key(os.getenv("GOOGLE_API_KEY", "")),
                "limit": int(os.getenv("GOOGLE_LIMIT", 5000)),  # requests/month
                "usage": 0,
                "priority": 6,
                "type": "nlp",
                "cost_per_1k": 0,
                "reset_period": "monthly",
                "model": "gemini-pro"
            }
        }
        
        self.usage_log = defaultdict(list)
        self.last_reset = datetime.now()
        self.load_usage()
    
    def load_usage(self):
        """Load usage data from file if exists"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    for provider, info in data.get("providers", {}).items():
                        if provider in self.providers:
                            self.providers[provider]["usage"] = info.get("usage", 0)
                    
                    last_reset_str = data.get("last_reset")
                    if last_reset_str:
                        self.last_reset = datetime.fromisoformat(last_reset_str)
                    
                logger.info("✅ Loaded usage data from file")
            except Exception as e:
                logger.error(f"❌ Error loading usage data: {e}")
        else:
            logger.info("📝 No existing usage file found, starting fresh")
    
    def save_usage(self):
        """Save usage data to file"""
        try:
            data = {
                "providers": {
                    name: {
                        "usage": info["usage"],
                        "limit": info["limit"],
                        "last_updated": datetime.now().isoformat()
                    }
                    for name, info in self.providers.items()
                },
                "last_reset": self.last_reset.isoformat()
            }
            with open(self.usage_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("💾 Saved usage data")
        except Exception as e:
            logger.error(f"❌ Error saving usage data: {e}")
    
    def reset_usage_if_needed(self):
        """Reset usage counters based on reset period"""
        now = datetime.now()
        
        # Daily reset
        if (now - self.last_reset).days >= 1:
            for provider, info in self.providers.items():
                if info["reset_period"] == "daily":
                    old_usage = info["usage"]
                    info["usage"] = 0
                    logger.info(f"🔄 Reset daily usage for {provider} (was: {old_usage})")
        
        # Monthly reset (first day of month)
        if now.month != self.last_reset.month or now.year != self.last_reset.year:
            for provider, info in self.providers.items():
                if info["reset_period"] == "monthly":
                    old_usage = info["usage"]
                    info["usage"] = 0
                    logger.info(f"🔄 Reset monthly usage for {provider} (was: {old_usage})")
            self.last_reset = now
            self.save_usage()
    
    def get_available_providers(self, task_type: str = "llm") -> List[Tuple[str, Dict]]:
        """Get list of available providers sorted by priority"""
        self.reset_usage_if_needed()
        
        available = []
        for name, info in self.providers.items():
            # Check if provider has a key and is available for the task type
            if (info["type"] == task_type and 
                info["key"] and 
                info["key"].strip() and
                info["usage"] < info["limit"]):
                available.append((name, info))
        
        # Sort by priority (lower number = higher priority)
        available.sort(key=lambda x: x[1]["priority"])
        return available
    
    def get_provider(self, task_type: str = "llm", preferred_provider: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Get the best available provider for a task
        Returns: (provider_name, api_key, model)
        """
        available = self.get_available_providers(task_type)
        
        if not available:
            raise Exception(f"❌ No available providers for task type: {task_type}")
        
        # If preferred provider is specified and available, use it
        if preferred_provider:
            for provider_name, provider_info in available:
                if provider_name == preferred_provider:
                    logger.info(f"🎯 Using preferred provider: {provider_name} (usage: {provider_info['usage']}/{provider_info['limit']})")
                    return provider_name, provider_info["key"], provider_info["model"]
            logger.warning(f"⚠️ Preferred provider '{preferred_provider}' not available, using fallback")
        
        # Use highest priority available provider
        provider_name, provider_info = available[0]
        logger.info(f"✅ Selected provider: {provider_name} (usage: {provider_info['usage']}/{provider_info['limit']})")
        return provider_name, provider_info["key"], provider_info["model"]
    
    def log_usage(self, provider: str, tokens_used: int):
        """Log usage for a provider"""
        if provider in self.providers:
            self.providers[provider]["usage"] += tokens_used
            self.usage_log[provider].append({
                "tokens": tokens_used,
                "timestamp": datetime.now().isoformat()
            })
            self.save_usage()
            
            # Log warning if approaching limit
            usage_percent = (self.providers[provider]["usage"] / self.providers[provider]["limit"]) * 100
            if usage_percent > 90:
                logger.warning(f"⚠️ {provider} usage CRITICAL: {usage_percent:.1f}% ({self.providers[provider]['usage']}/{self.providers[provider]['limit']})")
            elif usage_percent > 80:
                logger.warning(f"⚡ {provider} usage HIGH: {usage_percent:.1f}% ({self.providers[provider]['usage']}/{self.providers[provider]['limit']})")
            else:
                logger.debug(f"📊 {provider} usage: {usage_percent:.1f}% ({tokens_used} tokens)")
    
    def get_usage_stats(self) -> Dict:
        """Get usage statistics for all providers"""
        stats = {}
        for name, info in self.providers.items():
            usage_percent = (info["usage"] / info["limit"]) * 100 if info["limit"] > 0 else 0
            stats[name] = {
                "usage": info["usage"],
                "limit": info["limit"],
                "remaining": info["limit"] - info["usage"],
                "usage_percent": round(usage_percent, 2),
                "priority": info["priority"],
                "reset_period": info["reset_period"],
                "has_key": bool(info["key"] and info["key"].strip()),
                "model": info.get("model", "N/A")
            }
        return stats
    
    def estimate_remaining_days(self, avg_tokens_per_day: int = 10000) -> Dict:
        """Estimate how many days the API keys will last"""
        estimates = {}
        total_remaining_tokens = 0
        
        for name, info in self.providers.items():
            if not info["key"] or not info["key"].strip():
                estimates[name] = "No API key"
                continue
                
            if info["limit"] > 0 and info["usage"] < info["limit"]:
                remaining_tokens = info["limit"] - info["usage"]
                
                if info["reset_period"] == "daily":
                    estimates[name] = "♻️ Resets daily"
                    total_remaining_tokens += remaining_tokens  # Add one day worth
                elif info["reset_period"] == "monthly":
                    days = remaining_tokens / avg_tokens_per_day if avg_tokens_per_day > 0 else 0
                    estimates[name] = f"📅 {days:.1f} days"
                    total_remaining_tokens += remaining_tokens
                else:  # once
                    days = remaining_tokens / avg_tokens_per_day if avg_tokens_per_day > 0 else 0
                    estimates[name] = f"⏱️ {days:.1f} days (no reset)"
                    total_remaining_tokens += remaining_tokens
            else:
                estimates[name] = "❌ Exhausted"
        
        # Calculate total estimated days
        total_days = total_remaining_tokens / avg_tokens_per_day if avg_tokens_per_day > 0 else 0
        estimates["TOTAL_ESTIMATED_DAYS"] = f"🌟 ~{total_days:.0f} days total"
        
        return estimates
    
    def get_provider_info(self, provider_name: str) -> Optional[Dict]:
        """Get detailed info about a specific provider"""
        return self.providers.get(provider_name)
    
    def reset_provider_usage(self, provider_name: str):
        """Manually reset usage for a specific provider (for testing)"""
        if provider_name in self.providers:
            self.providers[provider_name]["usage"] = 0
            self.save_usage()
            logger.info(f"🔄 Manually reset usage for {provider_name}")
        else:
            logger.error(f"❌ Provider '{provider_name}' not found")
