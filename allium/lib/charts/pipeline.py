"""Chart-pass entry point.

HTML generate stays Jinja-only. Charts run after ``generate_site()`` in
a small spawn pool. matplotlib is never imported in this module.
"""

import importlib
import importlib.util
import os
import time
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
    has_1m_graph,
    month_blocks,
    overlays_for_relay,
    precompute_overlays,
)

CHARTS_OFF = "off"
CHARTS_AUTO = "auto"
CHARTS_ON = "on"
CHARTS_MODES = (CHARTS_OFF, CHARTS_AUTO, CHARTS_ON)

# Shown when --charts on cannot run. Always printed (not --progress
# only) so an operator who asked for charts sees why PNGs are missing.
_INSTALL_HINT = (
    "Charts: skipped (matplotlib not installed; "
    "pip install -r config/requirements-charts.txt)"
)
_RENDERER_HINT = "Charts: skipped (renderer not implemented; HTML unchanged)"
_NO_BANDWIDTH_HINT = "Charts: skipped (no bandwidth data; use --apis all)"


class ChartRunResult(object):
    """Outcome of maybe_run_charts()."""

    def __init__(
        self,
        status,
        reason,
        charts_mode=CHARTS_OFF,
        rendered=0,
        cache_hits=0,
        published=0,
        elapsed_s=0.0,
    ):
        self.status = status
        self.reason = reason
        self.charts_mode = charts_mode
        self.rendered = rendered
        self.cache_hits = cache_hits
        self.published = published
        self.elapsed_s = elapsed_s

    def __repr__(self):
        return (
            "ChartRunResult(status={!r}, reason={!r}, charts_mode={!r}, "
            "rendered={!r}, cache_hits={!r})"
        ).format(
            self.status, self.reason, self.charts_mode,
            self.rendered, self.cache_hits,
        )


def add_chart_arguments(parser):
    """Register --charts / --no-charts / --chart-workers on the CLI parser.

    Default is ``auto``: run after HTML when the charts extra is
    installed, silent no-op when it is not.
    """
    parser.add_argument(
        "--charts",
        dest="charts",
        nargs="?",
        const=CHARTS_ON,
        choices=list(CHARTS_MODES),
        default=CHARTS_AUTO,
        help=(
            "generate relay-page charts after HTML "
            "(off, auto, on; default: auto). "
            "auto enables only when the charts extra is installed"
        ),
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
        "--chart-workers",
        dest="chart_workers",
        type=int,
        default=0,
        help=(
            "process-pool size for chart render "
            "(default: min(4, CPU count); 0 = auto)"
        ),
        required=False,
    )


def resolve_charts_mode(args):
    """Return off/auto/on from an argparse namespace."""
    mode = getattr(args, "charts", CHARTS_AUTO) or CHARTS_AUTO
    if mode not in CHARTS_MODES:
        return CHARTS_OFF
    return mode


def default_chart_workers(override=0):
    """Small process-pool cap. Do not reuse --workers (often 8–16)."""
    if override and int(override) > 0:
        return int(override)
    cpu = os.cpu_count() or 1
    return max(1, min(4, cpu))


def matplotlib_is_available():
    """True when the charts extra is installed. Does not import pyplot."""
    return importlib.util.find_spec("matplotlib") is not None


def _import_renderer_module(spec):
    """Import the renderer module under ``allium.lib`` or ``lib``."""
    try:
        return importlib.import_module(spec.renderer_module)
    except ImportError:
        alt = spec.renderer_module
        if alt.startswith("allium."):
            return importlib.import_module(alt[len("allium."):])
        raise


def renderer_is_ready(spec):
    """True when the spec's render function exists and is callable."""
    try:
        module = _import_renderer_module(spec)
    except ImportError:
        return False
    func = getattr(module, spec.renderer_name, None)
    return callable(func)


def _emit(message, progress_logger=None):
    print(message)
    if progress_logger is not None:
        log = getattr(progress_logger, "log_without_increment", None)
        if callable(log):
            log(message)


