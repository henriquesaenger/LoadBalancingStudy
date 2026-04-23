from dataclasses import asdict

import streamlit as st

from load_balancing_study.algorithms import list_algorithms
from load_balancing_study.benchmark_presets import (
    estimate_default_total_requests,
    get_benchmark_preset,
    get_scenario_preset,
)
from load_balancing_study.ui.service import BenchmarkComparison, BenchmarkConfig, ScenarioConfig, run_benchmark_comparison


_SCENARIO_OPTIONS = (
    "constant",
    "burst",
    "poisson",
    "pareto-long-tail",
)

_SCENARIO_LABELS = {
    "constant": "Constant",
    "burst": "Burst",
    "poisson": "Poisson Arrivals",
    "pareto-long-tail": "Pareto Long Tail",
}

_DURATION_INPUT_KEY = "duration_seconds_input"
_SCENARIO_SELECT_KEY = "scenario_kind_select"
_TOTAL_REQUESTS_INPUT_KEY = "total_requests_input"


def _sync_total_requests_to_selected_scenario() -> None:
    scenario_kind = st.session_state[_SCENARIO_SELECT_KEY]
    duration_seconds = float(st.session_state[_DURATION_INPUT_KEY])
    st.session_state[_TOTAL_REQUESTS_INPUT_KEY] = estimate_default_total_requests(
        scenario_kind,
        duration_seconds,
    )


def _initialize_sidebar_state(benchmark_preset_duration: float, default_scenario_kind: str) -> None:
    if _DURATION_INPUT_KEY not in st.session_state:
        st.session_state[_DURATION_INPUT_KEY] = benchmark_preset_duration
    if _SCENARIO_SELECT_KEY not in st.session_state or st.session_state[_SCENARIO_SELECT_KEY] not in _SCENARIO_OPTIONS:
        st.session_state[_SCENARIO_SELECT_KEY] = default_scenario_kind
        st.session_state[_TOTAL_REQUESTS_INPUT_KEY] = estimate_default_total_requests(
            st.session_state[_SCENARIO_SELECT_KEY],
            float(st.session_state[_DURATION_INPUT_KEY]),
        )
    elif _TOTAL_REQUESTS_INPUT_KEY not in st.session_state:
        st.session_state[_TOTAL_REQUESTS_INPUT_KEY] = estimate_default_total_requests(
            st.session_state[_SCENARIO_SELECT_KEY],
            float(st.session_state[_DURATION_INPUT_KEY]),
        )


def render_app() -> None:
    st.set_page_config(
        page_title="Load Balancing Study UI",
        page_icon="LB",
        layout="wide",
    )
    st.title("Load Balancing Benchmark UI")
    st.caption("Compare the registered algorithms without rebuilding CLI commands by hand.")

    _render_sidebar_form()

    error_message = st.session_state.get("benchmark_error")
    if error_message:
        st.error(error_message)

    comparison: BenchmarkComparison | None = st.session_state.get("benchmark_comparison")
    config: BenchmarkConfig | None = st.session_state.get("benchmark_config")
    if comparison is None or config is None:
        st.info("Select the algorithms and benchmark parameters in the sidebar, then run the comparison.")
        return

    _render_summary(config, comparison)
    _render_comparison_table(comparison)
    _render_algorithm_details(comparison)


