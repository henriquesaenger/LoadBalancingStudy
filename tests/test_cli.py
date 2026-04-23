import json
import io
from contextlib import redirect_stderr, redirect_stdout

from load_balancing_study.cli.main import _build_workloads, build_parser, main
from load_balancing_study.scenarios import BurstScenario, ParetoLongTailScenario, PoissonArrivalScenario


def test_cli_runs_simulation_with_simultaneous_workloads() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = 0
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "--algorithm",
                "least-connections",
                "--duration",
                "4",
                "--servers",
                "2",
                "--max-concurrent",
                "1",
                "--queue-limit",
                "10",
                "--workload",
                "steady:constant:rps=2,service=0.5,start=0,duration=3",
                "--workload",
                "burst:constant:rps=4,service=0.5,start=1,duration=2",
            ]
        )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    output = stdout.getvalue()
    assert "Simulation Report" in output
    assert "comparison:" in output
    assert "algorithm" in output
    assert "least-connections" in output
    assert "drop_rate" in output


def test_cli_uses_all_algorithms_by_default() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(["--duration", "3", "--rps", "2"])

    assert exit_code == 0
    assert stderr.getvalue() == ""
    output = stdout.getvalue()
    assert "least-connections" in output
    assert "random" in output
    assert "round-robin" in output


def test_cli_parser_uses_realistic_defaults() -> None:
    args = build_parser().parse_args([])

    assert args.duration == 300.0
    assert args.servers == 4
    assert args.max_concurrent == 8
    assert args.queue_limit == 15
    assert args.scenario == "poisson"
    assert args.rps is None
    assert args.service_time is None
    assert args.base_rps is None
    assert args.burst_rps is None
    assert args.burst_start is None
    assert args.burst_end is None


def test_cli_uses_burst_specific_default_service_time() -> None:
    args = build_parser().parse_args(["--scenario", "burst"])

    workloads = _build_workloads(args)

    assert len(workloads) == 1
    assert isinstance(workloads[0].scenario, BurstScenario)
    assert workloads[0].scenario.service_time_seconds == 0.10


def test_cli_uses_poisson_default_service_time() -> None:
    args = build_parser().parse_args([])

    workloads = _build_workloads(args)

    assert len(workloads) == 1
    assert isinstance(workloads[0].scenario, PoissonArrivalScenario)
    assert workloads[0].scenario.service_time_seconds == 0.08
    assert workloads[0].scenario.requests_per_second == 220.0


def test_cli_uses_pareto_specific_defaults() -> None:
    args = build_parser().parse_args(["--scenario", "pareto-long-tail"])

    workloads = _build_workloads(args)

    assert len(workloads) == 1
    assert isinstance(workloads[0].scenario, ParetoLongTailScenario)
    assert workloads[0].scenario.requests_per_second == 180.0
    assert workloads[0].scenario.service_time_min_seconds == 0.05
    assert workloads[0].scenario.service_time_alpha == 1.4


def test_cli_returns_error_for_invalid_workload_spec() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(["--workload", "invalid-spec"])

    assert exit_code == 2
    assert "error:" in stderr.getvalue()


def test_cli_supports_poisson_scenario() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "--algorithm",
                "least-connections",
                "--scenario",
                "poisson",
                "--duration",
                "5",
                "--rps",
                "8",
                "--service-time",
                "0.15",
                "--output",
                "json",
            ]
        )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["workloads"][0]["scenario"] == "poisson"
    assert payload["comparative_metrics"][0]["metrics"]["total_requests"] > 0


def test_cli_supports_pareto_long_tail_scenario() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "--algorithm",
                "least-connections",
                "--scenario",
                "pareto-long-tail",
                "--duration",
                "5",
                "--rps",
                "8",
                "--service-time-min",
                "0.05",
                "--service-time-alpha",
                "1.5",
                "--output",
                "json",
            ]
        )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["workloads"][0]["scenario"] == "pareto-long-tail"
    assert payload["comparative_metrics"][0]["metrics"]["avg_service_seconds"] >= 0.05
