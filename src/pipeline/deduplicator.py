from __future__ import annotations

import hashlib
from collections import defaultdict

from rapidfuzz import fuzz

from src.models.schema import JobOffer

SIMILARITY_THRESHOLD = 85  # minimum score to consider two offers as duplicates


def compute_dedup_key(offer: JobOffer) -> str:
    """Generate a normalized key for fast pre-filtering."""
    parts = [
        (offer.company_name or "").lower().strip(),
        (offer.location_city or "").lower().strip(),
    ]
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def are_duplicates(a: JobOffer, b: JobOffer) -> bool:
    """Check if two offers are likely duplicates (different sources, same real job)."""
    if a.source == b.source:
        return False

    # Must be same company (fuzzy)
    if a.company_name and b.company_name:
        company_score = fuzz.ratio(a.company_name.lower(), b.company_name.lower())
        if company_score < 70:
            return False
    else:
        return False

    # Must be same city
    if a.location_city and b.location_city:
        if a.location_city != b.location_city:
            return False

    # Title similarity
    title_score = fuzz.token_sort_ratio(a.title.lower(), b.title.lower())
    return title_score >= SIMILARITY_THRESHOLD


def deduplicate_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """Assign dedup_cluster_id to offers that appear to be the same job across sources.

    Uses pre-filtering by company+city hash to avoid O(n²) full comparisons.
    Only compares offers from different sources within the same bucket.
    """
    # Group offers by dedup key (company+city hash) for fast pre-filtering
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, offer in enumerate(offers):
        key = compute_dedup_key(offer)
        buckets[key].append(idx)

    cluster_id = 0

    for indices in buckets.values():
        if len(indices) < 2:
            continue

        for i_pos, i in enumerate(indices):
            offer_a = offers[i]
            if offer_a.dedup_cluster_id:
                continue

            for j in indices[i_pos + 1 :]:
                offer_b = offers[j]
                if offer_b.dedup_cluster_id:
                    continue

                if are_duplicates(offer_a, offer_b):
                    if not offer_a.dedup_cluster_id:
                        offer_a.dedup_cluster_id = f"cluster_{cluster_id}"
                        cluster_id += 1
                    offer_b.dedup_cluster_id = offer_a.dedup_cluster_id

    return offers