def _render_sidebar_form() -> None:
    available_algorithms = list_algorithms()
    benchmark_preset = get_benchmark_preset()
    _initialize_sidebar_state(benchmark_preset.duration_seconds, benchmark_preset.scenario_kind)

    with st.sidebar:
        st.header("Benchmark Parameters")
        algorithm_names = st.multiselect(
            "Algorithms",
            options=available_algorithms,
            default=available_algorithms,
            help="Choose one or more algorithms to compare under the same workload.",
        )
        duration_seconds = st.number_input(
            "Duration (seconds)",
            min_value=0.1,
            key=_DURATION_INPUT_KEY,
            step=1.0,
        )
        total_requests_value = int(
            st.number_input(
                "Total requests (0 = scenario default)",
                min_value=0,
                key=_TOTAL_REQUESTS_INPUT_KEY,
                step=1,
                help="When provided, generate exactly N requests within the selected duration instead of using the scenario default count.",
            )
        )
        server_count = int(
            st.number_input(
                "Servers",
                min_value=1,
                value=benchmark_preset.server_count,
                step=1,
            )
        )
        max_concurrent = int(
            st.number_input(
                "Max concurrent per server",
                min_value=1,
                value=benchmark_preset.max_concurrent,
                step=1,
            )
        )

        unlimited_queue = st.checkbox("Unlimited queue", value=False)
        queue_limit: int | None
        if unlimited_queue:
            queue_limit = None
        else:
            queue_limit = int(
                st.number_input(
                    "Queue limit per server",
                    min_value=1,
                    value=benchmark_preset.queue_limit,
                    step=1,
                )
            )

        seed_raw = st.text_input(
            "Seed (optional)",
            value="",
            help="Use the same seed to make workload generation deterministic across runs.",
        )
        scenario_kind = st.selectbox(
            "Scenario",
            options=_SCENARIO_OPTIONS,
            key=_SCENARIO_SELECT_KEY,
            on_change=_sync_total_requests_to_selected_scenario,
            format_func=lambda option: _SCENARIO_LABELS[option],
        )
        scenario_preset = get_scenario_preset(scenario_kind)

        scenario_kwargs: dict[str, object] = {
            "kind": scenario_kind,
        }
        if scenario_kind == "constant":
            scenario_kwargs["service_time_seconds"] = st.number_input(
                "Service time (seconds)",
                min_value=0.01,
                value=scenario_preset.service_time_seconds,
                step=0.05,
            )
            scenario_kwargs["requests_per_second"] = st.number_input(
                "Requests per second",
                min_value=0.1,
                value=scenario_preset.requests_per_second,
                step=0.5,
            )
        elif scenario_kind == "burst":
            scenario_kwargs["service_time_seconds"] = st.number_input(
                "Service time (seconds)",
                min_value=0.01,
                value=scenario_preset.service_time_seconds,
                step=0.05,
            )
            scenario_kwargs["base_requests_per_second"] = st.number_input(
                "Base requests per second",
                min_value=0.0,
                value=scenario_preset.base_requests_per_second,
                step=0.5,
            )
            scenario_kwargs["burst_requests_per_second"] = st.number_input(
                "Burst requests per second",
                min_value=0.0,
                value=scenario_preset.burst_requests_per_second,
                step=0.5,
            )
            scenario_kwargs["burst_start_seconds"] = st.number_input(
                "Burst start (seconds)",
                min_value=0.0,
                value=scenario_preset.burst_start_seconds,
                step=0.5,
            )
            scenario_kwargs["burst_end_seconds"] = st.number_input(
                "Burst end (seconds)",
                min_value=0.0,
                value=scenario_preset.burst_end_seconds,
                step=0.5,
            )
        elif scenario_kind == "poisson":
            scenario_kwargs["service_time_seconds"] = st.number_input(
                "Service time (seconds)",
                min_value=0.01,
                value=scenario_preset.service_time_seconds,
                step=0.05,
            )
            scenario_kwargs["requests_per_second"] = st.number_input(
                "Requests per second",
                min_value=0.1,
                value=scenario_preset.requests_per_second,
                step=0.5,
            )
        elif scenario_kind == "pareto-long-tail":
            scenario_kwargs["requests_per_second"] = st.number_input(
                "Requests per second",
                min_value=0.1,
                value=scenario_preset.requests_per_second,
                step=0.5,
            )
            scenario_kwargs["service_time_min_seconds"] = st.number_input(
                "Minimum service time (seconds)",
                min_value=0.01,
                value=scenario_preset.service_time_min_seconds,
                step=0.01,
                format="%.2f",
            )
            scenario_kwargs["service_time_alpha"] = st.number_input(
                "Pareto alpha",
                min_value=1.01,
                value=scenario_preset.service_time_alpha,
                step=0.1,
                help="Lower values create a heavier long tail. Alpha must be > 1.",
            )

        submitted = st.button(
            "Run comparison",
            type="primary",
            use_container_width=True,
        )

        st.caption("The UI reuses the same simulation engine and metrics used by the CLI.")

    if not submitted:
        return

    try:
        config = BenchmarkConfig(
            algorithm_names=tuple(algorithm_names),
            duration_seconds=float(duration_seconds),
            total_requests=total_requests_value or None,
            server_count=server_count,
            max_concurrent=max_concurrent,
            queue_limit=queue_limit,
            seed=_parse_seed(seed_raw),
            scenario=ScenarioConfig(**scenario_kwargs),
        )
        comparison = run_benchmark_comparison(config)
    except ValueError as exc:
        st.session_state["benchmark_error"] = str(exc)
        st.session_state.pop("benchmark_comparison", None)
        st.session_state.pop("benchmark_config", None)
    else:
        st.session_state["benchmark_error"] = None
        st.session_state["benchmark_comparison"] = comparison
        st.session_state["benchmark_config"] = config


