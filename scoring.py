"""Scoring and categorisation.

    score = base(category)
          + relevance (capped at RELEVANCE_MAX)
          + recency bonus
          + payment verified bonus
          - competition penalty (grows with proposal count)
          - off topic penalty

The result is clamped to 0-100 and mapped to a High / Medium / Low fit band.
"""

from typing import Dict, List, Tuple

import config
from models import Job


def _haystacks(job: Job) -> Tuple[str, str]:
    """Return (title, body) lowercased, body covering description and skills."""
    title = (job.title or "").lower()
    body = " ".join([
        (job.description or "").lower(),
        (job.skills_text or "").lower(),
    ])
    return title, body


def relevance_for(job: Job, category: str) -> Tuple[float, List[str]]:
    """How well the job matches one category, capped at RELEVANCE_MAX."""
    signals = config.CATEGORY_SIGNALS.get(category, {})
    title, body = _haystacks(job)
    score = 0.0
    hits: List[str] = []

    for term in signals.get("strong", []):
        if term in title:
            score += config.STRONG_TITLE_POINTS
            hits.append(term)
        elif term in body:
            score += config.STRONG_BODY_POINTS
            hits.append(term)

    for term in signals.get("weak", []):
        if term in title:
            score += config.WEAK_TITLE_POINTS
        elif term in body:
            score += config.WEAK_BODY_POINTS

    return min(score, config.RELEVANCE_MAX), hits


def off_topic_hits(job: Job, category: str) -> List[str]:
    """Off topic terms present in the job, ignoring ones exempt for the category."""
    title, body = _haystacks(job)
    text = f"{title} {body}"
    exempt = config.OFF_TOPIC_EXEMPT.get(category, set())
    return [term for term in config.OFF_TOPIC_TERMS
            if term in text and term not in exempt]


def competition_penalty(proposal_count) -> float:
    """Penalty that grows with the number of proposals already submitted."""
    if proposal_count is None:
        # Unknown competition, assume the middle of the allowed range.
        return 9.0
    penalty = 0.0
    for lower_bound, points in config.PROPOSAL_PENALTY:
        if proposal_count >= lower_bound:
            penalty = points
    return penalty


def recency_bonus(age_hours) -> float:
    """Small bonus that decays as the post gets older."""
    if age_hours is None:
        return 0.0
    for max_hours, points in config.RECENCY_BONUS:
        if age_hours <= max_hours:
            return points
    return 0.0


def choose_category(job: Job) -> Tuple[str, float, List[str], bool]:
    """Pick the best fitting category.

    Starts from the category whose search returned the job, but moves it when
    another category clearly fits the title and description better. Returns
    (category, relevance, hits, poor_fit).
    """
    scores: Dict[str, Tuple[float, List[str]]] = {
        category: relevance_for(job, category)
        for category in config.CATEGORY_ORDER
    }

    source = job.source_category if job.source_category in scores else config.CATEGORY_ORDER[0]
    source_relevance, source_hits = scores[source]

    best_category, (best_relevance, best_hits) = max(
        scores.items(), key=lambda item: item[1][0]
    )

    chosen, relevance, hits = source, source_relevance, source_hits
    if best_relevance >= source_relevance + config.REASSIGN_MARGIN:
        chosen, relevance, hits = best_category, best_relevance, best_hits

    poor_fit = relevance < config.POOR_FIT_RELEVANCE
    return chosen, relevance, hits, poor_fit


def fit_band(score: float) -> str:
    if score >= config.FIT_HIGH_MIN:
        return "High"
    if score >= config.FIT_MEDIUM_MIN:
        return "Medium"
    return "Low"


