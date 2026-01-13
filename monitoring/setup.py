"""
Setup script for the monitoring module.
"""

from setuptools import setup, find_packages

with open("requirements.txt", "r") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="trading-system-monitoring",
    version="1.0.0",
    description="Production monitoring and hardening for trading system",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=requirements,
    python_requires=">=3.8",
)