"""Operator / contact chart paths, slice, vanity, and missing-map skip."""

import os
import sys

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from allium.lib.charts.cache import (
    cache_hit,
    published_png_path,
    sidecar_path,
)
from allium.lib.charts.pipeline import (
    CONTACT_BANDWIDTH_1M,
    RELAY_BANDWIDTH_1M,
    _Selection,
    _render_chart_job,
    contact_period_blocks,
    maybe_run_charts,
    run_chart_pass,
)
from allium.lib.charts.series import (
    aggregate_operator_bandwidth,
    contacts_from_relay_slice,
    is_contact_hash,
    is_relay_fingerprint,
    member_fingerprints_for_contact,
)
from allium.lib.contact_sorting import adjust_vanity_paths
from allium.lib.operator_analysis import contact_member_relays
from allium.lib.relays import apply_chart_html_flags
from tests.unit.charts.conftest import (
    CONTACT_A,
    CONTACT_B,
    FP_A,
    FP_B,
    FP_JEANGRAE,
    attach_contact_groups,
    make_bw,
    make_relay,
    make_relay_set,
    on_args,
    stub_chart_pool,
)

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "allium" / "templates"


def _contact_pair(fp, hid, extra_periods=(), **relay_extra):
    return (
        make_relay(fp, contact_md5=hid, **relay_extra),
        make_bw(fp, extra_periods=extra_periods),
    )


def test_contact_hash_is_32_hex_not_40():
    assert is_contact_hash(CONTACT_A) is True
    assert is_contact_hash(CONTACT_A.upper()) is True
    assert is_contact_hash("A" * 40) is False
    assert is_contact_hash(FP_JEANGRAE) is False
    assert is_contact_hash("jg") is False
    assert is_contact_hash("") is False
    assert is_contact_hash("../" + ("a" * 30)) is False
    assert is_relay_fingerprint(CONTACT_A) is False
    assert is_relay_fingerprint(FP_JEANGRAE) is True


