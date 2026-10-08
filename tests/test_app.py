"""Scenarios 11-18: form handling, messages and the chart."""

import itertools
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
    match = re.search(rf'<section id="result-{ear}">(.*?)</section>', html, re.DOTALL)
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
    steps = {round(b - a, 6) for a, b in itertools.pairwise(xs)}
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
    right = re.search(r'<g class="right">(.*?)</g>', html, re.DOTALL).group(1)
    left = re.search(r'<g class="left">(.*?)</g>', html, re.DOTALL).group(1)
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


# ---- v2 visual polish: scenarios V1-V11 ----

def style(html):
    return re.search(r"<style>(.*?)</style>", html, re.DOTALL).group(1)


def css_number(css, selector, prop):
    """Value of a numeric property in the rule whose selector is exactly `selector`."""
    rule = re.search(rf"(?:^|}})\s*{re.escape(selector)}\s*{{([^}}]*)}}", css)
    assert rule, f"no CSS rule for {selector}"
    return float(re.search(rf"{prop}:\s*([\d.]+)", rule.group(1)).group(1))


# Scenario V1
def test_bootstrap_is_served_locally(client):
    html = client.get("/").get_data(as_text=True)
    assert '<link rel="stylesheet" href="/static/css/bootstrap.min.css">' in html
    assert not re.search(r'(?:src|href)="(?:https?:)?//', html)
    response = client.get("/static/css/bootstrap.min.css")
    assert response.status_code == 200
    assert b"Bootstrap" in response.data[:200]


