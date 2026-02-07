#!/usr/bin/env python3
"""
STARTUP VALIDATOR: Prevent mode contamination every time system starts

This script runs automatically to:
1. Validate mode configuration
2. Prevent mock/real mixing
3. Warn about inconsistencies
4. Auto-fix safe errors
"""

import json
import sys
import os
from pathlib import Path

class ModeValidator:
    """Validate and enforce mode configuration rules"""
    
    VALID_COMBINATIONS = {
        # (mode, manual_override) tuples
        ('historical', 'paper_real'): 'Real historical data only - SAFE',
        ('live', 'live'): 'Real live trading - SAFE',
        ('mock', 'paper_mock'): 'Mock environment - SAFE for testing',
        ('paper', 'paper_real'): 'Paper trading with real historical data',
        ('paper', 'paper_mock'): 'Paper trading with mock data',
    }
    
    INVALID_COMBINATIONS = {
        # Mode combos that MUST be blocked
        ('historical', 'paper_mock'): 'CRITICAL: Mock data in historical mode!',
        ('live', 'paper_mock'): 'CRITICAL: Mock data in live mode!',
        ('mock', 'paper_real'): 'CRITICAL: Real data in mock mode!',
        ('historical', 'live'): 'CRITICAL: Live mode in historical!',
    }
    
    AUTO_FIX = {
        # Can be auto-fixed
        ('historical', 'paper_mock'): 'paper_real',
        ('live', 'paper_mock'): 'live',
        ('mock', 'paper_real'): 'paper_mock',
        ('historical', 'live'): 'paper_real',
    }
    
    def __init__(self, config_path='.mode_config.json'):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.warnings = []
        self.errors = []
        self.fixed = []
    
    def _load_config(self):
        """Load mode configuration"""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except Exception as e:
            self.errors.append(f"Cannot read config: {e}")
            return {}
    
    def _save_config(self):
        """Save mode configuration"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            self.errors.append(f"Cannot save config: {e}")
            return False
    
    def validate(self):
        """Validate configuration"""
        mode = self.config.get('mode', '').lower()
        override = self.config.get('manual_override', '').lower()
        
        key = (mode, override)
        
        # Check if invalid combination
        if key in self.INVALID_COMBINATIONS:
            msg = self.INVALID_COMBINATIONS[key]
            self.errors.append(f"{msg} - Detected: {key}")
            
            # Try to auto-fix
            if key in self.AUTO_FIX:
                correct_override = self.AUTO_FIX[key]
                self.config['manual_override'] = correct_override
                self.fixed.append(f"Auto-fixed: {mode}/{override} → {mode}/{correct_override}")
            
            return False
        
        # Check if valid combination
        if key not in self.VALID_COMBINATIONS:
            self.warnings.append(f"Unknown combination: {key}")
        
        return len(self.errors) == 0
    
    def generate_report(self, verbose=False):
        """Generate validation report"""
        report = []
        
        # Header
        report.append("="*70)
        report.append("MODE CONFIGURATION VALIDATOR")
        report.append("="*70)
        
        # Current config
        mode = self.config.get('mode', 'UNKNOWN')
        override = self.config.get('manual_override', 'UNKNOWN')
        report.append(f"\nCurrent Configuration:")
        report.append(f"  Mode: {mode}")
        report.append(f"  Manual Override: {override}")
        
        key = (mode.lower(), override.lower())
        if key in self.VALID_COMBINATIONS:
            status = "✅"
            desc = self.VALID_COMBINATIONS[key]
        else:
            status = "❌"
            desc = "UNKNOWN - NOT VALIDATED"
        
        report.append(f"\nStatus: {status} {desc}")
        
        # Errors
        if self.errors:
            report.append(f"\n🚨 ERRORS ({len(self.errors)}):")
            for error in self.errors:
                report.append(f"  ❌ {error}")
        
        # Fixes applied
        if self.fixed:
            report.append(f"\n✅ AUTO-FIXES APPLIED ({len(self.fixed)}):")
            for fix in self.fixed:
                report.append(f"  ✓ {fix}")
        
        # Warnings
        if self.warnings:
            report.append(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                report.append(f"  ⚠️  {warning}")
        
        # Detailed info
        if verbose:
            report.append(f"\n📋 Full Configuration:")
            for k, v in self.config.items():
                report.append(f"  {k}: {v}")
        
        # Summary
        report.append("\n" + "="*70)
        if len(self.errors) == 0 and len(self.fixed) == 0:
            report.append("✅ VALIDATION PASSED - Configuration is safe")
        elif len(self.fixed) > 0:
            report.append("✅ VALIDATION PASSED - Auto-fixes applied")
        else:
            report.append("❌ VALIDATION FAILED - Manual intervention required")
        report.append("="*70)
        
        return "\n".join(report)

def main():
    """Run validator"""
    validator = ModeValidator()
    
    # Validate
    is_valid = validator.validate()
    
    # Print report
    print(validator.generate_report(verbose=False))
    
    # Save if fixes applied
    if validator.fixed:
        if validator._save_config():
            print("\n💾 Configuration saved with fixes applied")
        else:
            print("\n❌ Failed to save configuration")
            sys.exit(1)
    
    # Exit code
    if is_valid or validator.fixed:
        print("\n✅ System ready - mode configuration is safe")
        return 0
    else:
        print("\n❌ System blocked - fix configuration errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
