#!/usr/bin/env python3
"""Test runner script for end-to-end tests."""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests(
    test_path: str = "tests/e2e",
    verbose: bool = True,
    coverage: bool = False,
    markers: str = None,
    parallel: bool = False,
    output_format: str = "default"
):
    """Run end-to-end tests.
    
    Args:
        test_path: Path to test directory or file
        verbose: Show verbose output
        coverage: Generate coverage report
        markers: Pytest markers to filter tests
        parallel: Run tests in parallel
        output_format: Output format (default, html, json)
    """
    # Build pytest command
    cmd = ["pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=dashboard",
            "--cov=engine_module",
            "--cov=data_niftybank",
            "--cov=user_module",
            "--cov-report=term-missing"
        ])
        
        if output_format == "html":
            cmd.append("--cov-report=html")
        elif output_format == "json":
            cmd.append("--cov-report=json")
    
    if markers:
        cmd.extend(["-m", markers])
    
    if parallel:
        cmd.extend(["-n", "auto"])  # Requires pytest-xdist
    
    # Add asyncio mode
    cmd.append("-p", "no:warnings")  # Suppress warnings for cleaner output
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run tests
    result = subprocess.run(cmd, cwd=project_root)
    
    return result.returncode


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run end-to-end tests for trading system"
    )
    
    parser.add_argument(
        "--path",
        default="tests/e2e",
        help="Test path (default: tests/e2e)"
    )
    
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run only fast tests (exclude slow markers)"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--coverage-html",
        action="store_true",
        help="Generate HTML coverage report"
    )
    
    parser.add_argument(
        "--markers",
        help="Pytest markers to filter tests (e.g., 'api or workflow')"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (requires pytest-xdist)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode (less verbose)"
    )
    
    parser.add_argument(
        "--category",
        choices=["api", "workflow", "safety", "all"],
        default="all",
        help="Test category to run"
    )
    
    args = parser.parse_args()
    
    # Determine test path based on category
    if args.category == "api":
        test_path = "tests/e2e/test_*_api.py"
    elif args.category == "workflow":
        test_path = "tests/e2e/test_*_workflow.py"
    elif args.category == "safety":
        test_path = "tests/e2e/test_paper_mode_safety.py"
    else:
        test_path = args.path
    
    # Determine markers
    markers = args.markers
    if args.fast:
        if markers:
            markers = f"{markers} and not slow"
        else:
            markers = "not slow"
    
    # Determine coverage
    coverage = args.coverage or args.coverage_html
    output_format = "html" if args.coverage_html else "default"
    
    # Run tests
    exit_code = run_tests(
        test_path=test_path,
        verbose=not args.quiet,
        coverage=coverage,
        markers=markers,
        parallel=args.parallel,
        output_format=output_format
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


