#!/usr/bin/env python3
"""
Localizes external recipe images (`https://...`) into `Aftensmadsretter/Files/images/<recipe-id>.jpg`,
resizing and compressing them with Pillow for fast offline PWA loading, and updates both YAML
and Markdown recipe files to reference `../Files/images/<recipe-id>.jpg`.
"""

import io
import os
import re
import urllib.request
from typing import Dict

from PIL import Image
import yaml

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TOOLS_DIR)
YAML_DIR = os.path.join(BASE_DIR, "recipes_yaml")
MD_DIR = os.path.join(BASE_DIR, "recipes")
IMAGES_DIR = os.path.join(BASE_DIR, "Files", "images")


def download_and_optimize(url: str, dest_path: str) -> bool:
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return True
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_bytes = resp.read()
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        # Resize to max 900px width while preserving aspect ratio
        max_w = 900
        if img.width > max_w:
            new_h = int(img.height * (max_w / img.width))
            img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        img.save(dest_path, format="JPEG", quality=82, optimize=True)
        return True
    except Exception as e:
        print(f"  ! Could not download {url}: {e}")
        return False


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    localized_count = 0

    # 1. Process YAML recipes
    if os.path.exists(YAML_DIR):
        for fname in sorted(os.listdir(YAML_DIR)):
            if not fname.endswith((".yaml", ".yml")):
                continue
            fpath = os.path.join(YAML_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            data = yaml.safe_load(text)
            rid = data.get("id", fname[:-5])
            img_url = data.get("image", "")
            if img_url.startswith("http"):
                local_rel = f"../Files/images/{rid}.jpg"
                dest_file = os.path.join(IMAGES_DIR, f"{rid}.jpg")
                if download_and_optimize(img_url, dest_file):
                    new_text = text.replace(f"image: {img_url}", f"image: {local_rel}")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_text)
                    localized_count += 1
                    print(f"Localized YAML image: {rid} -> {local_rel}")

    # 2. Process Markdown recipes
    if os.path.exists(MD_DIR):
        for fname in sorted(os.listdir(MD_DIR)):
            if not fname.endswith(".md") or fname in ("liste-af-retter.md", "nutrition-summary.md"):
                continue
            rid = fname[:-3]
            fpath = os.path.join(MD_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            m = re.search(r"(!\[[^\]]*\]\()(https?://[^)]+)(\))", text)
            if m:
                url = m.group(2)
                local_rel = f"../Files/images/{rid}.jpg"
                dest_file = os.path.join(IMAGES_DIR, f"{rid}.jpg")
                if download_and_optimize(url, dest_file):
                    new_text = text[:m.start()] + f"{m.group(1)}{local_rel}{m.group(3)}" + text[m.end():]
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_text)
                    localized_count += 1
                    print(f"Localized MD image: {rid} -> {local_rel}")

    print(f"Done. Localized/updated {localized_count} recipe file references.")


if __name__ == "__main__":
    main()
