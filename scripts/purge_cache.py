#!/usr/bin/env python3
"""
Purge jsDelivr CDN cache for backdrop files.
"""

import requests
import sys
from pathlib import Path


def purge_cdn_cache():
    """Purge jsDelivr cache for updated backdrops."""
    backdrops_dir = Path("backdrops")
    
    if not backdrops_dir.exists():
        print("No backdrops directory found.")
        return
    
    # Get all backdrop files
    backdrop_files = list(backdrops_dir.glob("*.jpg"))
    
    if not backdrop_files:
        print("No backdrop files to purge.")
        return
    
    purged = 0
    for backdrop in backdrop_files:
        try:
            # Construct jsDelivr CDN URL
            cdn_url = f"https://purge.jsdelivr.net/gh/Dwade58200/nuvio-configuration@feature/backdrops-automation/backdrops/{backdrop.name}"
            response = requests.get(cdn_url, timeout=10)
            
            if response.status_code == 200:
                purged += 1
                print(f"Purged: {backdrop.name}")
            else:
                print(f"Failed to purge {backdrop.name}: {response.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"Error purging {backdrop.name}: {e}", file=sys.stderr)
    
    print(f"Successfully purged {purged}/{len(backdrop_files)} backdrops from CDN.")


if __name__ == "__main__":
    purge_cdn_cache()
