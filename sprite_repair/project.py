"""
sprite_repair.project
~~~~~~~~~~~~~~~~~~~~~
Project save/load (*.spriteproject JSON) integrating Aseprite-grade Project models.
Conforms to Sections 7, 56 of MASTER_SPEC.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sprite_repair.models import Project, Sprite, Frame, Layer, Tag, Slice


def build_project_dict(result: dict[str, Any] | Project, *, name: str = "project") -> dict[str, Any]:
    if isinstance(result, Project):
        d = result.to_dict()
        d["format"] = "spriteproject"
        return d

    # Dictionary input (legacy or model-like)
    if "layers" in result and "sprite" in result:
        proj = Project.from_dict(result)
        d = proj.to_dict()
        d["format"] = "spriteproject"
        return d

    # Legacy raw session dict
    proj = Project.from_legacy_dict(result, name=name)
    d = proj.to_dict()
    d["format"] = "spriteproject"
    d["source"] = result.get("source")
    d["sheet_size"] = result.get("sheet_size")
    d["grid"] = result.get("grid")
    d["alpha_threshold"] = result.get("alpha_threshold")
    d["pad"] = result.get("pad")
    d["expand_ratio"] = result.get("expand_ratio")
    return d


def write_project(path: str | Path, result: dict[str, Any] | Project, name: str = "project") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = build_project_dict(result, name=name)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_project(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def load_project_model(path: str | Path) -> Project:
    data = read_project(path)
    if "version" in data and ("sprite" in data or "canvas" in data):
        return Project.from_dict(data)
    return Project.from_legacy_dict(data)
