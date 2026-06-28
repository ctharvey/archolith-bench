"""ArtifactMutator — the single writer for L4 artifacts (R9-lite, bench-first).

This is the ONLY thing that creates/promotes/supersedes artifacts (invariant 2). It
enforces the L4 invariants fail-closed so no other code path can mint a trusted fact:

- create() DERIVES status from source+evidence — there is no `status` parameter, so an
  LLM artifact structurally CANNOT be TRUSTED on write (invariant 4):
    * source=llm   -> always CANDIDATE
    * source=human -> TRUSTED iff it has >=1 PROMOTABLE evidence, else CANDIDATE (invariant 5)
- promote() flips CANDIDATE -> TRUSTED and REFUSES without >=1 promotable evidence (invariant 3).
  "Promotable" excludes agent_inference (LLM self-evidence): trust is never granted just
  because an LLM said so. Calling promote() is the review action (invariant 4).
- supersede() marks the old artifact HISTORICAL and links it — never deletes (invariant 7).

`load()` seeds pre-established state from a fixture and is intentionally NOT gated (a
fixture represents already-settled history); fixture integrity is checked separately
by the validator (commit 5), not here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import Artifact, ArtifactType, Evidence, Source, Status


class MutatorError(ValueError):
    """Raised when a write would violate an L4 invariant."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactMutator:
    """The only writer of L4 artifacts; enforces the invariants fail-closed."""

    def __init__(self, clock=_utc_now) -> None:
        self._store: dict[str, Artifact] = {}
        self._clock = clock

    # -- writes ---------------------------------------------------------------
    def create(
        self,
        *,
        id: str,
        type: ArtifactType,
        summary: str,
        source: Source,
        body: str = "",
        evidence: list[Evidence] | None = None,
        anchors: list[str] | None = None,
    ) -> Artifact:
        """Create an artifact with a DERIVED status (no status param by design)."""
        if id in self._store:
            raise MutatorError(f"artifact {id!r} already exists")
        ev = list(evidence or [])
        promotable = any(e.is_promotable for e in ev)  # agent_inference alone never trusts
        if source is Source.LLM:
            status = Status.CANDIDATE  # invariant 4: never trusted on write
        else:
            status = Status.TRUSTED if promotable else Status.CANDIDATE  # invariant 5
        art = Artifact(
            id=id, type=type, summary=summary, body=body, status=status, source=source,
            evidence=ev, anchors=list(anchors or []), created_at=self._clock(),
        )
        self._store[id] = art
        return art

    def promote(self, id: str, *, reviewed_by: str = "human") -> Artifact:
        """Review action: CANDIDATE -> TRUSTED. Refuses without evidence (invariant 3)."""
        art = self._require(id)
        if not art.has_promotable_evidence:
            raise MutatorError(
                f"cannot promote {id!r}: TRUSTED requires >=1 non-agent_inference evidence "
                "(invariant 3; LLM self-inference cannot justify trust)"
            )
        if art.is_historical:
            raise MutatorError(f"cannot promote {id!r}: it is historical/superseded")
        art.status = Status.TRUSTED
        return art

    def supersede(self, old_id: str, new_id: str) -> tuple[Artifact, Artifact]:
        """Mark old artifact HISTORICAL and link the pair — never deletes (invariant 7)."""
        if old_id == new_id:
            raise MutatorError("an artifact cannot supersede itself")
        old = self._require(old_id)
        new = self._require(new_id)
        old.status = Status.HISTORICAL
        old.superseded_by = new_id
        new.supersedes = old_id
        return old, new

    def load(self, artifacts: list[Artifact]) -> None:
        """Seed pre-established state (fixture). Not gated — validate fixtures separately."""
        for a in artifacts:
            self._store[a.id] = a

    # -- reads ----------------------------------------------------------------
    def get(self, id: str) -> Artifact | None:
        return self._store.get(id)

    def all(self) -> list[Artifact]:
        return list(self._store.values())

    def _require(self, id: str) -> Artifact:
        if id not in self._store:
            raise MutatorError(f"unknown artifact {id!r}")
        return self._store[id]