def _details_relays(relay_set):
    if not relay_set:
        return []
    json_doc = getattr(relay_set, "json", None) or {}
    return list(json_doc.get("relays") or [])


def _bandwidth_data(relay_set):
    if not relay_set:
        return None
    return getattr(relay_set, "bandwidth_data", None)


def _relays_published(relay_set, bandwidth_data):
    if bandwidth_data and bandwidth_data.get("relays_published"):
        return bandwidth_data.get("relays_published")
    json_doc = getattr(relay_set, "json", None) or {}
    return json_doc.get("relays_published") or ""


def _bandwidth_units(relay_set):
    if relay_set is not None and getattr(relay_set, "use_bits", False):
        return "bits"
    return "bytes"


def _output_dir(relay_set, args):
    if args is not None and getattr(args, "output_dir", None):
        return args.output_dir
    if relay_set is not None:
        return getattr(relay_set, "output_dir", "") or ""
    return ""


def charts_will_run(args, relay_set):
    """True when the post-HTML pass will actually render or publish."""
    mode = resolve_charts_mode(args)
    if mode == CHARTS_OFF:
        return False
    if not matplotlib_is_available():
        return False
    if not any(renderer_is_ready(spec) for spec in enabled_charts()):
        return False
    if not _bandwidth_data(relay_set):
        return False
    return True


def apply_chart_html_flags(relay_set, args):
    """Set ``charts_enabled`` / ``bandwidth_chart_fps`` before Jinja.

    Called before ``generate_site()`` so ``--no-charts`` and ``auto``
    without the extra omit the History ``<img>`` (no broken images).
    Does not import matplotlib.
    """
    will_run = charts_will_run(args, relay_set)
    fps = frozenset()
    if will_run:
        bw_map = build_bandwidth_map(_bandwidth_data(relay_set))
        fps = frozenset(chartable_fingerprints(_details_relays(relay_set), bw_map))
    if relay_set is not None:
        relay_set.charts_enabled = will_run
        relay_set.bandwidth_chart_fps = fps
    return will_run


def _init_chart_worker():
    """Spawn initializer: Agg backend, then pyplot, once per process."""
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot  # noqa: F401


def _render_chart_job(job):
    """Spawn-worker entry. ``job`` is a slim dict. No Relays object."""
    from .bandwidth import render_relay_bandwidth_1m

    spec = RELAY_BANDWIDTH_1M
    output_dir = job["output_dir"]
    fingerprint = job["fingerprint"]
    key = job["key"]
    cache_png = cached_png_path(output_dir, spec, fingerprint)
    try:
        render_relay_bandwidth_1m(job["render"], cache_png)
        write_sidecar(
            sidecar_path(output_dir, spec, fingerprint),
            key, spec.chart_id, fingerprint,
        )
        published = published_png_path(output_dir, spec, fingerprint)
        publish_png(cache_png, published)
        return {"ok": True, "fingerprint": fingerprint, "error": None}
    except Exception as exc:  # noqa: BLE001 — one bad relay must not kill the pool
        return {"ok": False, "fingerprint": fingerprint, "error": str(exc)}


def _build_render_job(relay, payload, bands, family, role):
    return {
        "nickname": payload["nickname"],
        "operator": payload["operator"],
        "fingerprint": payload["fingerprint"],
        "advertised_bandwidth": payload["advertised_bandwidth"],
        "flags": payload["flags"],
        "role": payload["role"],
        "last_restarted": payload["last_restarted"],
        "relays_published": payload["relays_published"],
        "overload_general_timestamp": relay.get("overload_general_timestamp"),
        "overload_ratelimits": payload["overload_ratelimits"],
        "overload_fd_exhausted": payload["overload_fd_exhausted"],
        "write_1m": payload["write_1m"],
        "read_1m": payload["read_1m"],
        "family_overlay": family,
        "role_overlay": role,
        "bands": bands,
        "bands_frozen_from": payload["bands_frozen_from"],
        "bandwidth_units": payload["bandwidth_units"],
    }