def score_job(job: Job) -> Job:
    """Fill in category, score, fit and a short explanation on the job."""
    category, relevance, hits, poor_fit = choose_category(job)
    off_topic = off_topic_hits(job, category)

    base = config.BASE_SCORES.get(category, 55)
    penalty_competition = competition_penalty(job.proposal_count)
    bonus_recency = recency_bonus(job.age_hours)
    bonus_verified = config.PAYMENT_VERIFIED_BONUS if job.payment_verified else 0
    penalty_off_topic = min(
        len(off_topic) * config.OFF_TOPIC_PENALTY, config.OFF_TOPIC_PENALTY_MAX
    )

    score = (
        base
        + relevance
        + bonus_recency
        + bonus_verified
        - penalty_competition
        - penalty_off_topic
    )

    # A job that matched a search keyword but says nothing about the service is
    # demoted rather than treated as on topic.
    if poor_fit:
        score -= 10

    job.category = category
    job.score = round(max(0.0, min(100.0, score)), 1)
    job.fit = fit_band(job.score)

    notes = [f"base {base}", f"relevance +{relevance:g}"]
    if bonus_recency:
        notes.append(f"recency +{bonus_recency:g}")
    if bonus_verified:
        notes.append(f"verified +{bonus_verified}")
    if penalty_competition:
        notes.append(f"competition -{penalty_competition:g}")
    if penalty_off_topic:
        notes.append(f"off topic -{penalty_off_topic:g} ({', '.join(off_topic[:3])})")
    if poor_fit:
        notes.append("poor fit -10")
    if hits:
        notes.append("matched: " + ", ".join(hits[:4]))
    job.score_notes = "; ".join(notes)
    return job


def _percentile(values: List[float], fraction: float) -> float:
    """Simple nearest rank percentile, no numpy dependency."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round(fraction * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def calibrate_fits(jobs: List[Job]) -> None:
    """Assign High / Medium / Low across the whole run.

    Uses the fixed thresholds for a small run, and this run's own tertiles for
    a normal sized one, so a day of heavy competition still surfaces its best
    listings instead of marking everything Low.
    """
    if not jobs:
        return

    high_cut, medium_cut = config.FIT_HIGH_MIN, config.FIT_MEDIUM_MIN

    if config.FIT_ADAPTIVE and len(jobs) >= config.FIT_ADAPTIVE_MIN_JOBS:
        scores = [job.score for job in jobs]
        high_cut = min(max(_percentile(scores, 2 / 3), config.FIT_HIGH_FLOOR),
                       config.FIT_HIGH_CEIL)
        medium_cut = min(max(_percentile(scores, 1 / 3), config.FIT_MEDIUM_FLOOR),
                         config.FIT_MEDIUM_CEIL)
        if medium_cut >= high_cut:
            medium_cut = high_cut - 1

    for job in jobs:
        if job.score <= config.FIT_HARD_LOW_MAX:
            job.fit = "Low"
        elif job.score >= high_cut:
            job.fit = "High"
        elif job.score >= medium_cut:
            job.fit = "Medium"
        else:
            job.fit = "Low"


def score_all(jobs: List[Job]) -> List[Job]:
    scored = [score_job(job) for job in jobs]
    calibrate_fits(scored)
    return scored


def dedupe(jobs: List[Job]) -> List[Job]:
    """Drop repeats across keyword searches, keyed on the numeric job id.

    When the same job turns up under two keywords the copy with the richer
    description wins, so the report keeps the most complete record.
    """
    best: Dict[str, Job] = {}
    for job in jobs:
        if not job.job_id:
            continue
        existing = best.get(job.job_id)
        if existing is None or len(job.description) > len(existing.description):
            if existing is not None:
                # Keep the first category that found it, the search that
                # matched first is the more specific one in config order.
                job.source_category = existing.source_category
                job.source_keyword = existing.source_keyword
            best[job.job_id] = job
    return list(best.values())


def filter_recent(jobs: List[Job], max_days: int = None) -> List[Job]:
    """Keep jobs inside the recency window, plus any whose age is unknown."""
    max_days = config.MAX_JOB_AGE_DAYS if max_days is None else max_days
    max_hours = max_days * 24
    return [job for job in jobs
            if job.age_hours is None or job.age_hours <= max_hours]
