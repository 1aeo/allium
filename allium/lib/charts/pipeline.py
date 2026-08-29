"""Chart-pass entry point. HTML stays Jinja-only; matplotlib stays in spawn."""

import importlib
import importlib.util
import os
import time
from collections import OrderedDict, namedtuple

from ..bandwidth_utils import build_bandwidth_map
from .cache import (
    build_relay_bandwidth_1m_payload,
    cache_hit,
    cache_key,
    cached_png_path,
    publish_png,
    published_png_path,
    sidecar_path,
    write_sidecar,
)
from .series import (
    PERIOD_KEYS,
    chartable_fingerprints,
    is_relay_fingerprint,
    overlays_for_relay,
    precompute_overlays,
    series_by_fp,
)


class ChartSpec(object):
    __slots__ = (
        "chart_id",
        "output_path_pattern",
        "cache_subdir",
        "renderer_module",
        "renderer_name",
        "renderer_version",
    )

    def __init__(
        self,
        chart_id,
        output_path_pattern,
        cache_subdir,
        renderer_module,
        renderer_name,
        renderer_version,
    ):
        self.chart_id = chart_id
        self.output_path_pattern = output_path_pattern
        self.cache_subdir = cache_subdir
        self.renderer_module = renderer_module
        self.renderer_name = renderer_name
        self.renderer_version = str(renderer_version)

    def output_path(self, fingerprint):
        return self.output_path_pattern.format(fingerprint=fingerprint)


def _bandwidth_spec(suffix):
    return ChartSpec(
        chart_id="relay_bandwidth_%s" % suffix,
        output_path_pattern="relay/{fingerprint}/bandwidth-%s.png" % suffix,
        cache_subdir="relay_bandwidth_%s" % suffix,
        renderer_module="allium.lib.charts.bandwidth",
        renderer_name="render_relay_bandwidth_1m",
        renderer_version="3",
    )


PERIOD_SPEC_BY_SUFFIX = OrderedDict(
    (suffix, _bandwidth_spec(suffix)) for _onionoo, suffix in PERIOD_KEYS
)
RELAY_BANDWIDTH_1M = PERIOD_SPEC_BY_SUFFIX["1m"]
RELAY_BANDWIDTH_PERIODS = tuple(PERIOD_SPEC_BY_SUFFIX.values())

_REGISTRY = OrderedDict(
    (spec.chart_id, spec) for spec in RELAY_BANDWIDTH_PERIODS
)


def get_chart(chart_id):
    return _REGISTRY.get(chart_id)


_Selection = namedtuple(
    "_Selection", "details bw_map series selected bandwidth_data"
)

CHARTS_OFF = "off"
CHARTS_AUTO = "auto"
CHARTS_ON = "on"
CHARTS_MODES = (CHARTS_OFF, CHARTS_AUTO, CHARTS_ON)
# Memory-safe ceiling and auto default: min(CPU, 16). Spawn+Agg is ~0.4–0.6 GiB
# per worker; the parent still holds onionoo (~4–6 GiB). Last 4-worker generate
# peaked ~8.3 GiB. 16 workers add ~6–8 GiB. Never start 4 isolated pools of N
# (that would be 4×N processes). --chart-workers overrides, still clamped here.
# Do not reuse --workers (HTML fork pool).
MAX_CHART_WORKERS = 16
# Cache-key fields the Agg renderer does not read — drop them before pickle.
_RENDER_SKIP_KEYS = frozenset((
    "schema_version", "chart_id", "renderer_version",
))
ChartRunResult = namedtuple(
    "ChartRunResult",
    ("status", "reason", "charts_mode", "rendered", "cache_hits",
     "published", "failed", "elapsed_s"),
)
ChartRunResult.__new__.__defaults__ = (CHARTS_OFF, 0, 0, 0, 0, 0.0)

