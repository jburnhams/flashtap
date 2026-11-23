"""Content packs: the skills Flashtap knows about, how they depend on each other, the phonics sequence and words, and
how a curriculum maps onto them. The packs are TOML files in `src/flashtap/packs/`; `docs/content.md` says how to
write one. `load()` returns them checked."""

from flashtap.content.registry import PACKS, ContentError, Problem, Registry, build, check, load, read
from flashtap.content.summary import ContentSummary, summarise

__all__ = [
    "PACKS",
    "ContentError",
    "ContentSummary",
    "Problem",
    "Registry",
    "build",
    "check",
    "load",
    "read",
    "summarise",
]
