from dataclasses import dataclass
import random

from load_balancing_study.scenarios.base import (
    Scenario,
    ArrivalWindow,
    build_uniform_arrival_windows,
    default_total_requests_for_rate,
    modulate_arrival_windows,
    sample_arrival_times_with_exact_total,
    validate_total_requests,
)
from load_balancing_study.simulation.models import Request


@dataclass(frozen=True, slots=True)
class ConstantRateScenario(Scenario):
    requests_per_second: float
    service_time_seconds: float = 1.0
    name: str = "constant-rate"

    def generate_requests(
        self,
        duration_seconds: float,
        seed: int | None = None,
        total_requests: int | None = None,
    ) -> list[Request]:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        if duration_seconds <= 0:
            return []

        rng = random.Random(seed)
        requested_total = validate_total_requests(total_requests)
        exact_total = requested_total
        if exact_total is None:
            exact_total = default_total_requests_for_rate(duration_seconds, self.requests_per_second)

        windows = modulate_arrival_windows(
            build_uniform_arrival_windows(duration_seconds, self.requests_per_second),
            rng,
        )
        arrival_times = sample_arrival_times_with_exact_total(windows, exact_total, rng)

        return [
            Request(
                request_id=index + 1,
                arrival_time=arrival.arrival_time,
                service_time=self.service_time_seconds,
                load_weight=arrival.load_weight,
            )
            for index, arrival in enumerate(arrival_times)
        ]


@dataclass(frozen=True, slots=True)
class BurstScenario(Scenario):
    base_requests_per_second: float
    burst_requests_per_second: float
    burst_start_seconds: float
    burst_end_seconds: float
    service_time_seconds: float = 1.0
    time_resolution_seconds: float = 0.1
    name: str = "burst"

    def generate_requests(
        self,
        duration_seconds: float,
        seed: int | None = None,
        total_requests: int | None = None,
    ) -> list[Request]:
        if self.base_requests_per_second < 0:
            raise ValueError("base_requests_per_second must be >= 0")
        if self.burst_requests_per_second < 0:
            raise ValueError("burst_requests_per_second must be >= 0")
        if self.time_resolution_seconds <= 0:
            raise ValueError("time_resolution_seconds must be > 0")
        if self.burst_end_seconds < self.burst_start_seconds:
            raise ValueError("burst_end_seconds must be >= burst_start_seconds")
        if duration_seconds <= 0:
            return []

        rng = random.Random(seed)
        requested_total = validate_total_requests(total_requests)

        time_slots = _build_time_slots(
            duration_seconds=duration_seconds,
            time_resolution_seconds=self.time_resolution_seconds,
            burst_start_seconds=self.burst_start_seconds,
            burst_end_seconds=self.burst_end_seconds,
            base_requests_per_second=self.base_requests_per_second,
            burst_requests_per_second=self.burst_requests_per_second,
        )
        windows = modulate_arrival_windows(
            [
                ArrivalWindow(
                    start_time=arrival_time,
                    end_time=min(duration_seconds, arrival_time + self.time_resolution_seconds),
                    requests_per_second=rate,
                )
                for arrival_time, rate in time_slots
            ],
            rng,
        )

        if requested_total is None:
            requested_total = sum(
                int(rate * self.time_resolution_seconds)
                for _, rate in time_slots
            )
            if requested_total <= 0:
                return []

        arrival_times = sample_arrival_times_with_exact_total(windows, requested_total, rng)
        return [
            Request(
                request_id=index + 1,
                arrival_time=arrival.arrival_time,
                service_time=self.service_time_seconds,
                load_weight=arrival.load_weight,
            )
            for index, arrival in enumerate(arrival_times)
        ]


def _build_time_slots(
    duration_seconds: float,
    time_resolution_seconds: float,
    burst_start_seconds: float,
    burst_end_seconds: float,
    base_requests_per_second: float,
    burst_requests_per_second: float,
) -> list[tuple[float, float]]:
    time_slots: list[tuple[float, float]] = []
    current_time = 0.0
    while current_time < duration_seconds:
        in_burst = burst_start_seconds <= current_time < burst_end_seconds
        requests_per_second = burst_requests_per_second if in_burst else base_requests_per_second
        time_slots.append((current_time, requests_per_second))
        current_time += time_resolution_seconds

    return time_slots
