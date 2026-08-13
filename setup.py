from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="llm-pqr",
    version="0.1.0",
    description="Test your models. Pick with evidence.",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    entry_points={"console_scripts": ["llm-pqr=llm_pqr.cli:main"]},
)
