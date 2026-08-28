#!/usr/bin/env python3
"""Entrypoint: start the real-time Reddit demand collector."""
from dotenv import load_dotenv

load_dotenv()

from collector import run_collector

if __name__ == "__main__":
    run_collector()