def test_published_paths_split_32_and_40_hex(temp_dir):
    hid = CONTACT_A
    fp = FP_JEANGRAE
    assert published_png_path(temp_dir, CONTACT_BANDWIDTH_1M, hid) == os.path.join(
        temp_dir, "contact", hid, "bandwidth-1m.png",
    )
    assert published_png_path(temp_dir, RELAY_BANDWIDTH_1M, fp) == os.path.join(
        temp_dir, "relay", fp, "bandwidth-1m.png",
    )
    for bad in (hid, "jg", "", "../etc/passwd"):
        try:
            published_png_path(temp_dir, RELAY_BANDWIDTH_1M, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("relay spec accepted %r" % (bad,))
    for bad in (fp, "jg", "", "a" * 31):
        try:
            published_png_path(temp_dir, CONTACT_BANDWIDTH_1M, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("contact spec accepted %r" % (bad,))


def test_cache_hit_rejects_wrong_id_class(temp_dir):
    assert cache_hit(temp_dir, RELAY_BANDWIDTH_1M, CONTACT_A, "k") is False
    assert cache_hit(temp_dir, CONTACT_BANDWIDTH_1M, FP_JEANGRAE, "k") is False
    try:
        sidecar_path(temp_dir, RELAY_BANDWIDTH_1M, CONTACT_A)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for 32-hex on relay spec")


def test_32_hex_publishes_to_contact_dir(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = attach_contact_groups(make_relay_set(temp_dir, [
        _contact_pair(FP_JEANGRAE, CONTACT_A),
    ]))
    args = on_args(temp_dir)
    apply_chart_html_flags(relay_set, args)
    assert CONTACT_A in relay_set.contact_chart_hashes
    result = run_chart_pass(relay_set, args)
    assert result.status == "ok"
    assert os.path.isfile(os.path.join(
        temp_dir, "contact", CONTACT_A, "bandwidth-1m.png",
    ))
    assert os.path.isfile(os.path.join(
        temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png",
    ))
    assert not os.path.isfile(os.path.join(
        temp_dir, "relay", CONTACT_A, "bandwidth-1m.png",
    ))
    assert not os.path.isfile(os.path.join(
        temp_dir, "contact", FP_JEANGRAE, "bandwidth-1m.png",
    ))


def test_fingerprint_slice_charts_one_operator(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = attach_contact_groups(make_relay_set(temp_dir, [
        _contact_pair(FP_JEANGRAE, CONTACT_A),
        _contact_pair(FP_A, CONTACT_A, nickname="sib"),
        _contact_pair(FP_B, CONTACT_B, nickname="other"),
    ]))
    args = on_args(temp_dir, chart_fingerprints=["$" + FP_A.lower()])
    apply_chart_html_flags(relay_set, args)
    assert relay_set.bandwidth_chart_fps == frozenset([FP_A])
    assert relay_set.contact_chart_hashes == frozenset([CONTACT_A])
    result = run_chart_pass(relay_set, args)
    assert result.rendered >= 1
    assert os.path.isfile(os.path.join(
        temp_dir, "contact", CONTACT_A, "bandwidth-1m.png",
    ))
    assert not os.path.isfile(os.path.join(
        temp_dir, "contact", CONTACT_B, "bandwidth-1m.png",
    ))
    assert os.path.isfile(os.path.join(temp_dir, "relay", FP_A, "bandwidth-1m.png"))
    assert not os.path.isfile(os.path.join(
        temp_dir, "relay", FP_JEANGRAE, "bandwidth-1m.png",
    ))


def test_vanity_rewrite_uses_contact_hash_src():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("contact-bandwidth-history.html")
    html = tmpl.render(
        charts_enabled=True,
        has_contact_chart=True,
        value=CONTACT_A,
        page_ctx={"path_prefix": "../../"},
        contact_hero_period="1m",
        contact_spark_periods=["6m"],
    )
    expected = "../../contact/%s/bandwidth-1m.png" % CONTACT_A
    spark = "../../contact/%s/bandwidth-6m.png" % CONTACT_A
    assert 'src="%s"' % expected in html
    assert 'src="%s"' % spark in html
    assert "relay/" not in html
    vanity = adjust_vanity_paths(html)
    assert 'src="../contact/%s/bandwidth-1m.png"' % CONTACT_A in vanity
    assert 'src="../contact/%s/bandwidth-6m.png"' % CONTACT_A in vanity
    assert "../../contact/" not in vanity


def test_missing_bandwidth_map_queues_no_contact_jobs(temp_dir, monkeypatch):
    stub_chart_pool(monkeypatch)
    relay_set = attach_contact_groups(make_relay_set(temp_dir, [
        _contact_pair(FP_JEANGRAE, CONTACT_A),
    ]))
    relay_set.bandwidth_data = None
    args = on_args(temp_dir)
    apply_chart_html_flags(relay_set, args)
    assert relay_set.charts_enabled is False
    assert relay_set.contact_chart_hashes == frozenset()
    result = maybe_run_charts(relay_set, args)
    assert result.status == "skipped"
    assert result.reason == "no_bandwidth_data"
    assert not os.path.isdir(os.path.join(temp_dir, "contact"))


def test_aggregate_sums_aligned_timestamps():
    bw_map = {
        FP_A: make_bw(
            FP_A, write_values=[10, 20, 30], read_values=[5, 6, 7], factor=2.0,
        ),
        FP_B: make_bw(
            FP_B, write_values=[1, 2, 3], read_values=[4, 5, 6], factor=2.0,
        ),
    }
    agg = aggregate_operator_bandwidth([FP_A, FP_B], bw_map, "1_month")
    assert agg is not None
    assert agg["member_n"] == 2
    assert agg["write"]["factor"] == 1.0
    assert agg["write"]["values"] == [22.0, 44.0, 66.0]
    assert agg["read"]["values"] == [18.0, 22.0, 26.0]


def test_aggregate_does_not_invent_1m_without_member_block():
    bw = make_bw(FP_A, extra_periods=("6_months",))
    bw["write_history"].pop("1_month")
    bw["read_history"].pop("1_month")
    bw_map = {FP_A: bw}
    assert aggregate_operator_bandwidth([FP_A], bw_map, "1_month") is None
    assert aggregate_operator_bandwidth([FP_A], bw_map, "6_months") is not None


def test_contact_period_blocks_skip_missing_1m():
    relay = make_relay(FP_A, contact_md5=CONTACT_A)
    bw = make_bw(FP_A, extra_periods=("6_months",))
    bw["write_history"].pop("1_month")
    bw["read_history"].pop("1_month")
    relay_set = attach_contact_groups(make_relay_set("/tmp", [(relay, bw)]))
    details = relay_set.json["relays"]
    from allium.lib.bandwidth_utils import build_bandwidth_map
    bw_map = build_bandwidth_map(relay_set.bandwidth_data)
    sel = _Selection(
        details, bw_map, {}, [FP_A], relay_set.bandwidth_data, None, {},
    )
    blocks = contact_period_blocks(relay_set, sel)
    assert CONTACT_A in blocks
    assert "1m" not in blocks[CONTACT_A]
    assert "6m" in blocks[CONTACT_A]


def test_contacts_from_relay_slice_and_sorted_indices():
    relays = [
        make_relay(FP_JEANGRAE, contact_md5=CONTACT_A),
        make_relay(FP_A, nickname="sib", contact_md5=CONTACT_A),
        make_relay(FP_B, nickname="other", contact_md5=CONTACT_B),
        make_relay("C" * 40, nickname="bad", contact_md5="jg"),
    ]
    assert contacts_from_relay_slice(relays, [FP_A, "C" * 40]) == [CONTACT_A]
    groups = {
        CONTACT_A: {"relays": [0, 1]},
        CONTACT_B: {"relays": [2]},
    }
    assert member_fingerprints_for_contact(
        CONTACT_A, relays, groups,
    ) == [FP_JEANGRAE, FP_A]
    relay_set = make_relay_set("/tmp", [
        (relays[0], make_bw(FP_JEANGRAE)),
        (relays[1], make_bw(FP_A)),
    ])
    attach_contact_groups(relay_set)
    members = contact_member_relays(relay_set, CONTACT_A)
    assert [m["fingerprint"] for m in members] == [FP_JEANGRAE, FP_A]


def test_render_job_rejects_32_hex_on_relay_spec():
    row = _render_chart_job({
        "chart_id": "relay_bandwidth_1m",
        "fingerprint": CONTACT_A,
        "output_dir": "/tmp",
        "key": "x",
        "render": {},
    })
    assert row["ok"] is False
    assert row["error"] == "invalid fingerprint"


def test_render_job_rejects_40_hex_on_contact_spec():
    row = _render_chart_job({
        "chart_id": "contact_bandwidth_1m",
        "contact_md5": FP_JEANGRAE,
        "output_dir": "/tmp",
        "key": "x",
        "render": {},
    })
    assert row["ok"] is False
    assert row["error"] == "invalid contact hash"


def test_contact_jobs_set_period(temp_dir, monkeypatch):
    seen = []

    def capture(job, dest):
        seen.append(job)
        from tests.unit.charts.conftest import fake_render
        return fake_render(job, dest)

    stub_chart_pool(monkeypatch, render=capture)
    relay_set = attach_contact_groups(make_relay_set(temp_dir, [
        _contact_pair(FP_JEANGRAE, CONTACT_A, extra_periods=("6_months",)),
    ]))
    run_chart_pass(relay_set, on_args(temp_dir))
    contact_jobs = [job for job in seen if job.get("contact_md5") == CONTACT_A]
    assert contact_jobs
    assert {job.get("period") for job in contact_jobs} <= {"1m", "6m"}
    assert all(job.get("period") for job in contact_jobs)
    assert all(job.get("scope") == "operator" for job in contact_jobs)


def test_contact_html_omits_img_when_ungated():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("contact-bandwidth-history.html")
    assert tmpl.render(charts_enabled=False, has_contact_chart=True, value=CONTACT_A) == ""
    assert tmpl.render(charts_enabled=True, has_contact_chart=False, value=CONTACT_A) == ""


def test_charts_package_and_page_writer_import_do_not_load_matplotlib():
    already = "matplotlib" in sys.modules or "matplotlib.pyplot" in sys.modules
    import allium.lib.page_writer  # noqa: F401
    import allium.lib.charts.cache  # noqa: F401
    import allium.lib.charts.pipeline  # noqa: F401
    if not already:
        assert "matplotlib" not in sys.modules
        assert "matplotlib.pyplot" not in sys.modules
