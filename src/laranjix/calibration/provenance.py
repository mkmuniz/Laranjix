"""Where each calibration number came from, and what it takes to trust it.

A generator like this has a failure mode that is quieter than a bug: the numbers
that define what "normal" looks like get written by whoever set up the file --
or by a model helping them -- and nobody ever goes back to check them against
reality. The dataset then encodes an *assumption* about Brazilian payments, and
every model trained on it learns that assumption as if it were a measurement.

Nothing here makes a number correct. What it does is make an ungrounded number
**impossible to hide**: every parameter file has to declare its provenance, the
declaration has to carry the evidence that provenance requires, and anything
still unverified is listed by `laranjix calibration`, named in every dataset
certificate, and blocks a release.
"""

from __future__ import annotations

from enum import StrEnum


class Provenance(StrEnum):
    """How a parameter came to hold the value it holds."""

    REGULATORY = "regulatory"
    """Fixed by a norm, not estimated: the Pix night limit, the MED deadline."""

    PUBLIC_STATISTIC = "public_statistic"
    """Derived from a published aggregate, with the source and the date it was read."""

    EXPERT_REVIEW = "expert_review"
    """A named person with stated credentials examined the value and signed off."""

    UNVERIFIED = "unverified"
    """Written by an author or a model, grounded in nothing external yet.

    Legitimate while building -- a generator cannot wait for every number to be
    sourced before it runs once. Not legitimate in a release, which is why this
    value fails :func:`require_grounded`.
    """


#: What each provenance has to show for itself.
REQUIRED_EVIDENCE: dict[Provenance, tuple[str, ...]] = {
    Provenance.REGULATORY: ("source",),
    Provenance.PUBLIC_STATISTIC: ("source", "source_url", "retrieved_at"),
    Provenance.EXPERT_REVIEW: ("reviewed_by", "reviewed_at"),
    Provenance.UNVERIFIED: ("note",),
}

GROUNDED = frozenset({Provenance.REGULATORY, Provenance.PUBLIC_STATISTIC, Provenance.EXPERT_REVIEW})


def parse(value: object, parameter_id: str) -> Provenance:
    """Return the declared provenance, or explain why it is not acceptable."""
    if value is None:
        raise ValueError(
            f"{parameter_id}: meta.provenance e obrigatorio. "
            f"Use um de: {', '.join(item.value for item in Provenance)}"
        )
    try:
        return Provenance(str(value))
    except ValueError:
        raise ValueError(
            f"{parameter_id}: provenance {value!r} nao existe. "
            f"Use um de: {', '.join(item.value for item in Provenance)}"
        ) from None


def missing_evidence(provenance: Provenance, meta: dict[str, object]) -> list[str]:
    """Return the fields this provenance requires and the file does not have."""
    return [field for field in REQUIRED_EVIDENCE[provenance] if not meta.get(field)]
