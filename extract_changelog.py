# extract_changelog.py
#
# This script reads the version tag (e.g., "v2.5.3") passed as a command-line argument,
# finds the corresponding entry in changelog.json, formats the notes into Markdown,
# and saves them to a file named 'releasenotes.md'.
#
# This is designed to be used by the GitHub Actions workflow.

import sys
import json

def format_changelog_for_release(version_tag):
    """
    Reads changelog.json, extracts notes for the given version,
    and writes them to releasenotes.md.
    """
    # The version tag from GitHub will be like 'v2.5.3'. We need '2.5.3' for the JSON key.
    if not version_tag.startswith('v'):
        print(f"Error: Version tag '{version_tag}' does not start with 'v'.")
        sys.exit(1)
    version_key = version_tag[1:]

    try:
        with open('changelog.json', 'r', encoding='utf-8') as f:
            changelog_data = json.load(f)
    except FileNotFoundError:
        print("Error: changelog.json not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Could not decode changelog.json.")
        sys.exit(1)

    # Get the list of changes for the specific version
    version_notes = changelog_data.get(version_key)

    if not version_notes:
        print(f"Warning: No changelog entry found for version '{version_key}'.")
        # Create an empty release notes file so the workflow doesn't fail
        release_body = f"No release notes found for version {version_key}."
    else:
        # Format the notes into a Markdown list
        # Example: "* ✨ New Feature: Did something cool."
        markdown_notes = [f"* {note}" for note in version_notes]
        release_body = "\n".join(markdown_notes)
        print(f"Successfully extracted notes for version {version_key}.")

    # Write the formatted notes to the output file for the release action to use
    with open('releasenotes.md', 'w', encoding='utf-8') as f:
        f.write(release_body)
    print("Release notes saved to releasenotes.md.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_changelog.py <version_tag>")
        sys.exit(1)
    
    # The version tag is passed from the GitHub Actions workflow
    tag = sys.argv[1]
    format_changelog_for_release(tag)

