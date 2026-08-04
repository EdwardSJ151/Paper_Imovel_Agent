"""Loads a property scene (zones + objects) and renders it as a catalog for the prompt."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# Reply / catalog language: "pt" or "en".
LANGUAGE = "pt"

DATA_DIR = Path(__file__).parent / "data"

_dictionary: Dict[str, dict] | None = None
_scenes: Dict[str, "Scene"] = {}


def _load_dictionary() -> Dict[str, dict]:
    global _dictionary
    if _dictionary is None:
        _dictionary = json.loads((DATA_DIR / "dictionary.json").read_text(encoding="utf-8"))
    return _dictionary


def _describe(mesh_name: str) -> tuple[str, str]:
    """(label, category) for a mesh name, falling back to the raw name."""
    entry = _load_dictionary().get(mesh_name)
    if entry is None:
        logger.warning("No dictionary entry for mesh %r — using the raw name.", mesh_name)
        return mesh_name, "?"
    return entry[LANGUAGE], entry["category"]


@dataclass
class Scene:
    env_id: str
    catalog_text: str
    valid_ids: Set[str]
    labels: Dict[str, str]

    def label_for(self, target_id: str) -> str:
        return self.labels.get(target_id, target_id)


def _render_catalog(data: dict) -> tuple[str, Set[str], Dict[str, str]]:
    valid_ids: Set[str] = set()
    labels: Dict[str, str] = {}
    lines: List[str] = []

    by_zone: Dict[str, List[dict]] = {}
    for obj in data["objects"]:
        by_zone.setdefault(obj["zoneId"], []).append(obj)

    for zone in data["zones"]:
        zone_id, zone_label = zone["id"], zone["label"]
        valid_ids.add(zone_id)
        labels[zone_id] = zone_label
        lines.append(f'{zone_label} (id={zone_id}, {zone["area"]:g} m2)')

        # Group by mesh name so counts are explicit and every itemId stays addressable.
        grouped: Dict[str, List[dict]] = {}
        for obj in by_zone.get(zone_id, []):
            grouped.setdefault(obj["name"], []).append(obj)

        if not grouped:
            lines.append("  (vazio)" if LANGUAGE == "pt" else "  (empty)")

        for mesh_name, objs in grouped.items():
            label, category = _describe(mesh_name)
            ids = [o["itemId"] for o in objs]
            for item_id in ids:
                valid_ids.add(item_id)
                labels[item_id] = label
            lines.append(f'  - {label} [{category}] x{len(ids)} -> {", ".join(ids)}')
        lines.append("")

    return "\n".join(lines).strip(), valid_ids, labels


def load_scene(env_id: str) -> Scene:
    """Load and cache the scene for an environment ID."""
    env_id = str(env_id)
    if env_id not in _scenes:
        path = DATA_DIR / f"{env_id}.json"
        if not path.exists():
            available = sorted(p.stem for p in DATA_DIR.glob("*.json") if p.stem != "dictionary")
            raise FileNotFoundError(
                f"No scene data for environment {env_id!r}. Available: {available}. "
                f"Add {path.name} to {DATA_DIR}."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        catalog_text, valid_ids, labels = _render_catalog(data)
        _scenes[env_id] = Scene(env_id, catalog_text, valid_ids, labels)
    return _scenes[env_id]
