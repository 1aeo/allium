"""Tests for chart identity and flag-set role."""

from allium.lib.charts.identity import (
    ROLE_EXIT,
    ROLE_EXIT_GUARD,
    ROLE_GUARD,
    ROLE_MIDDLE,
    chart_identity,
    operator_from_contact,
    peers_word,
    role_from_flags,
)


def test_operator_from_contact_uses_url_host():
    contact = (
        "jeangrae url:1aeo.com proof:uri-rsa ciissversion:2 "
        "ciisssecret:unused"
    )
    assert operator_from_contact(contact) == "1aeo.com"
    assert operator_from_contact("url:https://www.F3netze.de/foo") == "f3netze.de"
    assert operator_from_contact("url:digitalcourage.social") == "digitalcourage.social"
    for junk in ("", None, "just an email <a@b.com>", "url:none", "url:localhost", "url:notadomain"):
        assert operator_from_contact(junk) == ""


def test_chart_identity_joins_nickname_and_operator():
    assert chart_identity("jeangrae", "1aeo.com") == "jeangrae  ·  1aeo.com"
    assert chart_identity("F3Netze", "") == "F3Netze"
    assert chart_identity("", "1aeo.com") == "1aeo.com"
    assert chart_identity("1aeo.com", "1aeo.com") == "1aeo.com"


def test_role_from_flags_and_peers_word():
    assert role_from_flags(["Exit", "Guard", "Fast"]) == ROLE_EXIT_GUARD
    assert role_from_flags(["Exit", "Fast"]) == ROLE_EXIT
    assert role_from_flags(["Guard", "HSDir"]) == ROLE_GUARD
    assert role_from_flags(["Fast", "Running"]) == ROLE_MIDDLE
    assert role_from_flags([]) == ROLE_MIDDLE
    assert role_from_flags(None) == ROLE_MIDDLE
    assert peers_word(ROLE_GUARD) == "Guards"
    assert peers_word(ROLE_EXIT) == "Exits"
    assert peers_word(ROLE_EXIT_GUARD) == "Exit+Guards"
    assert peers_word(ROLE_MIDDLE) == "middle relays"
    assert peers_word({"role": "Guard"}) == "Guards"
