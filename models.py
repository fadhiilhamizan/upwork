"""Shared data structures."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Job:
    """One Upwork job listing, as scraped and then enriched by scoring."""

    job_id: str
    title: str
    url: str
    description: str = ""
    posted_text: str = ""
    age_hours: Optional[float] = None
    proposals_text: str = ""
    proposal_count: Optional[int] = None
    payment_verified: bool = False
    location: str = ""
    rate: str = ""
    price_type: str = ""
    skills: List[str] = field(default_factory=list)

    # Where the job came from
    source_category: str = ""
    source_keyword: str = ""

    # Filled in by scoring.py
    category: str = ""
    score: float = 0.0
    fit: str = ""
    score_notes: str = ""

    # Filled in by pull_jobs.py from seen_jobs.json
    is_new: bool = True

    @property
    def skills_text(self) -> str:
        return ", ".join(self.skills)

    @property
    def age_days(self) -> Optional[float]:
        return None if self.age_hours is None else self.age_hours / 24.0
