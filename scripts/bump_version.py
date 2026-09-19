#!/usr/bin/env python3
"""Automated single-command version bumper for NREGA Bot.

Updates all version references across the repository consistently:
  1. config/version.json        (latest_version, core_update URLs, empty hashes per RULE-REL-002, changelog)
  2. src/config.py              (APP_VERSION)
  3. docs/changelog.json        (changelog history)
  4. scripts/installer.iss      (#define AppVersion)
  5. scripts/installer_lite.iss (#define AppVersion)
  6. README.md                  (badge & header version)
  7. AGENTS.md                  (version table & status line)

Usage:
  python3 scripts/bump_version.py 3.2.12
  python3 scripts/bump_version.py 3.2.12 --notes "Note 1" "Note 2"
  python3 scripts/bump_version.py --check
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_current_version() -> str:
    v_path = os.path.join(ROOT, "config", "version.json")
    with open(v_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("latest_version", "0.0.0")


def bump_version(new_version: str, notes: list = None, dry_run: bool = False):
    if not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$", new_version):
        print(f"❌ Invalid version format '{new_version}'. Expected X.Y.Z or X.Y.Z-beta")
        sys.exit(1)

    curr = get_current_version()
    print(f"📦 Bumping version: v{curr} -> v{new_version}")

    notes = notes or []

    # 1. config/version.json
    v_path = os.path.join(ROOT, "config", "version.json")
    with open(v_path, "r", encoding="utf-8") as f:
        v_data = json.load(f)

    v_data["latest_version"] = new_version
    v_data["download_url_windows"] = f"https://nregabot.com/updates/NREGABot-v{new_version}-Setup.exe"
    v_data["download_url_macos"] = f"https://nregabot.com/updates/NREGABot-v{new_version}-macOS.dmg"
    v_data["download_url_linux"] = f"https://nregabot.com/updates/NREGABot-v{new_version}-Linux.tar.gz"

    if "core_update" in v_data:
        v_data["core_update"]["version"] = new_version
        v_data["core_update"]["url"] = f"https://nregabot.com/updates/core_v{new_version}.zip"
        v_data["core_update"]["url_windows"] = f"https://nregabot.com/updates/core_win_v{new_version}.zip"
        v_data["core_update"]["url_macos"] = f"https://nregabot.com/updates/core_mac_v{new_version}.zip"
        # RULE-REL-002: Always keep hashes empty in repository
        v_data["core_update"]["hash"] = ""
        v_data["core_update"]["hash_windows"] = ""
        v_data["core_update"]["hash_macos"] = ""

    if notes:
        existing_cl = v_data.get("changelog", {})
        new_cl = {new_version: notes}
        for k, val in existing_cl.items():
            if k != new_version:
                new_cl[k] = val
        v_data["changelog"] = new_cl

    if not dry_run:
        with open(v_path, "w", encoding="utf-8") as f:
            json.dump(v_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    print(f"  ✓ Updated config/version.json")

    # 2. src/config.py
    cfg_path = os.path.join(ROOT, "src", "config.py")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg_content = f.read()

    cfg_new = re.sub(
        r'APP_VERSION:\s*str\s*=\s*"[^"]+"',
        f'APP_VERSION: str = "{new_version}"',
        cfg_content
    )
    if not dry_run:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(cfg_new)
    print(f"  ✓ Updated src/config.py")

    # 3. docs/changelog.json
    doc_cl_path = os.path.join(ROOT, "docs", "changelog.json")
    if os.path.exists(doc_cl_path) and notes:
        with open(doc_cl_path, "r", encoding="utf-8") as f:
            try:
                doc_cl = json.load(f)
            except Exception:
                doc_cl = {}
        new_doc_cl = {new_version: notes}
        for k, val in doc_cl.items():
            if k != new_version:
                new_doc_cl[k] = val
        if not dry_run:
            with open(doc_cl_path, "w", encoding="utf-8") as f:
                json.dump(new_doc_cl, f, indent=2, ensure_ascii=False)
                f.write("\n")
        print(f"  ✓ Updated docs/changelog.json")

    # 4 & 5. Inno Setup scripts
    for iss_file in ("installer.iss", "installer_lite.iss"):
        iss_path = os.path.join(ROOT, "scripts", iss_file)
        if os.path.exists(iss_path):
            with open(iss_path, "r", encoding="utf-8") as f:
                iss_content = f.read()
            iss_new = re.sub(
                r'#define\s+AppVersion\s+"[^"]+"',
                f'#define AppVersion "{new_version}"',
                iss_content
            )
            if not dry_run:
                with open(iss_path, "w", encoding="utf-8") as f:
                    f.write(iss_new)
            print(f"  ✓ Updated scripts/{iss_file}")

    # 6. README.md
    readme_path = os.path.join(ROOT, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
        readme = re.sub(
            r'\*\*v\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?\*\*',
            f'**v{new_version}**',
            readme,
            count=1
        )
        readme = re.sub(
            r'badge/version-\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?-1F4E79',
            f'badge/version-{new_version}-1F4E79',
            readme
        )
        if not dry_run:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme)
        print(f"  ✓ Updated README.md")

    # 7. AGENTS.md
    agents_path = os.path.join(ROOT, "AGENTS.md")
    if os.path.exists(agents_path):
        with open(agents_path, "r", encoding="utf-8") as f:
            agents = f.read()
        agents = re.sub(
            r'version table refreshed \d+ \w+ \d+ for \*\*\d+\.\d+\.\d+\*\*',
            f'version table refreshed for **{new_version}**',
            agents
        )
        agents = re.sub(
            r'\|\s*`config/version\.json`\s*\|\s*`latest_version`\s*\|\s*\*\*\d+\.\d+\.\d+\*\*\s*\|',
            f'| `config/version.json` | `latest_version` | **{new_version}** |',
            agents
        )
        agents = re.sub(
            r'\|\s*`src/config\.py`\s*\|\s*`APP_VERSION`\s*\|\s*\*\*\d+\.\d+\.\d+\*\*\s*\|',
            f'| `src/config.py` | `APP_VERSION` | **{new_version}** |',
            agents
        )
        agents = re.sub(
            r'\|\s*`README\.md`\s*\|\s*Version badge\s*\|\s*\*\*v\d+\.\d+\.\d+\*\*\s*\|',
            f'| `README.md` | Version badge | **v{new_version}** |',
            agents
        )
        agents = re.sub(
            r'\|\s*`scripts/installer\.iss` / `installer_lite\.iss`\s*\|\s*`AppVersion`\s*\|\s*\*\*\d+\.\d+\.\d+\*\*\s*\|',
            f'| `scripts/installer.iss` / `installer_lite.iss` | `AppVersion` | **{new_version}** |',
            agents
        )
        if not dry_run:
            with open(agents_path, "w", encoding="utf-8") as f:
                f.write(agents)
        print(f"  ✓ Updated AGENTS.md")

    print(f"\n🎉 Successfully bumped repository to v{new_version}!")


def check_consistency():
    curr = get_current_version()
    print(f"🔍 Checking version consistency across files (target: {curr})...")
    all_ok = True

    # Check src/config.py
    with open(os.path.join(ROOT, "src", "config.py"), "r", encoding="utf-8") as f:
        match = re.search(r'APP_VERSION:\s*str\s*=\s*"([^"]+)"', f.read())
        cfg_ver = match.group(1) if match else "NOT_FOUND"
        if cfg_ver == curr:
            print(f"  ✓ src/config.py: {cfg_ver}")
        else:
            print(f"  ❌ src/config.py mismatch: {cfg_ver} != {curr}")
            all_ok = False

    # Check installers
    for iss in ("installer.iss", "installer_lite.iss"):
        with open(os.path.join(ROOT, "scripts", iss), "r", encoding="utf-8") as f:
            match = re.search(r'#define\s+AppVersion\s+"([^"]+)"', f.read())
            iss_ver = match.group(1) if match else "NOT_FOUND"
            if iss_ver == curr:
                print(f"  ✓ scripts/{iss}: {iss_ver}")
            else:
                print(f"  ⚠️ scripts/{iss}: {iss_ver} (differs from {curr})")

    if all_ok:
        print("✅ Core source-of-truth files match!")
    else:
        print("❌ Inconsistencies detected.")


def main():
    parser = argparse.ArgumentParser(description="Bump NREGA Bot version across all files.")
    parser.add_argument("version", nargs="?", help="New version (e.g. 3.2.12)")
    parser.add_argument("--notes", nargs="+", help="Changelog bullet points for this release")
    parser.add_argument("--check", action="store_true", help="Check current version consistency")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying files")

    args = parser.parse_args()
    if args.check:
        check_consistency()
        return

    if not args.version:
        parser.print_help()
        sys.exit(1)

    bump_version(args.version, notes=args.notes, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
