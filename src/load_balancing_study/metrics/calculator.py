import math
from collections import Counter
from collections.abc import Sequence

from load_balancing_study.metrics.models import ServerDistribution, SimulationMetrics, SourceDistribution
from load_balancing_study.simulation.models import SimulationInput, SimulationOutput


def calculate_metrics(
    simulation_input: SimulationInput,
    simulation_output: SimulationOutput,
    server_ids: Sequence[str] | None = None,
) -> SimulationMetrics:
    total_requests = len(simulation_input.requests)
    served_requests = len(simulation_output.assignments)
    dropped_by_count = max(0, total_requests - served_requests)
    dropped_requests = max(simulation_output.dropped_requests, dropped_by_count)

    request_by_id = {request.request_id: request for request in simulation_input.requests}

    latencies: list[float] = []
    waits: list[float] = []
    service_times: list[float] = []
    served_by_server: Counter[str] = Counter()
    served_by_source: Counter[str] = Counter()

    for assignment in simulation_output.assignments:
        request = request_by_id.get(assignment.request_id)
        if request is None:
            continue

        latencies.append(assignment.end_time - request.arrival_time)
        waits.append(assignment.start_time - request.arrival_time)
        service_times.append(assignment.end_time - assignment.start_time)

        served_by_server[assignment.server_id] += 1
        served_by_source[request.source] += 1

    all_servers = list(server_ids) if server_ids is not None else sorted(served_by_server.keys())
    server_distribution: list[ServerDistribution] = []
    for server_id in all_servers:
        count = served_by_server.get(server_id, 0)
        share = (count / served_requests) if served_requests else 0.0
        server_distribution.append(
            ServerDistribution(
                server_id=server_id,
                served_requests=count,
                share=share,
            )
        )

    total_by_source: Counter[str] = Counter(request.source for request in simulation_input.requests)
    source_distribution: list[SourceDistribution] = []
    for source in sorted(total_by_source.keys()):
        total_for_source = total_by_source[source]
        served_for_source = served_by_source.get(source, 0)
        source_distribution.append(
            SourceDistribution(
                source=source,
                total_requests=total_for_source,
                served_requests=served_for_source,
                dropped_requests=max(0, total_for_source - served_for_source),
            )
        )

    drop_rate = (dropped_requests / total_requests) if total_requests else 0.0
    throughput = (served_requests / simulation_input.duration_seconds) if simulation_input.duration_seconds > 0 else 0.0

    return SimulationMetrics(
        total_requests=total_requests,
        served_requests=served_requests,
        dropped_requests=dropped_requests,
        drop_rate=drop_rate,
        throughput_rps=throughput,
        avg_latency_seconds=_mean(latencies),
        p95_latency_seconds=_percentile(latencies, 95),
        avg_wait_seconds=_mean(waits),
        avg_service_seconds=_mean(service_times),
        server_distribution=server_distribution,
        source_distribution=source_distribution,
    )


def _mean(values: Sequence[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _percentile(values: Sequence[float], percentile: int) -> float:
    if not values:
        return 0.0

    sorted_values = sorted(values)
    rank = math.ceil((percentile / 100) * len(sorted_values)) - 1
    rank = max(0, min(rank, len(sorted_values) - 1))
    return sorted_values[rank]
