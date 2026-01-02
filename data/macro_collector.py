"""Macro economic data collection service."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings

logger = logging.getLogger(__name__)


class MacroCollector:
    """
    Collects macro economic data:
    - RBI policy announcements
    - Banking sector metrics (NPA trends)
    - Inflation/IIP data
    - Liquidity conditions
    """
    
    def __init__(self):
        """Initialize macro collector."""
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.events_collection = get_collection(self.db, "market_events")
        self.strategy_collection = get_collection(self.db, "strategy_parameters")
    
    def store_rbi_rate(self, rate: float, announcement_date: datetime, notes: str = ""):
        """Store RBI repo rate announcement."""
        event = {
            "event_type": "RBI_ANNOUNCEMENT",
            "event_timestamp": announcement_date.isoformat(),
            "source": "RBI",
            "data": {
                "repo_rate": rate,
                "notes": notes
            },
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            self.events_collection.insert_one(event)
            
            # Also update strategy parameters
            self.strategy_collection.update_one(
                {"strategy_name": "macro_context"},
                {
                    "$set": {
                        "rbi_rate": rate,
                        "rbi_rate_updated": announcement_date.isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                },
                upsert=True
            )
            
            logger.info(f"Stored RBI rate: {rate}%")
        except Exception as e:
            logger.error(f"Error storing RBI rate: {e}")
    
    def store_inflation_data(self, cpi: float, wpi: Optional[float] = None, date: Optional[datetime] = None):
        """Store inflation data (CPI, WPI)."""
        if date is None:
            date = datetime.now()
        
        event = {
            "event_type": "MACRO_DATA",
            "event_timestamp": date.isoformat(),
            "source": "Government",
            "data": {
                "cpi": cpi,
                "wpi": wpi
            },
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            self.events_collection.insert_one(event)
            
            # Update strategy parameters
            self.strategy_collection.update_one(
                {"strategy_name": "macro_context"},
                {
                    "$set": {
                        "inflation_rate": cpi,
                        "inflation_updated": date.isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                },
                upsert=True
            )
            
            logger.info(f"Stored inflation data: CPI={cpi}%")
        except Exception as e:
            logger.error(f"Error storing inflation data: {e}")
    
    def store_npa_data(self, npa_ratio: float, date: Optional[datetime] = None):
        """Store banking sector NPA ratio."""
        if date is None:
            date = datetime.now()
        
        event = {
            "event_type": "MACRO_DATA",
            "event_timestamp": date.isoformat(),
            "source": "RBI",
            "data": {
                "npa_ratio": npa_ratio
            },
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            self.events_collection.insert_one(event)
            
            # Update strategy parameters
            self.strategy_collection.update_one(
                {"strategy_name": "macro_context"},
                {
                    "$set": {
                        "npa_ratio": npa_ratio,
                        "npa_updated": date.isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                },
                upsert=True
            )
            
            logger.info(f"Stored NPA ratio: {npa_ratio}%")
        except Exception as e:
            logger.error(f"Error storing NPA data: {e}")
    
    def get_latest_macro_context(self) -> Dict[str, Any]:
        """Get latest macro context from strategy parameters."""
        try:
            doc = self.strategy_collection.find_one({"strategy_name": "macro_context"})
            if doc:
                return {
                    "rbi_rate": doc.get("rbi_rate"),
                    "inflation_rate": doc.get("inflation_rate"),
                    "npa_ratio": doc.get("npa_ratio"),
                    "updated_at": doc.get("updated_at")
                }
        except Exception as e:
            logger.error(f"Error getting macro context: {e}")
        
        return {
            "rbi_rate": None,
            "inflation_rate": None,
            "npa_ratio": None,
            "updated_at": None
        }

