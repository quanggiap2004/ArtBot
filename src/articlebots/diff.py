"""Decide what to upload by comparing local and remote (slug, hash) maps."""

from dataclasses import dataclass, field


@dataclass
class Plan:
    added: list[str] = field(default_factory=list)      # slugs new to the store
    updated: list[str] = field(default_factory=list)    # slugs whose content changed
    skipped: list[str] = field(default_factory=list)    # slugs already current

    def summary(self) -> str:
        return (
            f"RESULT added={len(self.added)} "
            f"updated={len(self.updated)} "
            f"skipped={len(self.skipped)}"
        )


def classify(local: dict[str, str], remote: dict[str, str]) -> Plan:
    """local and remote both map slug -> hash8."""
    plan = Plan()
    for slug, digest in sorted(local.items()):
        if slug not in remote:
            plan.added.append(slug)
        elif remote[slug] != digest:
            plan.updated.append(slug)
        else:
            plan.skipped.append(slug)
    return plan
