from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
import math
import random

from load_balancing_study.simulation.models import Request

_TARGET_WINDOW_COUNT = 24
_MIN_WINDOW_SECONDS = 0.25
_MAX_WINDOW_SECONDS = 5.0
_SMOOTHING_FACTOR = 0.65
_MIN_SCALE = 0.55
_MAX_SCALE = 1.45


@dataclass(frozen=True, slots=True)
class ArrivalWindow:
    start_time: float
    end_time: float
    requests_per_second: float
    load_weight: str = "expected"


@dataclass(frozen=True, slots=True)
class ArrivalSample:
    arrival_time: float
    load_weight: str


class Scenario(ABC):
    name: str

    @abstractmethod
    def generate_requests(
        self,
        duration_seconds: float,
        seed: int | None = None,
        total_requests: int | None = None,
    ) -> list[Request]:
        raise NotImplementedError


def validate_total_requests(total_requests: int | None) -> int | None:
    if total_requests is None:
        return None
    if total_requests <= 0:
        raise ValueError("total_requests must be > 0 when provided")
    return total_requests


def build_uniform_arrival_windows(duration_seconds: float, requests_per_second: float) -> list[ArrivalWindow]:
    if duration_seconds <= 0:
        return []

    window_seconds = min(
        _MAX_WINDOW_SECONDS,
        max(_MIN_WINDOW_SECONDS, duration_seconds / _TARGET_WINDOW_COUNT),
    )
    windows: list[ArrivalWindow] = []
    current_time = 0.0

    while current_time < duration_seconds:
        end_time = min(duration_seconds, current_time + window_seconds)
        windows.append(
            ArrivalWindow(
                start_time=current_time,
                end_time=end_time,
                requests_per_second=requests_per_second,
                load_weight="expected",
            )
        )
        current_time = end_time

    return windows


def modulate_arrival_windows(
    windows: Sequence[ArrivalWindow],
    rng: random.Random,
) -> list[ArrivalWindow]:
    modulated_windows: list[ArrivalWindow] = []
    previous_scale = 1.0

    for window in windows:
        if window.end_time <= window.start_time or window.requests_per_second <= 0:
            modulated_windows.append(
                ArrivalWindow(
                    start_time=window.start_time,
                    end_time=window.end_time,
                    requests_per_second=0.0,
                    load_weight=window.load_weight,
                )
            )
            continue

        target_scale = rng.uniform(0.75, 1.25)
        scale = (previous_scale * _SMOOTHING_FACTOR) + (target_scale * (1.0 - _SMOOTHING_FACTOR))

        event_roll = rng.random()
        if event_roll < 0.08:
            scale *= rng.uniform(0.55, 0.80)
        elif event_roll > 0.92:
            scale *= rng.uniform(1.20, 1.60)

        scale = min(_MAX_SCALE, max(_MIN_SCALE, scale))
        modulated_windows.append(
            ArrivalWindow(
                start_time=window.start_time,
                end_time=window.end_time,
                requests_per_second=window.requests_per_second * scale,
                load_weight=_resolve_window_load_weight(scale),
            )
        )
        previous_scale = scale

    return modulated_windows


def distribute_total_requests(total_requests: int, weights: Sequence[float]) -> list[int]:
    if total_requests <= 0:
        return [0] * len(weights)

    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("request distribution requires at least one positive weight")

    raw_counts = [(weight / total_weight) * total_requests for weight in weights]
    counts = [int(raw_count) for raw_count in raw_counts]
    remainder = total_requests - sum(counts)
    ranked_indexes = sorted(
        range(len(weights)),
        key=lambda index: (raw_counts[index] - counts[index], weights[index]),
        reverse=True,
    )

    for index in ranked_indexes[:remainder]:
        counts[index] += 1

    return counts


def sample_arrival_times_with_exact_total(
    windows: Sequence[ArrivalWindow],
    total_requests: int,
    rng: random.Random,
) -> list[ArrivalSample]:
    if total_requests <= 0:
        return []

    weights = [window.requests_per_second * (window.end_time - window.start_time) for window in windows]
    counts = distribute_total_requests(total_requests, weights)
    arrivals: list[ArrivalSample] = []

    for window, count in zip(windows, counts, strict=True):
        if count <= 0:
            continue

        span = window.end_time - window.start_time
        arrivals.extend(
            ArrivalSample(
                arrival_time=window.start_time + (rng.random() * span),
                load_weight=window.load_weight,
            )
            for _ in range(count)
        )

    arrivals.sort(key=lambda arrival: arrival.arrival_time)
    return arrivals


def sample_piecewise_poisson_arrivals(
    windows: Sequence[ArrivalWindow],
    rng: random.Random,
) -> list[ArrivalSample]:
    arrivals: list[ArrivalSample] = []

    for window in windows:
        if window.requests_per_second <= 0:
            continue

        current_time = window.start_time
        while True:
            current_time += rng.expovariate(window.requests_per_second)
            if current_time >= window.end_time:
                break
            arrivals.append(
                ArrivalSample(
                    arrival_time=current_time,
                    load_weight=window.load_weight,
                )
            )

    arrivals.sort(key=lambda arrival: arrival.arrival_time)
    return arrivals


def default_total_requests_for_rate(duration_seconds: float, requests_per_second: float) -> int:
    if duration_seconds <= 0 or requests_per_second <= 0:
        return 0
    return max(1, math.ceil(duration_seconds * requests_per_second))


def _resolve_window_load_weight(scale: float) -> str:
    if scale <= 0.9:
        return "below-expected"
    if scale >= 1.1:
        return "above-expected"
    return "expected"
