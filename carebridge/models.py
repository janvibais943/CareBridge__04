from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

# Provenance labels: this is how facts are separated from assumptions.
EXTRACTED = "extracted"            # verbatim in a source document, with a citation
INFERRED = "inferred"              # derived by the system (date maths, cross-document link)
NEEDS = "needs_confirmation"       # ambiguous / conflicting / missing -> human decides


@dataclass
class Source:
    file: str
    page: int
    quote: str


@dataclass
class Document:
    name: str
    pages: list
    doc_type: str = "unknown"
    doc_date: Optional[str] = None

    @property
    def text(self) -> str:
        return "\n".join(self.pages)


@dataclass
class Fact:
    id: str
    kind: str                      # medication | lab_result | instruction | referral | appointment | visit | patient_question
    date: Optional[str]
    description: str
    label: str
    source: Source
    data: dict = field(default_factory=dict)
    confidence: float = 0.9
    review_status: str = "pending"  # pending | approved | rejected
    conflict_group: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Reminder:
    id: str
    title: str
    due: str
    label: str
    basis: Source
    status: str                    # overdue | due_soon | upcoming
    review_status: str = "pending"

    def to_dict(self):
        return asdict(self)


@dataclass
class ChecklistItem:
    text: str
    label: str
    source: Optional[Source] = None
    category: str = "bring"        # bring | confirm | missing | question | followup
