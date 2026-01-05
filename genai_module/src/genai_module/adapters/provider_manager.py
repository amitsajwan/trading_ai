"""Adapter: wrap legacy LLMProviderManager behind LLMClient protocol."""
import logging
from typing import Optional

from genai_module.contracts import LLMClient, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class ProviderManagerClient(LLMClient):
    """Thin adapter to use existing LLMProviderManager via LLMClient interface."""

    def __init__(self, manager, default_model: Optional[str] = None):
        self.manager = manager
        self.default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        # The legacy manager uses blocking calls; run in thread if needed
        from functools import partial
        import asyncio

        def _call():
            # Manager expects text prompt; model selection is handled internally
            resp_text, tokens_used, cost = self.manager.generate_text(
                request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                model_override=request.model or self.default_model,
            )
            return resp_text, tokens_used, cost

        loop = asyncio.get_event_loop()
        content, tokens_used, cost = await loop.run_in_executor(None, _call)
        return LLMResponse(content=content, tokens_used=tokens_used or 0, cost=cost)

    async def estimate_cost(self, request: LLMRequest) -> float:
        # If manager has a cost estimator, use it; else return 0.0
        est = getattr(self.manager, "estimate_cost", None)
        if callable(est):
            return float(est(request.prompt, model=request.model or self.default_model))
        return 0.0

    async def validate(self) -> bool:
        # Validate preferred provider if available
        validator = getattr(self.manager, "validate_primary_provider", None)
        if callable(validator):
            return bool(validator())
        # Fallback: always true
        return True
