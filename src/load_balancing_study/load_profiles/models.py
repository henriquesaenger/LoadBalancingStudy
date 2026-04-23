from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class LoadTypeProfile:
    name: str
    share: float
    service_time_multiplier: float


LOAD_WEIGHT_MULTIPLIERS: dict[str, float] = {
    "below-expected": 0.80,
    "expected": 1.00,
    "above-expected": 1.35,
}


def build_default_load_type_profiles(rng: random.Random) -> tuple[LoadTypeProfile, ...]:
    auth_share = rng.uniform(0.05, 0.08)
    read_share = 0.78 - auth_share
    return (
        LoadTypeProfile(name="read", share=read_share, service_time_multiplier=0.70),
        LoadTypeProfile(name="write", share=0.18, service_time_multiplier=1.15),
        LoadTypeProfile(name="report", share=0.04, service_time_multiplier=2.80),
        LoadTypeProfile(name="auth", share=auth_share, service_time_multiplier=0.85),
    )