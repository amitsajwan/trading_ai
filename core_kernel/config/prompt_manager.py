"""Prompt management system for version control and updates."""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from mongodb_schema import get_mongo_client, get_collection
from core_kernel.config.settings import settings

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages system prompts with version control."""
    
    def __init__(self):
        """Initialize prompt manager."""
        self.prompts_dir = Path(__file__).parent / "prompts"
        self.prompts_dir.mkdir(exist_ok=True)
        
        # MongoDB connection
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client[settings.mongodb_db_name]
        self.prompts_collection = get_collection(self.db, "strategy_parameters")
    
    def get_prompt(self, agent_name: str, version: Optional[str] = None) -> str:
        """Get prompt for an agent, optionally by version."""
        # Try to load from file first
        prompt_file = self.prompts_dir / f"{agent_name}.txt"
        if prompt_file.exists():
            return prompt_file.read_text()
        
        # Fallback to MongoDB
        query = {"agent_name": agent_name}
        if version:
            query["version"] = version
        
        doc = self.prompts_collection.find_one(query, sort=[("updated_at", -1)])
        if doc:
            return doc.get("prompt_text", "")
        
        # Default fallback
        logger.warning(f"No prompt found for {agent_name}, using default")
        return f"Default prompt for {agent_name}"
    
    def save_prompt(self, agent_name: str, prompt_text: str, version: Optional[str] = None) -> None:
        """Save prompt to file and MongoDB."""
        # Save to file
        prompt_file = self.prompts_dir / f"{agent_name}.txt"
        prompt_file.write_text(prompt_text)
        
        # Save to MongoDB
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        doc = {
            "agent_name": agent_name,
            "version": version,
            "prompt_text": prompt_text,
            "updated_at": datetime.now().isoformat()
        }
        
        self.prompts_collection.insert_one(doc)
        logger.info(f"Saved prompt for {agent_name}, version {version}")
    
    def update_prompt_from_learning(self, agent_name: str, improvement_suggestion: str) -> str:
        """Update prompt based on learning agent feedback."""
        current_prompt = self.get_prompt(agent_name)
        
        # Use LLM to refine prompt (simplified - in production, use actual LLM call)
        # For now, just append improvement suggestion
        updated_prompt = f"{current_prompt}\n\n# Recent Improvement:\n{improvement_suggestion}"
        
        self.save_prompt(agent_name, updated_prompt)
        return updated_prompt
    
    def list_versions(self, agent_name: str) -> List[Dict[str, Any]]:
        """List all versions of a prompt."""
        docs = list(self.prompts_collection.find(
            {"agent_name": agent_name},
            sort=[("updated_at", -1)]
        ))
        
        return [
            {
                "version": doc.get("version"),
                "updated_at": doc.get("updated_at")
            }
            for doc in docs
        ]


