#!/usr/bin/env python3
"""
Generate backdrops for Nuvio configuration.
Fetches images from TMDB and FanArt APIs.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional
import requests
from PIL import Image
from io import BytesIO
import concurrent.futures
import json


class BackdropGenerator:
    """Generate and process backdrops for collections."""

    def __init__(self, tmdb_key: str, fanart_key: str, profile: str = "compressed", parallelism: int = 3):
        self.tmdb_key = tmdb_key
        self.fanart_key = fanart_key
        self.profile = profile
        self.parallelism = parallelism
        self.backdrops_dir = Path("backdrops")
        self.backdrops_dir.mkdir(exist_ok=True)

    def fetch_from_tmdb(self, item_id: int, item_type: str = "movie") -> Optional[str]:
        """Fetch backdrop URL from TMDB API."""
        try:
            endpoint = f"https://api.themoviedb.org/3/{item_type}/{item_id}"
            params = {"api_key": self.tmdb_key, "language": "en-US"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "backdrop_path" in data and data["backdrop_path"]:
                return f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
        except Exception as e:
            print(f"Error fetching from TMDB for {item_type} {item_id}: {e}", file=sys.stderr)
        
        return None

    def fetch_from_fanart(self, item_id: int, item_type: str = "movies") -> Optional[str]:
        """Fetch backdrop URL from FanArt API."""
        try:
            endpoint = f"https://webservice.fanart.tv/v3/{item_type}/{item_id}"
            params = {"api_key": self.fanart_key}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "backdrops" in data and data["backdrops"]:
                return data["backdrops"][0]["url"]
        except Exception as e:
            print(f"Error fetching from FanArt for {item_type} {item_id}: {e}", file=sys.stderr)
        
        return None

    def download_and_process_image(self, url: str, output_path: Path) -> bool:
        """Download image and process it based on profile."""
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if needed
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            
            # Apply profile-specific processing
            if self.profile == "compressed":
                img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=85, optimize=True)
            elif self.profile == "hq":
                img.thumbnail((4096, 2160), Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=95)
            else:
                img.save(output_path, "JPEG", quality=90)
            
            return True
        except Exception as e:
            print(f"Error processing image {url}: {e}", file=sys.stderr)
            return False

    def generate_backdrop(self, item_id: int, item_name: str, item_type: str = "movie") -> bool:
        """Generate and save backdrop for an item."""
        output_path = self.backdrops_dir / f"{item_name}_{item_id}.jpg"
        
        if output_path.exists():
            return True  # Already exists
        
        # Try TMDB first, then FanArt
        backdrop_url = self.fetch_from_tmdb(item_id, item_type)
        if not backdrop_url:
            backdrop_url = self.fetch_from_fanart(item_id, "movies" if item_type == "movie" else "shows")
        
        if not backdrop_url:
            print(f"No backdrop found for {item_name} ({item_id})", file=sys.stderr)
            return False
        
        return self.download_and_process_image(backdrop_url, output_path)

    def generate_all(self, items_file: Optional[str] = None):
        """Generate backdrops for all items."""
        items = []
        
        # Load from items file if provided
        if items_file and Path(items_file).exists():
            try:
                with open(items_file) as f:
                    items = json.load(f)
            except Exception as e:
                print(f"Error loading items file: {e}", file=sys.stderr)
                return
        
        if not items:
            print("No items to process. Create a backdrops/items.json file.")
            return
        
        # Process items in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            futures = [
                executor.submit(
                    self.generate_backdrop,
                    item["id"],
                    item["name"],
                    item.get("type", "movie")
                )
                for item in items
            ]
            
            completed = sum(1 for f in concurrent.futures.as_completed(futures) if f.result())
            print(f"Generated {completed}/{len(items)} backdrops successfully.")


def main():
    parser = argparse.ArgumentParser(description="Generate backdrops for Nuvio configuration")
    parser.add_argument("--api-key", required=True, help="TMDB API key")
    parser.add_argument("--fanart-key", required=True, help="FanArt API key")
    parser.add_argument("--profile", choices=["compressed", "hq", "standard"], default="compressed", help="Image quality profile")
    parser.add_argument("--parallelism", type=int, default=3, help="Number of parallel downloads")
    parser.add_argument("--items", help="Path to items.json file")
    
    args = parser.parse_args()
    
    generator = BackdropGenerator(
        args.api_key,
        args.fanart_key,
        args.profile,
        args.parallelism
    )
    generator.generate_all(args.items)


if __name__ == "__main__":
    main()
