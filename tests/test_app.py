"""Scenarios 11-18: form handling, messages and the chart."""

import re

import pytest

from app import app
from audiogram import chart


@pytest.fixture
def client():
    return app.test_client()


def fields(ear, conduction, values):
    """fields("right", "ac", {500: 10}) -> {"right_ac_500": "10"}"""
    return {f"{ear}_{conduction}_{freq}": str(v) for freq, v in values.items()}


def four(a, b, c, d):
    return {500: a, 1000: b, 2000: c, 4000: d}


def section(html, ear):
    """The result block of one ear, or None if it was not rendered."""
    match = re.search(rf'<section id="result-{ear}">(.*?)</section>', html, re.S)
    return match.group(1) if match else None


def post(client, *field_groups):
    data = {}
    for group in field_groups:
        data.update(group)
    return client.post("/", data=data).get_data(as_text=True)


def test_empty_page_shows_form_without_results(client):
    html = client.get("/").get_data(as_text=True)
    assert 'name="right_ac_500"' in html
    assert 'name="left_bc_4000"' in html
    assert 'name="left_bc_250"' not in html  # bone conduction is 500-4000 only
    assert section(html, "right") is None
    assert "<svg" not in html


# Scenario 1 and 7 end to end
def test_result_shows_pta_degree_and_type(client):
    html = post(
        client,
        fields("right", "ac", four(40, 45, 50, 45)),
        fields("right", "bc", four(10, 10, 10, 10)),
    )
    right = section(html, "right")
    assert "45 dB HL" in right
    assert "中度" in right
    assert "傳導性" in right


# Scenario 11
def test_missing_air_conduction_frequency(client):
    html = post(
        client,
        fields("right", "ac", {500: 40, 1000: 45, 2000: 50}),
        fields("left", "ac", four(10, 10, 15, 15)),
    )
    right = section(html, "right")
    assert "氣導資料不足，無法計算" in right
    assert "中度" not in right and "正常" not in right
    assert "12.5" in section(html, "left")
    assert "正常" in section(html, "left")


# Scenario 12
def test_missing_bone_conduction(client):
    html = post(
        client,
        fields("right", "ac", four(40, 45, 50, 55)),
        fields("right", "bc", {500: 10, 1000: 10}),
    )
    right = section(html, "right")
    assert "中度" in right
    assert "缺骨導資料，無法判斷" in right


def test_normal_air_conduction_needs_no_bone_conduction(client):
    html = post(client, fields("left", "ac", four(10, 10, 15, 15)))
    assert "缺骨導資料" not in section(html, "left")


# Scenario 13
def test_blank_250_and_8000_do_not_matter(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    assert "12.5" in section(html, "right")
    assert html.count('class="mark ac right"') == 4


def test_250_and_8000_are_drawn_but_not_averaged(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15) | {250: 80, 8000: 90}))
    assert "12.5 dB HL" in section(html, "right")
    assert html.count('class="mark ac right"') == 6


def test_pta_is_not_rounded(client):
    html = post(client, fields("left", "ac", four(45, 45, 45, 50)))
    assert "46.25 dB HL" in section(html, "left")


# Scenario 14
def test_untouched_ear_is_left_out(client):
    html = post(client, fields("left", "ac", four(10, 10, 15, 15)))
    assert section(html, "right") is None
    assert section(html, "left") is not None
    assert 'class="error"' not in html


# Scenario 15
@pytest.mark.parametrize("bad", ["42", "-15", "125", "abc", "12.5", "1_0", "１０"])
def test_invalid_value_is_reported_and_nothing_is_calculated(client, bad):
    html = post(
        client,
        fields("right", "ac", four(40, 45, 50, 55)),
        {"left_bc_1000": bad},
    )
    assert "左耳骨導 1000 Hz" in html
    assert section(html, "right") is None
    assert "<svg" not in html
    assert 'name="right_ac_500" value="40"' in html
    assert f'name="left_bc_1000" value="{bad}"' in html


def test_every_invalid_field_is_reported(client):
    html = post(client, {"right_ac_500": "42", "left_bc_2000": "abc"})
    assert "右耳氣導 500 Hz" in html
    assert "左耳骨導 2000 Hz" in html


def test_surrounding_spaces_are_ignored(client):
    html = post(client, fields("right", "ac", four(" 10 ", "10", "15", "15 ")))
    assert "12.5 dB HL" in section(html, "right")


def test_hint_uses_a_minus_sign_that_can_be_typed(client):
    assert "\u2212" not in client.get("/").get_data(as_text=True)


def test_limits_are_accepted(client):
    html = post(client, fields("right", "ac", four(-10, 120, 0, 5)))
    assert 'class="error"' not in html


# Scenario 16
def test_chart_axes():
    freqs = [250, 500, 1000, 2000, 4000, 8000]
    xs = [chart.x(f) for f in freqs]
    assert xs == sorted(xs)
    steps = {round(b - a, 6) for a, b in zip(xs, xs[1:])}
    assert len(steps) == 1  # octaves are evenly spaced
    assert chart.y(-10) < chart.y(0) < chart.y(120)  # dB grows downwards


def test_chart_is_drawn_with_axis_labels(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    assert "<svg" in html
    for label in ("250", "8000", "-10", "120"):
        assert f">{label}</text>" in html


# Scenario 17
def test_air_conduction_symbols_and_lines(client):
    html = post(
        client,
        fields("right", "ac", four(10, 10, 15, 15)),
        fields("left", "ac", {500: 20, 1000: 20}),
    )
    assert html.count('<circle class="mark ac right"') == 4
    assert html.count('<text class="mark ac left"') == 2
    assert html.count('<polyline class="line right"') == 1
    assert html.count('<polyline class="line left"') == 1
    assert re.search(r"\.right\s*{[^}]*#c00", html)
    assert re.search(r"\.left\s*{[^}]*#06c", html)
    # the colour classes must actually wrap each ear's marks
    right = re.search(r'<g class="right">(.*?)</g>', html, re.S).group(1)
    left = re.search(r'<g class="left">(.*?)</g>', html, re.S).group(1)
    assert "mark ac right" in right and "mark ac left" not in right
    assert "mark ac left" in left and "mark ac right" not in left


# Scenario 18
def test_bone_conduction_symbols_are_not_joined(client):
    html = post(
        client,
        fields("right", "bc", four(10, 10, 10, 10)),
        fields("left", "bc", four(10, 10, 10, 10)),
    )
    assert len(re.findall(r'<text class="mark bc right"[^>]*>&lt;</text>', html)) == 4
    assert len(re.findall(r'<text class="mark bc left"[^>]*>&gt;</text>', html)) == 4
    assert "<polyline" not in html


def test_only_air_conduction_is_joined_when_both_are_present(client):
    html = post(
        client,
        fields("right", "ac", four(40, 45, 50, 45)),
        fields("right", "bc", four(10, 10, 15, 10)),
    )
    assert html.count("<polyline") == 1
    assert html.count('class="mark bc right"') == 4
