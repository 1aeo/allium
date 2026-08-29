"""Shared chart-test builders. Not pytest fixtures — import the functions."""

import os
from types import SimpleNamespace

FP_JEANGRAE = "02B1C5DFBCBEC735435652050DE1AF0BB0B108CF"
FP_A = "A" * 40
FP_B = "B" * 40
FP_C = "C" * 40

_PUBLISHED = "2026-08-15 06:00:00"
_FIRST = "2026-07-16 12:00:00"


def make_relay(fp=FP_JEANGRAE, nickname="jeangrae", family=None, **extra):
    relay = {
        "fingerprint": fp,
        "nickname": nickname,
        "contact": "url:1aeo.com proof:uri-rsa ciissversion:2",
        "contact_md5": "jg",
        "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir"],
        "advertised_bandwidth": 82000000,
        "last_restarted": "2025-10-01 00:00:00",
        "overload_general_timestamp": None,
        "effective_family": list(family if family is not None else [fp]),
    }
    relay.update(extra)
    return relay


def make_bw(
    fp=FP_JEANGRAE,
    write_values=None,
    read_values=None,
    factor=1000.0,
    first=_FIRST,
    last="2026-07-19 12:00:00",
    interval=86400,
    **extra
):
    extra_periods = extra.pop("extra_periods", ())
    write_values = (
        list(write_values) if write_values is not None else [100, 110, 120, 115]
    )
    read_values = (
        list(read_values) if read_values is not None else [95, 105, 112, 110]
    )
    month = {
        "first": first,
        "last": last,
        "interval": interval,
        "factor": factor,
        "values": write_values,
    }
    read_month = dict(month, values=read_values)
    bw = {
        "fingerprint": fp,
        "write_history": {"1_month": month},
        "read_history": {"1_month": read_month},
    }
    for key in extra_periods:
        bw["write_history"][key] = dict(month)
        bw["read_history"][key] = dict(read_month)
    bw.update(extra)
    return bw


def make_job(**overrides):
    values_w = [80, 90, 85, 88, 92, 400, 350, 90, 91, 89]
    values_r = [76, 86, 82, 84, 88, 80, 80, 86, 87, 85]
    job = {
        "nickname": "jeangrae",
        "operator": "1aeo.com",
        "fingerprint": FP_JEANGRAE,
        "advertised_bandwidth": 82000000,
        "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir"],
        "role": "Guard",
        "last_restarted": "2025-10-01 00:00:00",
        "relays_published": _PUBLISHED,
        "overload_general_timestamp": None,
        "overload_ratelimits": None,
        "overload_fd_exhausted": None,
        "write_1m": {
            "first": _FIRST,
            "last": "2026-07-25 12:00:00",
            "interval": 86400,
            "factor": 100000.0,
            "values": values_w,
        },
        "read_1m": {
            "first": _FIRST,
            "last": "2026-07-25 12:00:00",
            "interval": 86400,
            "factor": 100000.0,
            "values": values_r,
        },
        "family_overlay": None,
        "role_overlay": {"n": 10, "values": [1.04] * 10},
        "bands_frozen_from": "2026-08-15 19:00:00",
    }
    job.update(overrides)
    return job


def make_relay_set(output_dir, pairs=None, **extra):
    pairs = list(pairs or [(make_relay(), make_bw())])
    ns = SimpleNamespace(
        json={
            "relays": [pair[0] for pair in pairs],
            "relays_published": _PUBLISHED,
        },
        bandwidth_data={
            "relays": [pair[1] for pair in pairs],
            "relays_published": _PUBLISHED,
        },
        output_dir=output_dir,
        use_bits=True,
    )
    for key, value in extra.items():
        setattr(ns, key, value)
    return ns


def fake_render(job, dest):
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dest, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + b"fake")
    return dest


class _DummyPool(object):
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def imap_unordered(self, func, jobs, chunksize=1):
        return [func(job) for job in jobs]


class _DummyCtx(object):
    def Pool(self, **kwargs):
        return _DummyPool()


def stub_chart_pool(monkeypatch, render=fake_render, mpl=True):
    monkeypatch.setattr(
        "allium.lib.charts.pipeline.matplotlib_is_available",
        lambda: mpl,
    )
    if render is not None:
        monkeypatch.setattr(
            "allium.lib.charts.bandwidth.render_relay_bandwidth_1m",
            render,
        )
        monkeypatch.setattr(
            "allium.lib.charts.bandwidth.render_relay_bandwidth_spark",
            render,
        )
        monkeypatch.setattr(
            "multiprocessing.get_context",
            lambda name: _DummyCtx(),
        )


def on_args(output_dir, **extra):
    values = dict(charts="on", chart_workers=1, output_dir=output_dir)
    values.update(extra)
    return SimpleNamespace(**values)
