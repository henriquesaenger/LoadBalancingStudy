import random
from dataclasses import dataclass

from load_balancing_study.scenarios.base import (
    Scenario,
    build_uniform_arrival_windows,
    default_total_requests_for_rate,
    modulate_arrival_windows,
    sample_arrival_times_with_exact_total,
    sample_piecewise_poisson_arrivals,
    validate_total_requests,
)
from load_balancing_study.simulation.models import Request


@dataclass(frozen=True, slots=True)
class PoissonArrivalScenario(Scenario):
    requests_per_second: float
    service_time_seconds: float = 1.0
    name: str = "poisson"

    def generate_requests(
        self,
        duration_seconds: float,
        seed: int | None = None,
        total_requests: int | None = None,
    ) -> list[Request]:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        if self.service_time_seconds <= 0:
            raise ValueError("service_time_seconds must be > 0")
        if duration_seconds <= 0:
            return []

        rng = random.Random(seed)
        requested_total = validate_total_requests(total_requests)
        windows = modulate_arrival_windows(
            build_uniform_arrival_windows(duration_seconds, self.requests_per_second),
            rng,
        )

        if requested_total is not None:
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

        arrival_times = sample_piecewise_poisson_arrivals(windows, rng)
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
class ParetoLongTailScenario(Scenario):
    requests_per_second: float
    service_time_min_seconds: float = 0.05
    service_time_alpha: float = 1.5
    name: str = "pareto-long-tail"

    def generate_requests(
        self,
        duration_seconds: float,
        seed: int | None = None,
        total_requests: int | None = None,
    ) -> list[Request]:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        if self.service_time_min_seconds <= 0:
            raise ValueError("service_time_min_seconds must be > 0")
        if self.service_time_alpha <= 1:
            raise ValueError("service_time_alpha must be > 1")
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
                service_time=_sample_pareto_service_time(
                    rng,
                    minimum_seconds=self.service_time_min_seconds,
                    alpha=self.service_time_alpha,
                ),
                load_weight=arrival.load_weight,
            )
            for index, arrival in enumerate(arrival_times)
        ]


def _sample_pareto_service_time(rng: random.Random, minimum_seconds: float, alpha: float) -> float:
    return minimum_seconds * rng.paretovariate(alpha)