# Scenario V2
def test_form_on_the_left_results_and_chart_on_the_right(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    left_col = html.index('<div class="col-lg-5">')
    right_col = html.index('<div class="col-lg-7">')
    assert left_col < html.index("<form") < right_col
    assert right_col < html.index('<section id="result-right">') < html.index("<svg")


# Scenario V3
def test_page_fits_a_phone_screen(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    # safety net only: if a table were ever too wide it would scroll in its own box,
    # not the page. That it actually fits at 390px was checked in the browser.
    assert html.count('<div class="table-responsive">') == 2
    assert re.search(r"svg\.audiogram\s*{[^}]*width:\s*100%", style(html))


# Scenario V4
def test_each_ear_gets_a_card_in_its_colour(client):
    html = post(
        client,
        fields("right", "ac", four(40, 45, 50, 45)),
        fields("left", "ac", four(10, 10, 15, 15)),
    )
    for ear in ("right", "left"):
        assert re.search(
            rf'<div class="card result-card {ear}[^"]*">\s*<section id="result-{ear}">', html
        )
    assert re.search(r"\.result-card\s*{[^}]*border-top:[^}]*currentColor", style(html))
    assert '<p class="pta">45 dB HL</p>' in section(html, "right")


# Scenario V5
@pytest.mark.parametrize(
    "thresholds, name, css_class",
    [
        (four(10, 10, 15, 15), "正常", "degree-normal"),
        (four(30, 30, 30, 30), "輕度", "degree-mild"),
        (four(50, 50, 50, 50), "中度", "degree-moderate"),
        (four(60, 60, 60, 60), "中重度", "degree-moderately-severe"),
        (four(80, 80, 80, 80), "重度", "degree-severe"),
        (four(100, 100, 100, 100), "極重度", "degree-profound"),
    ],
)
def test_degree_badge_is_coloured_by_degree(client, thresholds, name, css_class):
    html = post(client, fields("right", "ac", thresholds))
    assert f'<span class="degree {css_class}">{name}</span>' in section(html, "right")


def test_degree_colours_go_from_green_to_dark_red(client):
    css = style(client.get("/").get_data(as_text=True))
    expected = {
        "normal": "#198754",  # green
        "mild": "#0d9488",  # teal
        "moderate": "#d97706",  # amber
        "moderately-severe": "#ea580c",  # orange
        "severe": "#dc2626",  # red
        "profound": "#7f1d1d",  # dark red
    }
    for name, colour in expected.items():
        assert re.search(rf"\.degree-{name}\s*{{[^}}]*background:\s*{colour}", css), name


# Scenario V6
def test_insufficient_data_card_has_no_degree_badge(client):
    html = post(client, fields("right", "ac", {500: 40, 1000: 45}))
    right = section(html, "right")
    assert "氣導資料不足，無法計算" in right
    assert "degree-" not in right


# Scenario V7
def test_chart_has_a_legend_for_all_four_symbols(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    legend = re.search(r'<g class="legend"[^>]*>(.*)</g>\s*</svg>', html, re.DOTALL).group(1)
    assert re.search(r'<circle class="legend-mark ac right"[^>]*/>\s*<text[^>]*>右耳氣導</text>', legend)
    assert re.search(r'<text class="legend-mark ac left"[^>]*>✕</text>\s*<text[^>]*>左耳氣導</text>', legend)
    assert re.search(r'<text class="legend-mark bc right"[^>]*>&lt;</text>\s*<text[^>]*>右耳骨導</text>', legend)
    assert re.search(r'<text class="legend-mark bc left"[^>]*>&gt;</text>\s*<text[^>]*>左耳骨導</text>', legend)


def test_legend_is_not_mistaken_for_an_ears_marks(client):
    # the v1 colour test finds each ear's marks by <g class="right">; the legend must not match
    html = post(client, fields("left", "ac", four(20, 20, 20, 20)))
    assert '<g class="right">' not in html
    assert '<g class="left">' in html


def test_legend_is_inside_the_drawing_area(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    y = float(re.search(r'<g class="legend" transform="translate\([\d.]+ ([\d.]+)\)"', html).group(1))
    assert chart.y(chart.DB_MAX) < y < chart.HEIGHT


# Scenario V8
def test_normal_range_is_shaded(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    rect = re.search(r'<rect class="normal-zone"([^>]*)/>', html).group(1)
    attr = {k: float(v) for k, v in re.findall(r'(\w+)="([\d.]+)"', rect)}
    assert attr["x"] == chart.x(250)
    assert attr["x"] + attr["width"] == chart.x(8000)
    assert attr["y"] == chart.y(-10)
    assert attr["y"] + attr["height"] == chart.y(25)
    assert "正常範圍 ≤25" in html
    # drawn first, so grid lines and marks sit on top of it
    assert html.index("normal-zone") < html.index('class="grid')


# Scenario V9
def test_axis_titles_and_bold_zero_line(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    assert ">頻率 (Hz)</text>" in html
    assert ">聽閾 (dB HL)</text>" in html
    zero = re.findall(r'<line class="grid-major"[^>]*y1="([\d.]+)"', html)
    assert [float(v) for v in zero] == [chart.y(0)]
    css = style(html)
    assert css_number(css, ".grid-major", "stroke-width") > css_number(css, ".grid", "stroke-width")


# Scenario V10
def test_bone_conduction_symbols_are_bigger_and_bolder_than_v1(client):
    css = style(client.get("/").get_data(as_text=True))
    assert css_number(css, "text.mark.bc", "font-size") > 20  # v1: 20px
    assert css_number(css, "text.mark.bc", "font-weight") > 700  # v1: 700
    assert css_number(css, "text.mark.bc", "stroke-width") > 0  # v1: no outline


# Scenario V11
def test_errors_are_in_an_alert_and_bad_fields_are_marked(client):
    html = post(client, {"right_ac_500": "40", "left_bc_1000": "42", "right_bc_2000": "abc"})
    assert re.search(r'<div class="alert alert-danger" role="alert">\s*<ul class="error">', html)
    invalid = re.findall(r'<input class="[^"]*is-invalid[^"]*" name="(\w+)"', html)
    assert sorted(invalid) == ["left_bc_1000", "right_bc_2000"]
    assert 'class="form-control form-control-sm" name="right_ac_500" value="40"' in html


def test_no_field_is_marked_without_errors(client):
    html = post(client, fields("right", "ac", four(10, 10, 15, 15)))
    assert not re.search(r'<input class="[^"]*is-invalid', html)
    assert "alert-danger" not in html


def test_input_table_fits_a_phone_without_sideways_scrolling(client):
    css = style(client.get("/").get_data(as_text=True))
    phone = re.search(r"@media \(max-width: 575\.98px\)\s*{(.*?)}\s*}", css, re.DOTALL).group(1) + "}"
    assert css_number(phone, ".thresholds input", "width") < css_number(css, ".thresholds input", "width")
    assert re.search(r"\.thresholds th\s*{[^}]*white-space:\s*nowrap", phone)


def test_invalid_field_has_no_warning_icon_covering_the_number(client):
    # must be at least as specific as Bootstrap's .form-control.is-invalid to win
    css = style(client.get("/").get_data(as_text=True))
    rule = re.search(r"\.thresholds \.form-control\.is-invalid\s*{([^}]*)}", css).group(1)
    assert re.search(r"background-image:\s*none", rule)
