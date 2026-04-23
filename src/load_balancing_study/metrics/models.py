from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServerDistribution:
    server_id: str
    served_requests: int
    share: float


@dataclass(frozen=True, slots=True)
class SourceDistribution:
    source: str
    total_requests: int
    served_requests: int
    dropped_requests: int


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    total_requests: int
    served_requests: int
    dropped_requests: int
    drop_rate: float
    throughput_rps: float
    avg_latency_seconds: float
    p95_latency_seconds: float
    avg_wait_seconds: float
    avg_service_seconds: float
    server_distribution: list[ServerDistribution]
    source_distribution: list[SourceDistribution]