_INSTALL_HINT = (
    "Charts: skipped (matplotlib not installed; "
    "pip install -r config/requirements-charts.txt)"
)
_RENDERER_HINT = "Charts: skipped (renderer not implemented; HTML unchanged)"
_NO_BANDWIDTH_HINT = "Charts: skipped (no bandwidth data; use --apis all)"


def add_chart_arguments(parser):
    parser.add_argument(
        "--charts",
        dest="charts",
        nargs="?",
        const=CHARTS_ON,
        choices=list(CHARTS_MODES),
        default=CHARTS_ON,
        help="after HTML: off, auto, or on (default: on)",
        required=False,
    )
    parser.add_argument(
        "--no-charts",
        dest="charts",
        action="store_const",
        const=CHARTS_OFF,
        help="skip chart generation",
        required=False,
    )
    parser.add_argument(
        "--charts-limit",
        dest="charts_limit",
        type=int,
        default=0,
        metavar="N",
        help="chart at most N relays (0 = no limit)",
        required=False,
    )
    parser.add_argument(
        "--fingerprint",
        dest="chart_fingerprints",
        action="append",
        default=None,
        metavar="FP",
        help="only chart this fingerprint (repeatable)",
        required=False,
    )
    parser.add_argument(
        "--chart-workers",
        dest="chart_workers",
        type=int,
        default=0,
        help=(
            "chart process-pool size (0 = min(CPU, {cap}); cap {cap}; "
            "split across 1M/6M/1Y/5Y period runners)"
        ).format(cap=MAX_CHART_WORKERS),
        required=False,
    )


def resolve_charts_mode(args):
    mode = getattr(args, "charts", CHARTS_OFF) or CHARTS_OFF
    if mode not in CHARTS_MODES:
        return CHARTS_OFF
    return mode


def default_chart_workers(override=0):
    try:
        override = int(override or 0)
    except (TypeError, ValueError):
        override = 0
    auto = max(1, min(MAX_CHART_WORKERS, os.cpu_count() or 1))
    if override > 0:
        return max(1, min(MAX_CHART_WORKERS, override))
    return auto


def job_period(job):
    """Date-range suffix for a queued spawn job (``1m`` / ``6m`` / ``1y`` / ``5y``)."""
    period = job.get("period") if job else None
    if period:
        return period
    chart_id = (job or {}).get("chart_id") or ""
    prefix = "relay_bandwidth_"
    if chart_id.startswith(prefix) and chart_id[len(prefix):]:
        return chart_id[len(prefix):]
    return ((job or {}).get("render") or {}).get("period") or "1m"


def partition_jobs_by_period(jobs):
    """Group jobs so each date range can run in its own spawn pool."""
    buckets = OrderedDict((suffix, []) for suffix in PERIOD_SPEC_BY_SUFFIX)
    extra = OrderedDict()
    for job in jobs or ():
        period = job_period(job)
        if period in buckets:
            buckets[period].append(job)
        else:
            extra.setdefault(period, []).append(job)
    groups = [(period, group) for period, group in buckets.items() if group]
    groups.extend(extra.items())
    return groups


def allocate_period_workers(total_workers, n_groups):
    """Split one process budget across period pools. ``None`` = one shared pool.

    Never returns 4×N. Remainder goes to earlier periods (1M is heaviest).
    """
    try:
        total_workers = int(total_workers)
        n_groups = int(n_groups)
    except (TypeError, ValueError):
        return None
    if total_workers < 1 or n_groups < 1:
        return None
    if total_workers < n_groups:
        return None
    base = total_workers // n_groups
    rem = total_workers % n_groups
    return [base + (1 if i < rem else 0) for i in range(n_groups)]


def chart_imap_chunksize(n_jobs, n_proc):
    """Batch spawn IPC. Cap 32 so a period pool stays busy."""
    try:
        n_jobs = int(n_jobs)
        n_proc = int(n_proc)
    except (TypeError, ValueError):
        return 1
    if n_jobs <= 1:
        return 1
    n_proc = max(1, n_proc)
    raw = n_jobs // (n_proc * 4)
    return max(1, min(32, raw if raw else 1))


