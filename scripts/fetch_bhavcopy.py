#!/usr/bin/env python3
"""Download and cache one day's NSE cash-market bhavcopy.

Usage: python3 scripts/fetch_bhavcopy.py 2026-11-13

Files land in data/ (gitignored - NSE data is downloaded for local
computation only and never redistributed). Be polite: one file at a time.
"""
import sys
from datetime import date

from papertrading.data import fetch_bhavcopy

if __name__ == "__main__":
    d = date.fromisoformat(sys.argv[1])
    print(fetch_bhavcopy(d))
