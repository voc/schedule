#!/usr/bin/env python3
"""Wrapper to run voctoimport from anywhere"""
import sys
from pathlib import Path

# Add this directory to Python path so 'voc' package is found
sys.path.insert(0, str(Path(__file__).parent))

# Execute the voctoimport module
if __name__ == "__main__":
    import runpy
    runpy.run_module("voc.voctoimport", run_name="__main__")
