from __future__ import annotations
import json, os, hashlib
from dataclasses import dataclass, field
from typing import Optional
from config import TOTAL_SLOTS, DEFAULT_WEIGHT_RANGES, PRESETS_FILE, WEIGHT_COLORS


def _default_ranges_signature() -> str:
    """
    Stable hash of config.py's current DEFAULT_WEIGHT_RANGES. Stored
    inside the saved "Default 66 Ranges" preset so SlotManager can tell,
    on next load, whether config.py's defaults have changed since that
    preset was written — and if so, discard the stale preset and rebuild
    fresh instead of silently reapplying old ranges forever.
    """
    payload = json.dumps(DEFAULT_WEIGHT_RANGES, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DEFAULT_PRESET_NAME = "Default 66 Ranges"


@dataclass
class Slot:
    index:       int
    min_ct:      float = 0.0
    max_ct:      float = 0.0
    count:       int   = 0
    diamond_ids: list  = field(default_factory=list)
    sorted_color: str  = ""   # empty = no diamond sorted yet

    @property
    def is_configured(self) -> bool:
        return self.max_ct > 0

    @property
    def has_been_sorted(self) -> bool:
        """True only after a diamond has been placed in this slot."""
        return self.sorted_color != ""

    @property
    def color(self) -> str:
        if not self.is_configured:
            return "#1c201c"
        pct = self.index / max(1, TOTAL_SLOTS - 1)
        color_idx = int(pct * (len(WEIGHT_COLORS) - 1))
        return WEIGHT_COLORS[color_idx]

    def accepts(self, weight_ct: float) -> bool:
        return self.is_configured and self.min_ct <= weight_ct < self.max_ct


@dataclass
class Preset:
    name:  str
    slots: list   # list of dicts {min_ct, max_ct}
    signature: str = ""   # only meaningful for the auto-generated default preset

    def to_dict(self) -> dict:
        return {"name": self.name, "slots": self.slots, "signature": self.signature}

    @classmethod
    def from_dict(cls, d: dict) -> "Preset":
        return cls(
            name=d["name"],
            slots=d.get("slots", []),
            signature=d.get("signature", ""),
        )


class SlotManager:
    def __init__(self):
        self.slots:   list[Slot]   = [Slot(i) for i in range(TOTAL_SLOTS)]
        self.presets: list[Preset] = []
        self._load_presets()
        self._build_default_preset()

    # ── SLOT OPERATIONS ───────────────────────────────────────────────────────

    def configure_slot(self, index: int, min_ct: float, max_ct: float):
        if 0 <= index < TOTAL_SLOTS:
            self.slots[index].min_ct = min_ct
            self.slots[index].max_ct = max_ct

    def find_slot_for_weight(self, weight_ct: float) -> Optional[int]:
        """Return slot index for given weight, or None if no match."""
        for slot in self.slots:
            if slot.accepts(weight_ct):
                return slot.index
        return None

    def record_diamond(self, slot_index: int, diamond_id: str):
        if 0 <= slot_index < TOTAL_SLOTS:
            self.slots[slot_index].count += 1
            self.slots[slot_index].diamond_ids.append(diamond_id)

    def reset_counts(self):
        for s in self.slots:
            s.count = 0
            s.diamond_ids.clear()
            s.sorted_color = ""   # clear color on reset

    def apply_preset(self, preset: Preset):
        self.reset_counts()
        for i, cfg in enumerate(preset.slots):
            if i < TOTAL_SLOTS:
                self.slots[i].min_ct = cfg.get("min_ct", 0.0)
                self.slots[i].max_ct = cfg.get("max_ct", 0.0)

    # ── PRESETS ───────────────────────────────────────────────────────────────

    def save_preset(self, name: str, signature: str = "") -> Preset:
        slot_cfgs = [{"min_ct": s.min_ct, "max_ct": s.max_ct} for s in self.slots]
        p = Preset(name=name, slots=slot_cfgs, signature=signature)
        self.presets = [x for x in self.presets if x.name != name]
        self.presets.append(p)
        self._save_presets()
        return p

    def delete_preset(self, name: str):
        self.presets = [p for p in self.presets if p.name != name]
        self._save_presets()

    def _build_default_preset(self):
        """
        Assign one unique weight range per slot from DEFAULT_WEIGHT_RANGES
        in config.py — but only if there's no saved default preset yet,
        OR the saved default preset's signature no longer matches
        config.py's current DEFAULT_WEIGHT_RANGES (meaning the operator
        edited the ranges in config.py since that preset was written).

        This prevents an old presets.json from silently locking in stale
        slot ranges forever after config.py changes — e.g. previously
        blocking only A1-A5 and reassigning B1/C1/D1/D3/E1, now blocking
        A1-A5 AND B1-B6 with sequential ranges from C1.

        User-created custom presets (any name other than the default) are
        never touched by this check — only the auto-generated default
        preset is signature-checked and regenerated.
        """
        current_sig = _default_ranges_signature()

        existing_default = next(
            (p for p in self.presets if p.name == DEFAULT_PRESET_NAME), None
        )

        if existing_default is not None and existing_default.signature == current_sig:
            # Saved default preset matches config.py's current defaults —
            # safe to apply as-is.
            self.apply_preset(existing_default)
            return

        if existing_default is not None and existing_default.signature != current_sig:
            print("[SlotManager] config.py DEFAULT_WEIGHT_RANGES changed since "
                  "presets.json was last written — regenerating default preset.")

        # No default preset yet, OR it's stale — rebuild fresh from
        # config.py and overwrite the saved default preset with the new
        # signature so this only happens once per config.py change.
        for i, r in enumerate(DEFAULT_WEIGHT_RANGES):
            if i < TOTAL_SLOTS:
                self.slots[i].min_ct = r["min_ct"]
                self.slots[i].max_ct = r["max_ct"]
        self.save_preset(DEFAULT_PRESET_NAME, signature=current_sig)

    def _load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE) as f:
                    data = json.load(f)
                self.presets = [Preset.from_dict(d) for d in data]
            except Exception:
                self.presets = []

    def _save_presets(self):
        try:
            with open(PRESETS_FILE, "w") as f:
                json.dump([p.to_dict() for p in self.presets], f, indent=2)
        except Exception:
            pass