def matplotlib_is_available():
    return importlib.util.find_spec("matplotlib") is not None


def _import_renderer_module(spec):
    try:
        return importlib.import_module(spec.renderer_module)
    except ImportError:
        alt = spec.renderer_module
        if alt.startswith("allium."):
            return importlib.import_module(alt[len("allium."):])
        raise


def renderer_is_ready(spec):
    try:
        module = _import_renderer_module(spec)
    except ImportError:
        return False
    return callable(getattr(module, spec.renderer_name, None))


def _emit(message, progress_logger=None):
    print(message)
    if progress_logger is not None:
        log = getattr(progress_logger, "log_without_increment", None)
        if callable(log):
            log(message)


def _details_relays(relay_set):
    if not relay_set:
        return []
    return list((getattr(relay_set, "json", None) or {}).get("relays") or [])


def _bandwidth_data(relay_set):
    return getattr(relay_set, "bandwidth_data", None) if relay_set else None


def _relays_published(relay_set, bandwidth_data):
    if bandwidth_data and bandwidth_data.get("relays_published"):
        return bandwidth_data.get("relays_published")
    json_doc = getattr(relay_set, "json", None) or {}
    return json_doc.get("relays_published") or ""


def _output_dir(relay_set, args):
    if args is not None and getattr(args, "output_dir", None):
        return args.output_dir
    if relay_set is not None:
        return getattr(relay_set, "output_dir", "") or ""
    return ""


def _selection(relay_set, args):
    """Details, 1M series, and the --charts-limit / --fingerprint slice."""
    bandwidth_data = _bandwidth_data(relay_set)
    details = _details_relays(relay_set)
    bw_map = build_bandwidth_map(bandwidth_data)
    series = series_by_fp(details, bw_map)
    selected = chartable_fingerprints(
        details,
        bw_map,
        fingerprints=getattr(args, "chart_fingerprints", None) if args else None,
        limit=getattr(args, "charts_limit", 0) if args else 0,
        series=series,
    )
    return _Selection(details, bw_map, series, selected, bandwidth_data)


def _skip_reason(args, relay_set):
    """Why the HTML gate and the pass both stay off. None means run."""
    mode = resolve_charts_mode(args)
    if mode == CHARTS_OFF:
        return "off"
    if not matplotlib_is_available():
        return "matplotlib_missing" if mode == CHARTS_ON else "auto_unavailable"
    if not any(renderer_is_ready(spec) for spec in RELAY_BANDWIDTH_PERIODS):
        return "renderer_missing"
    if not _bandwidth_data(relay_set):
        return "no_bandwidth_data"
    return None


def _init_chart_worker():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot  # noqa: F401


def _queue_or_publish(jobs, output_dir, spec, fp, payload, extra_render=None):
    """Cache-hit → publish; miss → one slim spawn job. Returns ``hit`` or ``job``."""
    key = cache_key(payload)
    if cache_hit(output_dir, spec, fp, key):
        if publish_png(
            cached_png_path(output_dir, spec, fp),
            published_png_path(output_dir, spec, fp),
        ):
            return "hit"
        return None
    render = {
        key_name: value
        for key_name, value in payload.items()
        if key_name not in _RENDER_SKIP_KEYS
    }
    if extra_render:
        render.update(extra_render)
    period = render.get("period") or payload.get("period") or "1m"
    jobs.append({
        "output_dir": output_dir,
        "fingerprint": fp,
        "key": key,
        "chart_id": spec.chart_id,
        "period": period,
        "render": render,
    })
    return "job"


