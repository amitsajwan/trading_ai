"""FastAPI endpoints to expose provider health and token usage for genai_module."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .core.llm_provider_manager import get_llm_manager, ProviderStatus

router = APIRouter(prefix="/genai", tags=["genai"])


class ProviderInfo(BaseModel):
    name: str
    status: str
    is_current: bool
    requests_today: int
    requests_this_minute: int
    rate_limit_per_minute: int
    rate_limit_per_day: int
    tokens_today: int
    daily_token_quota: Optional[int]
    last_error: Optional[str]
    last_error_time: Optional[str]


class ProviderListResponse(BaseModel):
    providers: Dict[str, ProviderInfo]


class HealthResponse(BaseModel):
    provider: str
    healthy: bool
    last_error: Optional[str]


class UsageResponse(BaseModel):
    total_requests_today: int
    providers: Dict[str, Dict[str, Any]]


@router.get("/providers", response_model=Dict[str, Any])
def list_providers():
    mgr = get_llm_manager()
    try:
        status = mgr.get_provider_status()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return status


@router.get("/providers/{provider_name}/health", response_model=HealthResponse)
def provider_health(provider_name: str):
    mgr = get_llm_manager()
    if provider_name not in mgr.providers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    healthy = mgr.check_provider_health(provider_name)
    info = mgr.get_provider_status().get(provider_name, {})
    return HealthResponse(provider=provider_name, healthy=bool(healthy), last_error=info.get("last_error"))


@router.post("/providers/{provider_name}/check", response_model=HealthResponse)
def trigger_provider_check(provider_name: str):
    mgr = get_llm_manager()
    if provider_name not in mgr.providers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    healthy = mgr.check_provider_health(provider_name)
    info = mgr.get_provider_status().get(provider_name, {})
    # If provider recovered, ensure status updated
    current_status = mgr.providers[provider_name].status
    current_value = getattr(current_status, 'value', current_status)
    if healthy and current_value != ProviderStatus.AVAILABLE.value:
        mgr.providers[provider_name].status = ProviderStatus.AVAILABLE
    return HealthResponse(provider=provider_name, healthy=bool(healthy), last_error=info.get("last_error"))


@router.get("/usage", response_model=UsageResponse)
def usage():
    mgr = get_llm_manager()
    total = 0
    protos: Dict[str, Dict[str, Any]] = {}
    for name, cfg in mgr.providers.items():
        reqs = getattr(cfg, "requests_today", 0) or 0
        tokens = getattr(cfg, "tokens_today", 0) or 0
        quota = getattr(cfg, "daily_token_quota", None)
        protos[name] = {
            "requests_today": reqs,
            "tokens_today": tokens,
            "daily_token_quota": quota,
            "status": cfg.status.value
        }
        total += reqs
    return UsageResponse(total_requests_today=total, providers=protos)


# Helper to include genai status in global health endpoint
def get_health_fragment() -> Dict[str, Any]:
    """Return a minimal health fragment suitable for inclusion in /api/health.

    Example return value:
      {"genai": {"status": "ok", "providers": {"openai": {"status": "available"}}}}
    """
    mgr = get_llm_manager()
    providers = {}
    overall_ok = True
    try:
        stats = mgr.get_provider_status()
        for name, info in stats.items():
            if name == "multi_provider_fallback":
                continue
            providers[name] = {
                "status": info.get("status"),
                "last_error": info.get("last_error"),
                "is_current": info.get("is_current", False)
            }
            if info.get("status") != "available":
                overall_ok = False
    except Exception:
        # If we cannot query providers, mark genai as degraded
        return {"genai": {"status": "degraded", "error": "unreachable"}}

    return {"genai": {"status": "ok" if overall_ok else "degraded", "providers": providers}}

