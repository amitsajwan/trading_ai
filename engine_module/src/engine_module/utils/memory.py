"""Memory system for agents to learn from past decisions."""

import chromadb
from chromadb.config import Settings
from typing import Dict, Any, List, Optional
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentMemory:
    """ChromaDB-based memory for agents to store and retrieve past experiences."""

    def __init__(self, agent_name: str, persist_directory: str = "./agent_memory"):
        """Initialize memory for a specific agent."""
        self.agent_name = agent_name
        self.persist_directory = os.path.join(persist_directory, agent_name)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(f"{agent_name}_memory")
        except:
            self.collection = self.client.create_collection(f"{agent_name}_memory")

    def store_experience(self, situation: str, decision: str, outcome: str,
                        confidence: float, metadata: Dict[str, Any] = None):
        """Store a past experience."""
        try:
            doc_id = f"{self.agent_name}_{datetime.now().isoformat()}"

            document = f"Situation: {situation}\nDecision: {decision}\nOutcome: {outcome}"

            meta = {
                "agent": self.agent_name,
                "decision": decision,
                "outcome": outcome,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat()
            }
            if metadata:
                meta.update(metadata)

            self.collection.add(
                documents=[document],
                metadatas=[meta],
                ids=[doc_id]
            )

            logger.debug(f"Stored experience for {self.agent_name}: {decision} -> {outcome}")

        except Exception as e:
            logger.warning(f"Failed to store experience: {e}")

    def retrieve_similar(self, current_situation: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Retrieve similar past experiences."""
        try:
            results = self.collection.query(
                query_texts=[current_situation],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

            experiences = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i]
                    distance = results["distances"][0][i]

                    experiences.append({
                        "document": doc,
                        "metadata": meta,
                        "similarity": 1 - distance  # Convert distance to similarity
                    })

            return experiences

        except Exception as e:
            logger.warning(f"Failed to retrieve experiences: {e}")
            return []

    def get_recent_experiences(self, n_results: int = 5) -> List[Dict[str, Any]]:
        """Get most recent experiences."""
        try:
            # Get all and sort by timestamp
            results = self.collection.get(include=["documents", "metadatas"])

            if not results["metadatas"]:
                return []

            # Sort by timestamp
            experiences = []
            for i, meta in enumerate(results["metadatas"]):
                experiences.append({
                    "document": results["documents"][i],
                    "metadata": meta
                })

            experiences.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)

            return experiences[:n_results]

        except Exception as e:
            logger.warning(f"Failed to get recent experiences: {e}")
            return []


class FinancialSituationMemory:
    """Specialized memory for financial situations and trading decisions."""

    def __init__(self, persist_directory: str = "./financial_memory"):
        """Initialize financial memory."""
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )

        try:
            self.collection = self.client.get_collection("financial_situations")
        except:
            self.collection = self.client.create_collection("financial_situations")

    def add_situation(self, situation: str, recommendation: str, outcome: str = None):
        """Add a financial situation and recommendation."""
        try:
            doc_id = f"situation_{datetime.now().isoformat()}"

            document = f"Situation: {situation}\nRecommendation: {recommendation}"
            if outcome:
                document += f"\nOutcome: {outcome}"

            metadata = {
                "situation": situation,
                "recommendation": recommendation,
                "outcome": outcome,
                "timestamp": datetime.now().isoformat()
            }

            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id]
            )

        except Exception as e:
            logger.warning(f"Failed to add financial situation: {e}")

    def get_memories(self, current_situation: str, n_matches: int = 2) -> List[Dict[str, Any]]:
        """Get relevant memories for current situation."""
        try:
            results = self.collection.query(
                query_texts=[current_situation],
                n_results=n_matches,
                include=["documents", "metadatas", "distances"]
            )

            memories = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i]
                    memories.append({
                        "situation": meta["situation"],
                        "recommendation": meta["recommendation"],
                        "outcome": meta.get("outcome"),
                        "similarity": 1 - results["distances"][0][i]
                    })

            return memories

        except Exception as e:
            logger.warning(f"Failed to get memories: {e}")
            return []