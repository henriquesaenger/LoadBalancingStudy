from collections.abc import Sequence
from dataclasses import replace
import random

from load_balancing_study.load_profiles.models import LOAD_WEIGHT_MULTIPLIERS, LoadTypeProfile, build_default_load_type_profiles
from load_balancing_study.simulation.models import Request


def assign_general_load_types(requests: Sequence[Request], seed: int | None = None) -> list[Request]:
    if not requests:
        return []

    rng = random.Random(seed if seed is not None else None)
    profiles = build_default_load_type_profiles(rng)
    counts = _distribute_total_requests(len(requests), [profile.share for profile in profiles])

    profile_assignments: list[LoadTypeProfile] = []
    for profile, count in zip(profiles, counts, strict=True):
        profile_assignments.extend([profile] * count)

    rng.shuffle(profile_assignments)

    assigned_requests: list[Request] = []
    for request, profile in zip(requests, profile_assignments, strict=True):
        load_weight = _normalize_load_weight(request.load_weight)
        service_multiplier = LOAD_WEIGHT_MULTIPLIERS[load_weight] * profile.service_time_multiplier
        assigned_requests.append(
            replace(
                request,
                service_time=max(0.000001, request.service_time * service_multiplier),
                load_type=profile.name,
                load_weight=load_weight,
                source=f"{profile.name}-{load_weight}",
            )
        )

    return assigned_requests


def _distribute_total_requests(total_requests: int, shares: Sequence[float]) -> list[int]:
    if total_requests <= 0:
        return [0] * len(shares)

    total_share = sum(shares)
    raw_counts = [(share / total_share) * total_requests for share in shares]
    counts = [int(raw_count) for raw_count in raw_counts]
    remainder = total_requests - sum(counts)
    ranked_indexes = sorted(
        range(len(shares)),
        key=lambda index: (raw_counts[index] - counts[index], shares[index]),
        reverse=True,
    )

    for index in ranked_indexes[:remainder]:
        counts[index] += 1

    return counts


def _normalize_load_weight(load_weight: str) -> str:
    normalized = load_weight.strip().lower()
    legacy_aliases = {
        "lull": "below-expected",
        "normal": "expected",
        "surge": "above-expected",
    }
    normalized = legacy_aliases.get(normalized, normalized)
    if normalized not in LOAD_WEIGHT_MULTIPLIERS:
        return "expected"
    return normalized