"""
sprite_repair.models
~~~~~~~~~~~~~~~~~~~~
Aseprite-grade data model architecture for Sprite Animation Repair Studio.
Conforms to Sections 7, 8, 9, 10, 23, 24, 28 of MASTER_SPEC.md.

Hierarchy:
  Project
   ├── Sprite (Canvas dimensions, global anchor, color mode)
   ├── Layers[] (Character, VFX, Shadow, Correction, Mask, Reference)
   ├── Frames[]
   │     ├── Nominal / Content / Character / Effect / Combined Rects
   │     ├── Anchor (Foot/Root) & Canvas Offset
   │     ├── Diagnostics (Jitter, Scale Anomaly, Overflow, Review Flag)
   │     └── Cels[] (Layer x Frame matrix cells)
   ├── Tags[] (Animation sub-sequences: Idle, Attack, etc.)
   ├── Slices[] (Bounding sub-slices with optional pivots)
   └── ExportSettings
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Literal


@dataclass
class Point:
    x: int = 0
    y: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"x": int(self.x), "y": int(self.y)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Point:
        if not data:
            return cls(0, 0)
        return cls(x=int(data.get("x", 0)), y=int(data.get("y", 0)))


@dataclass
class Rect:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def w(self) -> int:
        return self.width

    @property
    def h(self) -> int:
        return self.height

    @property
    def left(self) -> int:
        return self.x

    @property
    def top(self) -> int:
        return self.y

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0

    def to_dict(self) -> dict[str, int]:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
            "w": int(self.width),
            "h": int(self.height),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Rect:
        if not data:
            return cls(0, 0, 0, 0)
        w = int(data.get("width", data.get("w", 0)))
        h = int(data.get("height", data.get("h", 0)))
        return cls(x=int(data.get("x", 0)), y=int(data.get("y", 0)), width=w, height=h)


@dataclass
class Anchor:
    x: int = 0
    y: int = 0
    type: str = "foot"  # "foot" | "root" | "center" | "custom"
    locked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "type": self.type,
            "locked": bool(self.locked),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Anchor:
        if not data:
            return cls(0, 0)
        return cls(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            type=str(data.get("type", "foot")),
            locked=bool(data.get("locked", False)),
        )


@dataclass
class Diagnostics:
    jitter: bool = False
    scale_anomaly: bool = False
    overflow: bool = False
    review_required: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "jitter": bool(self.jitter),
            "scale_anomaly": bool(self.scale_anomaly),
            "overflow": bool(self.overflow),
            "review_required": bool(self.review_required),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Diagnostics:
        if not data:
            return cls()
        return cls(
            jitter=bool(data.get("jitter", False)),
            scale_anomaly=bool(data.get("scale_anomaly", False)),
            overflow=bool(data.get("overflow", False)),
            review_required=bool(data.get("review_required", False)),
            warnings=list(data.get("warnings", [])),
        )


@dataclass
class Layer:
    id: str
    name: str
    type: str = "character"  # "character" | "vfx" | "shadow" | "correction" | "mask" | "reference" | "group"
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"
    locked: bool = False
    parent_id: str | None = None
    collapsed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "visible": self.visible,
            "opacity": float(self.opacity),
            "blend_mode": self.blend_mode,
            "locked": bool(self.locked),
            "parent_id": self.parent_id,
            "collapsed": bool(self.collapsed),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Layer:
        return cls(
            id=str(data.get("id", "layer_default")),
            name=str(data.get("name", "Layer")),
            type=str(data.get("type", "character")),
            visible=bool(data.get("visible", True)),
            opacity=float(data.get("opacity", 1.0)),
            blend_mode=str(data.get("blend_mode", "normal")),
            locked=bool(data.get("locked", False)),
            parent_id=data.get("parent_id"),
            collapsed=bool(data.get("collapsed", False)),
        )


@dataclass
class Cel:
    layer_id: str
    frame_id: int
    x: int = 0
    y: int = 0
    opacity: float = 1.0
    visible: bool = True
    image_data: str | None = None  # Base64 data URL
    linked_cel_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "layer_id": self.layer_id,
            "frame_id": int(self.frame_id),
            "x": int(self.x),
            "y": int(self.y),
            "opacity": float(self.opacity),
            "visible": bool(self.visible),
        }
        if self.image_data:
            res["image_data"] = self.image_data
        if self.linked_cel_id:
            res["linked_cel_id"] = self.linked_cel_id
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cel:
        return cls(
            layer_id=str(data.get("layer_id", "")),
            frame_id=int(data.get("frame_id", 0)),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            opacity=float(data.get("opacity", 1.0)),
            visible=bool(data.get("visible", True)),
            image_data=data.get("image_data"),
            linked_cel_id=data.get("linked_cel_id"),
        )


@dataclass
class Frame:
    id: int
    index: int
    duration_ms: int = 80
    nominal_rect: Rect = field(default_factory=Rect)
    content_rect: Rect = field(default_factory=Rect)
    character_bbox: Rect | None = None
    effect_bbox: Rect | None = None
    combined_bbox: Rect | None = None
    anchor: Anchor = field(default_factory=Anchor)
    offset: Point = field(default_factory=Point)
    pivot: Point | None = None
    linked_cel_id: str | None = None
    mask_strokes: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: Diagnostics = field(default_factory=Diagnostics)
    cels: list[Cel] = field(default_factory=list)
    image_data: str | None = None  # Composite preview data URL

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "id": self.id,
            "index": self.index,
            "duration_ms": self.duration_ms,
            "nominal_rect": self.nominal_rect.to_dict(),
            "content_rect": self.content_rect.to_dict(),
            "character_bbox": self.character_bbox.to_dict() if self.character_bbox else None,
            "effect_bbox": self.effect_bbox.to_dict() if self.effect_bbox else None,
            "combined_bbox": self.combined_bbox.to_dict() if self.combined_bbox else None,
            "anchor": self.anchor.to_dict(),
            "offset": self.offset.to_dict(),
            "diagnostics": self.diagnostics.to_dict(),
            "cels": [c.to_dict() for c in self.cels],
        }
        if self.pivot:
            res["pivot"] = self.pivot.to_dict()
        else:
            res["pivot"] = None
        if self.linked_cel_id:
            res["linked_cel_id"] = self.linked_cel_id
        else:
            res["linked_cel_id"] = None
        if self.mask_strokes:
            res["mask_strokes"] = list(self.mask_strokes)
        else:
            res["mask_strokes"] = []
        if self.image_data:
            res["image_data"] = self.image_data
        # Legacy compatibility aliases
        res["frame"] = self.index
        res["duration"] = self.duration_ms
        res["rect"] = self.content_rect.to_dict()
        res["crop"] = self.content_rect.to_dict()
        res["qa_warnings"] = list(self.diagnostics.warnings)
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Frame:
        frame_idx = int(data.get("index", data.get("frame", data.get("id", 0))))
        frame_id = int(data.get("id", frame_idx))
        duration = int(data.get("duration_ms", data.get("duration", 80)))

        nom_rect = Rect.from_dict(data.get("nominal_rect"))
        content_rect = Rect.from_dict(data.get("content_rect", data.get("rect", data.get("crop"))))
        char_box = Rect.from_dict(data.get("character_bbox")) if data.get("character_bbox") else None
        eff_box = Rect.from_dict(data.get("effect_bbox")) if data.get("effect_bbox") else None
        comb_box = Rect.from_dict(data.get("combined_bbox")) if data.get("combined_bbox") else None
        anchor = Anchor.from_dict(data.get("anchor"))
        offset = Point.from_dict(data.get("offset"))
        pivot = Point.from_dict(data.get("pivot")) if data.get("pivot") else None
        linked_cel_id = data.get("linked_cel_id")
        mask_strokes = list(data.get("mask_strokes") or [])

        diag_data = data.get("diagnostics")
        if isinstance(diag_data, dict):
            diag = Diagnostics.from_dict(diag_data)
        else:
            diag = Diagnostics(warnings=list(data.get("qa_warnings", [])))
            diag.review_required = len(diag.warnings) > 0

        cels = [Cel.from_dict(c) for c in data.get("cels", [])]
        img_data = data.get("image_data", data.get("data_url"))

        return cls(
            id=frame_id,
            index=frame_idx,
            duration_ms=duration,
            nominal_rect=nom_rect,
            content_rect=content_rect,
            character_bbox=char_box,
            effect_bbox=eff_box,
            combined_bbox=comb_box,
            anchor=anchor,
            offset=offset,
            pivot=pivot,
            linked_cel_id=linked_cel_id,
            mask_strokes=mask_strokes,
            diagnostics=diag,
            cels=cels,
            image_data=img_data,
        )


@dataclass
class Tag:
    name: str
    from_frame: int
    to_frame: int
    direction: str = "forward"  # "forward" | "reverse" | "pingpong"
    repeat: int = 0  # 0 = infinite
    color: str = "#6aa8ff"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "from": int(self.from_frame),
            "to": int(self.to_frame),
            "from_frame": int(self.from_frame),
            "to_frame": int(self.to_frame),
            "direction": self.direction,
            "repeat": int(self.repeat),
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tag:
        return cls(
            name=str(data.get("name", "Animation")),
            from_frame=int(data.get("from", data.get("from_frame", 0))),
            to_frame=int(data.get("to", data.get("to_frame", 0))),
            direction=str(data.get("direction", "forward")),
            repeat=int(data.get("repeat", 0)),
            color=str(data.get("color", "#6aa8ff")),
        )


@dataclass
class Slice:
    name: str
    bounds: Rect
    pivot: Point | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "name": self.name,
            "bounds": self.bounds.to_dict(),
        }
        if self.pivot:
            res["pivot"] = self.pivot.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Slice:
        return cls(
            name=str(data.get("name", "slice")),
            bounds=Rect.from_dict(data.get("bounds")),
            pivot=Point.from_dict(data.get("pivot")) if data.get("pivot") else None,
        )


@dataclass
class Sprite:
    width: int = 128
    height: int = 128
    anchor: Point = field(default_factory=Point)
    color_mode: str = "RGBA"

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": int(self.width),
            "height": int(self.height),
            "w": int(self.width),
            "h": int(self.height),
            "anchor": self.anchor.to_dict(),
            "color_mode": self.color_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Sprite:
        if not data:
            return cls()
        w = int(data.get("width", data.get("w", 128)))
        h = int(data.get("height", data.get("h", 128)))
        anchor = Point.from_dict(data.get("anchor"))
        return cls(width=w, height=h, anchor=anchor, color_mode=data.get("color_mode", "RGBA"))


@dataclass
class Project:
    name: str = "Untitled"
    version: str = "2.0"
    sprite: Sprite = field(default_factory=Sprite)
    layers: list[Layer] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    slices: list[Slice] = field(default_factory=list)
    export_settings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.layers:
            self.layers = [
                Layer(id="layer_character", name="Character", type="character"),
                Layer(id="layer_vfx", name="VFX", type="vfx"),
            ]
        if not self.tags and self.frames:
            self.tags = [
                Tag(name="Default", from_frame=0, to_frame=len(self.frames) - 1, direction="forward")
            ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "sprite": self.sprite.to_dict(),
            "canvas": self.sprite.to_dict(),  # Alias for legacy compatibility
            "layers": [layer.to_dict() for layer in self.layers],
            "frames": [frame.to_dict() for frame in self.frames],
            "tags": [tag.to_dict() for tag in self.tags],
            "slices": [sl.to_dict() for sl in self.slices],
            "export_settings": dict(self.export_settings),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        name = str(data.get("name", "Untitled"))
        version = str(data.get("version", "2.0"))
        sprite_data = data.get("sprite", data.get("canvas"))
        sprite = Sprite.from_dict(sprite_data)

        layers = [Layer.from_dict(l) for l in data.get("layers", [])]
        frames = [Frame.from_dict(f) for f in data.get("frames", [])]
        tags = [Tag.from_dict(t) for t in data.get("tags", [])]
        slices = [Slice.from_dict(s) for s in data.get("slices", [])]
        export_settings = dict(data.get("export_settings", {}))

        return cls(
            name=name,
            version=version,
            sprite=sprite,
            layers=layers,
            frames=frames,
            tags=tags,
            slices=slices,
            export_settings=export_settings,
        )

    @classmethod
    def from_json(cls, json_str: str) -> Project:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_legacy_dict(self) -> dict[str, Any]:
        """Bridges new Project object into the legacy pipeline/server dictionary format."""
        return {
            "canvas": self.sprite.to_dict(),
            "frames": [f.to_dict() for f in self.frames],
            "meta": {
                "name": self.name,
                "version": self.version,
                "layers": [l.to_dict() for l in self.layers],
                "tags": [t.to_dict() for t in self.tags],
                "slices": [s.to_dict() for s in self.slices],
            },
        }

    @classmethod
    def from_legacy_dict(cls, data: dict[str, Any], name: str = "Untitled") -> Project:
        """Constructs a Project instance from a legacy pipeline/server dictionary."""
        canvas_dict = data.get("canvas", {})
        sprite = Sprite.from_dict(canvas_dict)
        raw_frames = data.get("frames", [])
        frames = [Frame.from_dict(f) for f in raw_frames]

        meta = data.get("meta", {})
        layers = [Layer.from_dict(l) for l in meta.get("layers", [])] if "layers" in meta else []
        tags = [Tag.from_dict(t) for t in meta.get("tags", [])] if "tags" in meta else []
        slices = [Slice.from_dict(s) for s in meta.get("slices", [])] if "slices" in meta else []

        proj = cls(
            name=str(meta.get("name", name)),
            version=str(meta.get("version", "2.0")),
            sprite=sprite,
            layers=layers,
            frames=frames,
            tags=tags,
            slices=slices,
        )
        return proj
