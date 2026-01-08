"""Mode management for trading system with auto-switching based on market hours."""

import os
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from core_kernel.src.core_kernel.market_hours import is_market_open, get_suggested_mode


# Mode configuration file path
MODE_CONFIG_FILE = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))) / ".mode_config.json"


class ModeManager:
    """Manages trading mode with auto-switching and manual override support."""
    
    def __init__(self):
        self._current_mode = os.getenv("TRADING_MODE", "paper_mock")
        # Load full config first
        self._config_cache = self._read_full_config()
        self._manual_override = self._config_cache.get("manual_override")
        self._last_switch_time = None
    
    def _read_full_config(self) -> dict:
        """Read the full configuration file."""
        try:
            if MODE_CONFIG_FILE.exists():
                import json
                with open(MODE_CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _write_full_config(self, config: dict):
        """Write the full configuration file."""
        try:
            import json
            MODE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MODE_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            self._config_cache = config
        except Exception as e:
            print(f"Warning: Could not save config: {str(e)}")

    def _load_manual_override(self) -> Optional[str]:
        """Load manual mode override from config file."""
        return self._read_full_config().get("manual_override")
    
    def _save_manual_override(self, mode: Optional[str]):
        """Save manual mode override to config file."""
        config = self._read_full_config()
        config["manual_override"] = mode
        self._write_full_config(config)

    def save_historical_config(self, start_date: str, end_date: Optional[str], interval: str):
        """Save historical replay configuration."""
        config = self._read_full_config()
        config["historical_replay"] = {
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval
        }
        self._write_full_config(config)

    def get_historical_config(self) -> dict:
        """Get historical replay configuration."""
        return self._config_cache.get("historical_replay", {})
    
    def get_current_mode(self) -> str:
        """Get current active mode."""
        return self._current_mode
    
    def has_manual_override(self) -> bool:
        """Check if user has manually set a mode."""
        return self._manual_override is not None
    
    def get_manual_override(self) -> Optional[str]:
        """Get manually set mode if exists."""
        return self._manual_override
    
    def set_manual_mode(self, mode: str, require_confirmation: bool = False) -> Tuple[bool, str]:
        """
        Set mode manually (user override).
        
        Args:
            mode: Mode to set (paper_mock, paper_live, live)
            require_confirmation: If True and mode is 'live', requires confirmation
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        if mode not in ["paper_mock", "paper_live", "live"]:
            return False, f"Invalid mode: {mode}"
        
        if mode == "live" and require_confirmation:
            return False, "CONFIRMATION_REQUIRED"
        
        self._current_mode = mode
        self._manual_override = mode
        self._last_switch_time = datetime.now()
        self._save_manual_override(mode)
        
        return True, f"Mode set to {mode}"
    
    def clear_manual_override(self):
        """Clear manual override to allow auto-switching."""
        self._manual_override = None
        self._save_manual_override(None)
    
    def check_auto_switch(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if mode should auto-switch based on market hours.
        
        Returns:
            Tuple of (should_switch: bool, suggested_mode: str, reason: str)
        """
        # If manual override exists, don't auto-switch
        if self._manual_override is not None:
            return False, None, "Manual override active"
        
        suggested = get_suggested_mode()
        current = self._current_mode
        
        # Determine if we should switch
        if suggested == "paper_live" and current == "paper_mock":
            return True, "paper_live", "Market is open - switching to live data"
        elif suggested == "paper_mock" and current in ["paper_live", "live"]:
            return True, "paper_mock", "Market is closed - switching to mock data"
        
        return False, None, "No switch needed"
    
    def auto_switch(self, require_confirmation_for_live: bool = True) -> Tuple[bool, str, Optional[str]]:
        """
        Perform auto-switch if needed.
        
        Args:
            require_confirmation_for_live: If True, requires confirmation when switching to live mode
        
        Returns:
            Tuple of (switched: bool, new_mode: str, confirmation_required: Optional[str])
        """
        should_switch, suggested_mode, reason = self.check_auto_switch()
        
        if not should_switch:
            return False, self._current_mode, None
        
        # If switching to live mode, check if confirmation needed
        if suggested_mode in ["paper_live", "live"] and require_confirmation_for_live:
            # For paper_live, we can auto-switch
            # For live, we need confirmation
            if suggested_mode == "live":
                return False, self._current_mode, "CONFIRMATION_REQUIRED"
        
        # Perform the switch
        old_mode = self._current_mode
        self._current_mode = suggested_mode
        self._last_switch_time = datetime.now()
        
        return True, suggested_mode, None
    
    def get_mode_info(self) -> dict:
        """Get comprehensive mode information."""
        is_open = is_market_open()
        suggested = get_suggested_mode()
        should_switch, suggested_mode, reason = self.check_auto_switch()
        
        return {
            "current_mode": self._current_mode,
            "manual_override": self._manual_override,
            "has_manual_override": self.has_manual_override(),
            "market_open": is_open,
            "suggested_mode": suggested,
            "should_auto_switch": should_switch,
            "auto_switch_suggested": suggested_mode,
            "auto_switch_reason": reason,
            "last_switch_time": self._last_switch_time.isoformat() if self._last_switch_time else None
        }


# Global instance
_mode_manager = None


def get_mode_manager() -> ModeManager:
    """Get global mode manager instance."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ModeManager()
    return _mode_manager


