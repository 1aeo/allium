"""Chart-pass entry point. HTML stays Jinja-only; matplotlib stays in spawn."""

import importlib
import importlib.util
import os
import time
from collections import namedtuple

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
from .registry import RELAY_BANDWIDTH_1M, enabled_charts
from .series import (
    build_bandwidth_map,
    chartable_fingerprints,
    is_relay_fingerprint,
    overlays_for_relay,
    precompute_overlays,
    series_by_fp,
)

_Selection = namedtuple(
    "_Selection", "details bw_map series selected bandwidth_data"
)

CHARTS_OFF = "off"
CHARTS_AUTO = "auto"
CHARTS_ON = "on"
CHARTS_MODES = (CHARTS_OFF, CHARTS_AUTO, CHARTS_ON)
MAX_CHART_WORKERS = 8

_INSTALL_HINT = (
    "Charts: skipped (matplotlib not installed; "
    "pip install -r config/requirements-charts.txt)"
)
_RENDERER_HINT = "Charts: skipped (renderer not implemented; HTML unchanged)"
_NO_BANDWIDTH_HINT = "Charts: skipped (no bandwidth data; use --apis all)"


class ChartRunResult(object):
    def __init__(
        self,
        status,
        reason,
        charts_mode=CHARTS_OFF,
        rendered=0,
        cache_hits=0,
        published=0,
        failed=0,
        elapsed_s=0.0,
    ):
        self.status = status
        self.reason = reason
        self.charts_mode = charts_mode
        self.rendered = rendered
        self.cache_hits = cache_hits
        self.published = published
        self.failed = failed
        self.elapsed_s = elapsed_s

    def __repr__(self):
        return (
            "ChartRunResult(status={!r}, reason={!r}, charts_mode={!r}, "
            "rendered={!r}, cache_hits={!r}, failed={!r})"
        ).format(
            self.status, self.reason, self.charts_mode,
            self.rendered, self.cache_hits, self.failed,
        )


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
        help="chart process-pool size (0 = min(4, CPU); cap {})".format(
            MAX_CHART_WORKERS
        ),
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
    auto = max(1, min(4, os.cpu_count() or 1))
    if override > 0:
        return max(1, min(MAX_CHART_WORKERS, override))
    return auto


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
    if not any(renderer_is_ready(spec) for spec in enabled_charts()):
        return "renderer_missing"
    if not _bandwidth_data(relay_set):
        return "no_bandwidth_data"
    return None


def charts_will_run(args, relay_set):
    return not _skip_reason(args, relay_set)


def apply_chart_html_flags(relay_set, args):
    """Set ``charts_enabled`` / ``bandwidth_chart_fps`` before Jinja."""
    will_run = not _skip_reason(args, relay_set)
    sel = _selection(relay_set, args) if will_run else None
    fps = frozenset(sel.selected) if sel else frozenset()
    if relay_set is not None:
        relay_set.charts_enabled = will_run
        relay_set.bandwidth_chart_fps = fps
        relay_set._chart_selection = sel
    return will_run


def _init_chart_worker():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot  # noqa: F401


def _render_chart_job(job):
    from .bandwidth import render_relay_bandwidth_1m

    spec = RELAY_BANDWIDTH_1M
    output_dir = job["output_dir"]
    fingerprint = job["fingerprint"]
    if not is_relay_fingerprint(fingerprint):
        return {
            "ok": False, "fingerprint": fingerprint, "error": "invalid fingerprint",
        }
    key = job["key"]
    cache_png = cached_png_path(output_dir, spec, fingerprint)
    try:
        render_relay_bandwidth_1m(job["render"], cache_png)
        write_sidecar(
            sidecar_path(output_dir, spec, fingerprint),
            key, spec.chart_id, fingerprint,
        )
        publish_png(cache_png, published_png_path(output_dir, spec, fingerprint))
        return {"ok": True, "fingerprint": fingerprint, "error": None}
    except Exception as exc:  # noqa: BLE001 — one bad relay must not kill the pool
        return {"ok": False, "fingerprint": fingerprint, "error": str(exc)}


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
    spec = RELAY_BANDWIDTH_1M

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
        payload = build_relay_bandwidth_1m_payload(
            relay,
            bandwidth_relay=sel.bw_map.get(fp),
            relays_published=published,
            family_overlay=family,
            role_overlay=role_ov,
            bands=bands,
            bands_frozen_from=frozen,
            renderer_version=spec.renderer_version,
            write_1m=parsed["write_1m"],
            read_1m=parsed["read_1m"],
        )
        key = cache_key(payload)
        if cache_hit(output_dir, spec, fp, key):
            if publish_png(
                cached_png_path(output_dir, spec, fp),
                published_png_path(output_dir, spec, fp),
            ):
                hits += 1
                published_n += 1
            continue
        render = dict(payload)
        render["relays_published"] = published
        jobs.append({
            "output_dir": output_dir,
            "fingerprint": fp,
            "key": key,
            "render": render,
        })

    rendered = 0
    failed = 0
    if jobs:
        import multiprocessing

        ctx = multiprocessing.get_context("spawn")
        n_proc = max(1, min(workers, len(jobs)))
        results = []
        try:
            with ctx.Pool(
                processes=n_proc, initializer=_init_chart_worker,
            ) as pool:
                for row in pool.imap_unordered(
                    _render_chart_job, jobs, chunksize=1,
                ):
                    results.append(row)
        except Exception as exc:  # noqa: BLE001 — pool death must not fail HTML
            failed += len(jobs) - len(results)
            _emit("Charts: pool error ({})".format(exc), progress_logger)
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
