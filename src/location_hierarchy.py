# location_hierarchy.py
"""
Location Hierarchy Manager.

Stores parent-child relationships between location types:
  State → District → Block → Panchayat → Village

Data stored in a JSON file at the app data directory.

Structure:
  {
    "state:district": { "JHARKHAND": ["RANCHI", "HAZARIBAGH", ...], ... },
    "district:block":  { "RANCHI": ["KANKE", "MANDAR", ...], ... },
    "block:panchayat": { "KANKE": ["GP1", "GP2", ...], ... },
    "panchayat:village": { "GP1": ["VILLAGE_A", ...], ... }
  }
"""

import os
import json
from src.utils import get_data_path, get_logger
from typing import Dict, List, Optional

logger = get_logger()

# Ordered hierarchy types (top → bottom)
HIERARCHY_TYPES = ["State", "District", "Block", "Panchayat", "Village"]

# Map display name → storage key prefix
TYPE_TO_PREFIX = {
    "State": "state",
    "District": "district",
    "Block": "block",
    "Panchayat": "panchayat",
    "Village": "village",
}

# Parent → child relationship key
def _rel_key(parent_type: str, child_type: str) -> str:
    """E.g., 'state:district' or 'block:panchayat'."""
    return f"{TYPE_TO_PREFIX[parent_type]}:{TYPE_TO_PREFIX[child_type]}"


class LocationHierarchy:
    """Manages parent-child relationships between location types."""

    def __init__(self):
        self.file_path = get_data_path("location_hierarchy.json")
        self._data: Dict[str, Dict[str, List[str]]] = {}
        self._load()

    # ── Persistence ──

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning("Failed to load location hierarchy: %s", e)
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save location hierarchy: %s", e)

    # ── Query helpers ──

    def get_parent_type(self, child_type: str) -> Optional[str]:
        """Return the parent type for a given child type. E.g., 'State' for 'District'."""
        idx = HIERARCHY_TYPES.index(child_type) if child_type in HIERARCHY_TYPES else -1
        if idx > 0:
            return HIERARCHY_TYPES[idx - 1]
        return None

    def get_child_type(self, parent_type: str) -> Optional[str]:
        """Return the child type for a given parent type."""
        idx = HIERARCHY_TYPES.index(parent_type) if parent_type in HIERARCHY_TYPES else -1
        if idx != -1 and idx < len(HIERARCHY_TYPES) - 1:
            return HIERARCHY_TYPES[idx + 1]
        return None

    def get_parent_names(self, child_type: str) -> List[str]:
        """Return all unique parent names for a given child type.
        E.g., get_parent_names('District') → ['JHARKHAND', 'BIHAR', ...]
        """
        parent_type = self.get_parent_type(child_type)
        if not parent_type:
            return []
        # The parent type's values are the keys in the relationship map
        # E.g., for 'District', the relationship is 'state:district'
        rel = _rel_key(parent_type, child_type)
        return sorted(self._data.get(rel, {}).keys())

    def get_children(self, parent_type: str, parent_name: str, child_type: str) -> List[str]:
        """Return all children of a given parent.
        E.g., get_children('State', 'JHARKHAND', 'District') → ['RANCHI', ...]
        """
        rel = _rel_key(parent_type, child_type)
        return sorted(self._data.get(rel, {}).get(parent_name, []))

    def add_child(self, parent_type: str, parent_name: str, child_type: str, child_name: str):
        """Add a child under a parent.
        parent_name and child_name are uppercased for consistency.
        """
        parent_name = parent_name.upper()
        child_name = child_name.upper()
        rel = _rel_key(parent_type, child_type)
        if rel not in self._data:
            self._data[rel] = {}
        if parent_name not in self._data[rel]:
            self._data[rel][parent_name] = []
        if child_name not in self._data[rel][parent_name]:
            self._data[rel][parent_name].append(child_name)
            self._data[rel][parent_name].sort()
        self._save()

    def remove_child(self, parent_type: str, parent_name: str, child_type: str, child_name: str):
        """Remove a child from under a parent."""
        parent_name = parent_name.upper()
        child_name = child_name.upper()
        rel = _rel_key(parent_type, child_type)
        children = self._data.get(rel, {}).get(parent_name, [])
        if child_name in children:
            children.remove(child_name)
            if not children:
                del self._data[rel][parent_name]
            self._save()

    def remove_all_children_of(self, parent_type: str, parent_name: str):
        """Remove all children of a given parent (used when parent is deleted)."""
        parent_name = parent_name.upper()
        child_type = self.get_child_type(parent_type)
        if child_type:
            rel = _rel_key(parent_type, child_type)
            self._data.get(rel, {}).pop(parent_name, None)
        self._save()

    def get_all_without_parent(self, child_type: str) -> List[str]:
        """Return children that don't have a parent assigned.
        Used for backward compatibility when hierarchy data doesn't exist.
        """
        # Simply return empty - all entries should ideally have parents
        parent_type = self.get_parent_type(child_type)
        if not parent_type:
            return []
        all_parents = self.get_parent_names(child_type)
        all_children = set()
        for p in all_parents:
            all_children.update(self.get_children(parent_type, p, child_type))
        return sorted(all_children)


# Global singleton
_hierarchy: Optional[LocationHierarchy] = None


def get_hierarchy() -> LocationHierarchy:
    global _hierarchy
    if _hierarchy is None:
        _hierarchy = LocationHierarchy()
    return _hierarchy