def _render_chart_job(job):
    spec = get_chart(job.get("chart_id")) or RELAY_BANDWIDTH_1M
    output_dir = job["output_dir"]
    fingerprint = job["fingerprint"]
    if not is_relay_fingerprint(fingerprint):
        return {
            "ok": False, "fingerprint": fingerprint, "error": "invalid fingerprint",
        }
    key = job["key"]
    cache_png = cached_png_path(output_dir, spec, fingerprint)
    try:
        module = _import_renderer_module(spec)
        getattr(module, spec.renderer_name)(job["render"], cache_png)
        write_sidecar(
            sidecar_path(output_dir, spec, fingerprint),
            key, spec.chart_id, fingerprint,
        )
        publish_png(cache_png, published_png_path(output_dir, spec, fingerprint))
        return {"ok": True, "fingerprint": fingerprint, "error": None}
    except Exception as exc:  # noqa: BLE001 — one bad relay must not kill the pool
        return {"ok": False, "fingerprint": fingerprint, "error": str(exc)}


def _drain_pool(pool, jobs, n_proc):
    """imap_unordered one pool. Returns ``(rows, error_or_None, unstarted)``."""
    results = []
    try:
        for row in pool.imap_unordered(
            _render_chart_job, jobs,
            chunksize=chart_imap_chunksize(len(jobs), n_proc),
        ):
            results.append(row)
    except Exception as exc:  # noqa: BLE001 — pool death must not fail HTML
        return results, exc, len(jobs) - len(results)
    return results, None, 0


def _run_spawn_pool(jobs, n_proc):
    """One spawn+Agg pool on the calling thread."""
    import multiprocessing

    if not jobs:
        return [], None, 0
    ctx = multiprocessing.get_context("spawn")
    n_proc = max(1, min(int(n_proc), len(jobs)))
    with ctx.Pool(processes=n_proc, initializer=_init_chart_worker) as pool:
        return _drain_pool(pool, jobs, n_proc)


