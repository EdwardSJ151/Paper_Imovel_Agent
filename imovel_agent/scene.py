"""Loads a property scene (zones + objects) and renders it as a catalog for the prompt."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# Reply language: "pt" or "en". Object labels always come from the dictionary, which is pt-BR.
LANGUAGE = "pt"

DATA_DIR = Path(__file__).parent / "data"

# Rooms are separated by a wall, so touching polygons sit a few centimetres apart.
ADJACENT_M = 0.3

_scenes: Dict[str, "Scene"] = {}


def _load_dictionary(env_id: str) -> Dict[str, str]:
    """Parse `key = label` lines. Keys are mesh names, or an itemId for a single object."""
    entries = {}
    for line in (DATA_DIR / f"{env_id}.txt").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, label = line.split("=", 1)
            entries[key.strip()] = label.strip()
    return entries


@dataclass
class Scene:
    env_id: str
    catalog_text: str
    valid_ids: Set[str]
    labels: Dict[str, str]

    def label_for(self, target_id: str) -> str:
        return self.labels.get(target_id, target_id)


def _nearest_zone(position: dict, zones: List[dict]) -> str:
    def distance(zone: dict) -> float:
        xs = [p["x"] for p in zone["polygon"]]
        zs = [p["z"] for p in zone["polygon"]]
        dx = max(min(xs) - position["x"], 0.0, position["x"] - max(xs))
        dz = max(min(zs) - position["z"], 0.0, position["z"] - max(zs))
        return dx * dx + dz * dz

    return min(zones, key=distance)["id"]


def _point_to_segment(p, a, b) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    if dx == dz == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (dx * dx + dz * dz)))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def _zone_distance(zone_a: dict, zone_b: dict) -> float:
    """Gap between two room outlines. Exact while the rooms do not overlap."""
    a = [(p["x"], p["z"]) for p in zone_a["polygon"]]
    b = [(p["x"], p["z"]) for p in zone_b["polygon"]]
    return min(
        _point_to_segment(p, q, r)
        for poly, other in ((a, b), (b, a))
        for p in poly
        for q, r in zip(other, other[1:] + other[:1])
    )


def _neighbours(zone: dict, zones: List[dict]) -> List[str]:
    return [
        other["label"]
        for other in zones
        if other is not zone and _zone_distance(zone, other) <= ADJACENT_M
    ]


def _render_catalog(env_id: str, data: dict, dictionary: Dict[str, str]):
    valid_ids: Set[str] = set()
    labels: Dict[str, str] = {}
    lines: List[str] = []

    zone_ids = {zone["id"] for zone in data["zones"]}
    by_zone: Dict[str, List[dict]] = {}
    for obj in data["objects"]:
        zone_id = obj["zoneId"]
        if zone_id not in zone_ids:  # wall-mounted props land just outside every polygon
            zone_id = _nearest_zone(obj["scenePosition"], data["zones"])
        by_zone.setdefault(zone_id, []).append(obj)

    for zone in data["zones"]:
        zone_id, zone_label = zone["id"], zone["label"]
        valid_ids.add(zone_id)
        labels[zone_id] = zone_label
        neighbours = ", ".join(_neighbours(zone, data["zones"])) or "nenhum"
        lines.append(
            f'{zone_label} (id={zone_id}, {zone["area"]:g} m2, ao lado de: {neighbours})'
        )

        # An itemId entry overrides the mesh label, so identical meshes can be named apart.
        grouped: Dict[str, List[str]] = {}
        for obj in by_zone.get(zone_id, []):
            item_id, mesh = obj["itemId"], obj["name"]
            label = dictionary.get(item_id) or dictionary.get(mesh)
            if label is None:
                logger.warning("env %s: no dictionary entry for %r", env_id, mesh)
                label = mesh
            valid_ids.add(item_id)
            labels[item_id] = label
            grouped.setdefault(label, []).append(item_id)

        if not grouped:
            lines.append("  (vazio)")
        for label, ids in grouped.items():
            lines.append(f'  - {label} x{len(ids)} -> {", ".join(ids)}')
        lines.append("")

    return "\n".join(lines).strip(), valid_ids, labels


def load_scene(env_id: str) -> Scene:
    """Load and cache the scene and dictionary for an environment ID."""
    env_id = str(env_id)
    if env_id not in _scenes:
        path = DATA_DIR / f"{env_id}.json"
        if not path.exists():
            available = sorted(p.stem for p in DATA_DIR.glob("*.json"))
            raise FileNotFoundError(
                f"No scene data for environment {env_id!r}. Available: {available}."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        catalog_text, valid_ids, labels = _render_catalog(env_id, data, _load_dictionary(env_id))
        _scenes[env_id] = Scene(env_id, catalog_text, valid_ids, labels)
    return _scenes[env_id]