def _render_summary(config: BenchmarkConfig, comparison: BenchmarkComparison) -> None:
    queue_label = "unlimited" if config.queue_limit is None else str(config.queue_limit)
    total_requests_label = "scenario default" if config.total_requests is None else str(config.total_requests)
    summary_columns = st.columns(6)
    summary_columns[0].metric("Generated requests", str(len(comparison.simulation_input.requests)))
    summary_columns[1].metric("Algorithms", str(len(comparison.results)))
    summary_columns[2].metric("Servers", str(config.server_count))
    summary_columns[3].metric("Max concurrent/server", str(config.max_concurrent))
    summary_columns[4].metric("Queue limit", queue_label)
    summary_columns[5].metric("Target requests", total_requests_label)

    st.caption(
        f"Scenario: {comparison.scenario_name} | Duration: {config.duration_seconds:.2f}s"
        + (" | Total requests: scenario default" if config.total_requests is None else f" | Total requests: {config.total_requests}")
        + (" | Seed: random" if config.seed is None else f" | Seed: {config.seed}")
    )


def _render_comparison_table(comparison: BenchmarkComparison) -> None:
    st.subheader("Comparison")
    table_data = {
        "algorithm": [result.algorithm_name for result in comparison.results],
        "total_requests": [result.metrics.total_requests for result in comparison.results],
        "served_requests": [result.metrics.served_requests for result in comparison.results],
        "dropped_requests": [result.metrics.dropped_requests for result in comparison.results],
        "drop_rate": [round(result.metrics.drop_rate, 4) for result in comparison.results],
        "throughput_rps": [round(result.metrics.throughput_rps, 4) for result in comparison.results],
        "avg_latency_s": [round(result.metrics.avg_latency_seconds, 4) for result in comparison.results],
        "p95_latency_s": [round(result.metrics.p95_latency_seconds, 4) for result in comparison.results],
        "avg_wait_s": [round(result.metrics.avg_wait_seconds, 4) for result in comparison.results],
    }
    st.dataframe(table_data, use_container_width=True, hide_index=True)


def _render_algorithm_details(comparison: BenchmarkComparison) -> None:
    st.subheader("Algorithm Details")
    tabs = st.tabs([result.algorithm_name for result in comparison.results])
    for tab, result in zip(tabs, comparison.results, strict=True):
        with tab:
            metric_columns = st.columns(4)
            metric_columns[0].metric("Throughput", f"{result.metrics.throughput_rps:.4f} rps")
            metric_columns[1].metric("Average latency", f"{result.metrics.avg_latency_seconds:.4f} s")
            metric_columns[2].metric("P95 latency", f"{result.metrics.p95_latency_seconds:.4f} s")
            metric_columns[3].metric("Average wait", f"{result.metrics.avg_wait_seconds:.4f} s")

            left_column, right_column = st.columns(2)
            with left_column:
                st.markdown("**Server distribution**")
                st.dataframe(_distribution_table(result.metrics.server_distribution), use_container_width=True, hide_index=True)
            with right_column:
                st.markdown("**Source distribution**")
                st.dataframe(_distribution_table(result.metrics.source_distribution), use_container_width=True, hide_index=True)


def _distribution_table(items: list[object]) -> dict[str, list[object]]:
    rows = [asdict(item) for item in items]
    if not rows:
        return {"status": ["no data"]}

    columns = list(rows[0].keys())
    return {
        column: [row[column] for row in rows]
        for column in columns
    }


def _parse_seed(raw_value: str) -> int | None:
    candidate = raw_value.strip()
    if not candidate:
        return None

    try:
        return int(candidate)
    except ValueError as exc:
        raise ValueError("seed must be an integer") from exc


render_app()