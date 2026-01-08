"""Script to run all tests."""

import sys
import subprocess
import os

def main():
    """Run all tests."""
    print("Running GenAI Trading System Tests...")
    print("=" * 50)
    
    # Set test environment variables if not already set
    test_env = os.environ.copy()
    test_env.setdefault("KITE_API_KEY", "test_key")
    test_env.setdefault("KITE_API_SECRET", "test_secret")
    test_env.setdefault("OPENAI_API_KEY", "test_openai_key")
    test_env.setdefault("MONGODB_URI", "mongodb://localhost:27017/")
    test_env.setdefault("REDIS_HOST", "localhost")
    test_env.setdefault("PAPER_TRADING_MODE", "true")
    
    # Run pytest
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        env=test_env
    )
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
    else:
        print("\n" + "=" * 50)
        print("❌ Some tests failed. Check output above.")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())