def run_chart_pass(relay_set, args, progress_logger=None):
    """Cache-aware spawn pass. Parent never imports matplotlib."""
    from .bands import bands_for_flags, bands_frozen_from, load_role_bands
    from .registry import RELAY_BANDWIDTH_1M as spec

    started = time.monotonic()
    output_dir = _output_dir(relay_set, args)
    bandwidth_data = _bandwidth_data(relay_set)
    bw_map = build_bandwidth_map(bandwidth_data)
    details = _details_relays(relay_set)
    published = _relays_published(relay_set, bandwidth_data)
    units = _bandwidth_units(relay_set)
    catalog = load_role_bands()
    frozen = bands_frozen_from(catalog)
    overlays = precompute_overlays(details, bw_map)
    workers = default_chart_workers(getattr(args, "chart_workers", 0) if args else 0)

    jobs = []
    hits = 0
    published_n = 0
    for relay in details:
        fp = relay.get("fingerprint")
        if not fp or not str(fp).isalnum():
            continue
        bw_relay = bw_map.get(fp)
        if not has_1m_graph(bw_relay):
            continue
        write_1m, read_1m = month_blocks(bw_relay)
        family, role_ov = overlays_for_relay(relay, write_1m, overlays)
        bands = bands_for_flags(relay.get("flags"), catalog)
        payload = build_relay_bandwidth_1m_payload(
            relay,
            bandwidth_relay=bw_relay,
            relays_published=published,
            bandwidth_units=units,
            family_overlay=family,
            role_overlay=role_ov,
            bands_frozen_from=frozen,
            renderer_version=spec.renderer_version,
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
        jobs.append({
            "output_dir": output_dir,
            "fingerprint": fp,
            "key": key,
            "render": _build_render_job(
                relay, payload, bands, family, role_ov,
            ),
        })

    rendered = 0
    failed = 0
    if jobs:
        import multiprocessing

        # Always spawn — never import matplotlib in the HTML parent.
        ctx = multiprocessing.get_context("spawn")
        n_proc = max(1, min(workers, len(jobs)))
        with ctx.Pool(
            processes=n_proc, initializer=_init_chart_worker,
        ) as pool:
            results = list(
                pool.imap_unordered(_render_chart_job, jobs, chunksize=1)
            )
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
    return ChartRunResult(
        status="ok",
        reason="rendered" if rendered or hits else "nothing_to_draw",
        charts_mode=resolve_charts_mode(args) if args else CHARTS_AUTO,
        rendered=rendered,
        cache_hits=hits,
        published=published_n,
        elapsed_s=elapsed,
    )


def maybe_run_charts(relay_set, args, progress_logger=None):
    """Run or skip the chart pass. Safe to call after generate_site().

    ``off`` and ``auto`` without the extra are silent so the ~5 minute
    HTML generate is unchanged. Missing extra never fails HTML.
    """
    mode = resolve_charts_mode(args)
    if mode == CHARTS_OFF:
        return ChartRunResult(status="skipped", reason="off", charts_mode=mode)

    extra_ok = matplotlib_is_available()
    if not extra_ok:
        if mode == CHARTS_ON:
            _emit(_INSTALL_HINT, progress_logger)
            return ChartRunResult(
                status="skipped",
                reason="matplotlib_missing",
                charts_mode=mode,
            )
        return ChartRunResult(
            status="skipped",
            reason="auto_unavailable",
            charts_mode=mode,
        )

    specs = [spec for spec in enabled_charts() if renderer_is_ready(spec)]
    if not specs:
        if mode == CHARTS_ON:
            _emit(_RENDERER_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="renderer_missing",
            charts_mode=mode,
        )

    if not _bandwidth_data(relay_set):
        _emit(_NO_BANDWIDTH_HINT, progress_logger)
        return ChartRunResult(
            status="skipped",
            reason="no_bandwidth_data",
            charts_mode=mode,
        )

    return run_chart_pass(relay_set, args, progress_logger)
