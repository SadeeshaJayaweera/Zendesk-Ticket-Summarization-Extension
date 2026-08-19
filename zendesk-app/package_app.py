#!/usr/bin/env python3
"""Zendesk App Packager & Validator.

Validates the ZAF app structure against Zendesk specification and generates
a compliant zip package in zendesk-app/dist/zendesk-ticket-summarizer.zip
ready for upload in Zendesk Admin Center (Private Apps).
"""

import json
import os
import sys
import zipfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(APP_DIR, "dist")
OUTPUT_ZIP = os.path.join(DIST_DIR, "zendesk-ticket-summarizer.zip")


def validate_app_structure():
    """Verify that all required files and manifest schema fields are present."""
    print("🔍 Validating Zendesk App Structure...")

    manifest_path = os.path.join(APP_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("manifest.json not found in app root.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            manifest = json.load(f)
        except Exception as e:
            raise ValueError(f"manifest.json is invalid JSON: {e}")

    # Check manifest required fields
    required_keys = ["name", "author", "defaultLocale", "location", "frameworkVersion"]
    for key in required_keys:
        if key not in manifest:
            raise ValueError(f"manifest.json missing required top-level property '{key}'")

    # Check location definition
    location = manifest.get("location", {})
    if "support" not in location or "ticket_sidebar" not in location["support"]:
        raise ValueError("manifest.json must define location.support.ticket_sidebar")

    sidebar_url = location["support"]["ticket_sidebar"].get("url")
    if not sidebar_url or not os.path.exists(os.path.join(APP_DIR, sidebar_url)):
        raise FileNotFoundError(f"ticket_sidebar url '{sidebar_url}' does not exist on disk.")

    # Check translations
    default_locale = manifest.get("defaultLocale", "en")
    translation_file = os.path.join(APP_DIR, "translations", f"{default_locale}.json")
    if not os.path.exists(translation_file):
        raise FileNotFoundError(f"Translation file '{translation_file}' not found.")

    print("   ✅ manifest.json schema and files validated.")
    return manifest


def build_package(manifest):
    """Build compliant zip package."""
    os.makedirs(DIST_DIR, exist_ok=True)
    print(f"📦 Packaging Zendesk App '{manifest.get('name')}' v{manifest.get('version')}...")

    files_to_pack = []

    # 1. Manifest
    files_to_pack.append(("manifest.json", os.path.join(APP_DIR, "manifest.json")))

    # 2. Assets
    assets_dir = os.path.join(APP_DIR, "assets")
    for root, _, files in os.walk(assets_dir):
        for file in files:
            if file.startswith("."):
                continue
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, APP_DIR)
            files_to_pack.append((rel_path, abs_path))

    # 3. Translations
    trans_dir = os.path.join(APP_DIR, "translations")
    for root, _, files in os.walk(trans_dir):
        for file in files:
            if file.startswith("."):
                continue
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, APP_DIR)
            files_to_pack.append((rel_path, abs_path))

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for archive_name, disk_path in files_to_pack:
            zipf.write(disk_path, archive_name)
            print(f"   + Added: {archive_name}")

    file_size_kb = os.path.getsize(OUTPUT_ZIP) / 1024
    print(f"\n🎉 Package created successfully: {OUTPUT_ZIP} ({file_size_kb:.2f} KB)")
    print("👉 Upload this file in Zendesk Admin Center > Apps and integrations > Zendesk Support apps > Upload private app")


def main():
    try:
        manifest = validate_app_structure()
        build_package(manifest)
    except Exception as e:
        print(f"❌ Packaging Failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