def _run_period_pools(groups, alloc, progress_logger=None):
    """One spawn pool per date range. Pools start on this thread (not daemons)."""
    import multiprocessing
    import threading
    from contextlib import ExitStack

    ctx = multiprocessing.get_context("spawn")
    collected = []
    leftover = [0]
    errors = []
    lock = threading.Lock()

    def worker(period, group_jobs, n_proc, pool):
        rows, exc, fail_n = _drain_pool(pool, group_jobs, n_proc)
        with lock:
            collected.extend(rows)
            leftover[0] += fail_n
            if exc is not None:
                errors.append((period, exc))

    with ExitStack() as stack:
        opened = []
        for (period, group_jobs), n_proc in zip(groups, alloc):
            n_proc = max(1, min(int(n_proc), len(group_jobs)))
            pool = stack.enter_context(
                ctx.Pool(processes=n_proc, initializer=_init_chart_worker),
            )
            opened.append((period, group_jobs, n_proc, pool))
        threads = []
        for period, group_jobs, n_proc, pool in opened:
            thread = threading.Thread(
                target=worker,
                args=(period, group_jobs, n_proc, pool),
                name="chart-%s" % period,
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

    for period, exc in errors:
        _emit("Charts: {} pool error ({})".format(period, exc), progress_logger)
    return collected, leftover[0]


def _run_chart_jobs(jobs, workers, progress_logger=None):
    """Period-parallel spawn pools sharing one process budget, or one pool."""
    groups = partition_jobs_by_period(jobs)
    alloc = allocate_period_workers(workers, len(groups))
    if alloc is None or len(groups) <= 1:
        _emit(
            "Charts: {} jobs, 1 pool, {} workers".format(len(jobs), workers),
            progress_logger,
        )
        results, exc, leftover = _run_spawn_pool(jobs, workers)
        if exc:
            _emit("Charts: pool error ({})".format(exc), progress_logger)
        return results, leftover

    _emit(
        "Charts: {} jobs, {} period runners ({}), {} workers".format(
            len(jobs),
            len(groups),
            "/".join(period for period, _group in groups),
            sum(alloc),
        ),
        progress_logger,
    )
    return _run_period_pools(groups, alloc, progress_logger)


def run_chart_pass(relay_set, args, progress_logger=None):
    from .bands import bands_for_flags, bands_frozen_from, load_role_bands

    started = time.monotonic()
    output_dir = _output_dir(relay_set, args)
    sel = getattr(relay_set, "_chart_selection", None) if relay_set else None
    if sel is None:
        sel = _selection(relay_set, args)
    selected = frozenset(sel.selected)
    published = _relays_published(relay_set, sel.bandwidth_data)
    catalog = load_role_bands()
    frozen = bands_frozen_from(catalog)
    # Full series population — not the --charts-limit slice — for overlay n≥2.
    overlays = precompute_overlays(sel.details, sel.bw_map, series=sel.series)
    workers = default_chart_workers(getattr(args, "chart_workers", 0) if args else 0)

    jobs = []
    hits = 0
    published_n = 0
    for relay in sel.details:
        fp = relay.get("fingerprint")
        if fp not in selected:
            continue
        parsed = sel.series.get(fp)
        if not parsed:
            continue
        family, role_ov = overlays_for_relay(relay, parsed["write_1m"], overlays)
        bands = bands_for_flags(relay.get("flags"), catalog)
        periods = parsed.get("periods") or {}
        for suffix, spec in PERIOD_SPEC_BY_SUFFIX.items():
            block = periods.get(suffix)
            if not block:
                continue
            is_hero_1m = suffix == "1m"
            payload = build_relay_bandwidth_1m_payload(
                relay,
                bandwidth_relay=sel.bw_map.get(fp),
                relays_published=published,
                family_overlay=family if is_hero_1m else None,
                role_overlay=role_ov if is_hero_1m else None,
                bands=bands,
                bands_frozen_from=frozen,
                renderer_version=spec.renderer_version,
                period=suffix,
                write=block["write"],
                read=block["read"],
            )
            queued = _queue_or_publish(
                jobs, output_dir, spec, fp, payload,
                extra_render={"relays_published": published, "period": suffix},
            )
            if queued == "hit":
                hits += 1
                published_n += 1

    rendered = 0
    failed = 0
    if jobs:
        results, leftover = _run_chart_jobs(jobs, workers, progress_logger)
        failed += leftover
        for row in results:
            if row and row.get("ok"):
                rendered += 1
                published_n += 1
            else:
                failed += 1

    elapsed = time.monotonic() - started
    total = rendered + hits
    msg = "Charts: {}/{} rendered, {} cache hits ({:.1f}s)".format(
        rendered, total if total else len(jobs), hits, elapsed,
    )
    if failed:
        msg += ", {} failed".format(failed)
    _emit(msg, progress_logger)
    reason = "rendered" if rendered or hits else "nothing_to_draw"
    if failed and not (rendered or hits):
        reason = "all_failed"
    elif failed:
        reason = "partial"
    return ChartRunResult(
        status="ok" if not failed else ("error" if reason == "all_failed" else "ok"),
        reason=reason,
        charts_mode=resolve_charts_mode(args) if args else CHARTS_OFF,
        rendered=rendered,
        cache_hits=hits,
        published=published_n,
        failed=failed,
        elapsed_s=elapsed,
    )


def maybe_run_charts(relay_set, args, progress_logger=None):
    mode = resolve_charts_mode(args)
    reason = _skip_reason(args, relay_set)
    if reason:
        if reason == "matplotlib_missing" and mode == CHARTS_ON:
            _emit(_INSTALL_HINT, progress_logger)
        elif reason == "renderer_missing" and mode == CHARTS_ON:
            _emit(_RENDERER_HINT, progress_logger)
        elif reason == "no_bandwidth_data":
            _emit(_NO_BANDWIDTH_HINT, progress_logger)
        return ChartRunResult(status="skipped", reason=reason, charts_mode=mode)

    try:
        return run_chart_pass(relay_set, args, progress_logger)
    except Exception as exc:  # noqa: BLE001 — HTML already succeeded
        _emit(
            "Charts: failed ({}); HTML unchanged".format(exc),
            progress_logger,
        )
        return ChartRunResult(
            status="error", reason="pass_failed", charts_mode=mode,
        )
