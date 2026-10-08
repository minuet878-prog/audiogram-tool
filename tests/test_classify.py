"""Scenarios 1-10: PTA, degree and type of hearing loss."""

import pytest

from audiogram.classify import degree, hearing_type, pta


def ear(v500, v1000, v2000, v4000):
    return {500: v500, 1000: v1000, 2000: v2000, 4000: v4000}


# Scenario 1, 2, 4
@pytest.mark.parametrize(
    "thresholds, expected_pta, expected_degree",
    [
        (ear(10, 10, 15, 15), 12.5, "正常"),
        (ear(40, 45, 50, 55), 47.5, "中度"),
        (ear(95, 95, 95, 95), 95, "極重度"),
    ],
)
def test_pta_and_degree(thresholds, expected_pta, expected_degree):
    assert pta(thresholds) == expected_pta
    assert degree(pta(thresholds)) == expected_degree


def test_pta_ignores_other_frequencies():
    thresholds = ear(10, 10, 15, 15) | {250: 80, 8000: 90}
    assert pta(thresholds) == 12.5


# Scenario 3 (and 5b, 5c): every boundary, exactly on it and 1.25 above
@pytest.mark.parametrize(
    "value, expected",
    [
        (25, "正常"),
        (26.25, "輕度"),
        (40, "輕度"),
        (41.25, "中度"),
        (55, "中度"),
        (56.25, "中重度"),
        (70, "中重度"),
        (71.25, "重度"),
        (90, "重度"),
        (91.25, "極重度"),
    ],
)
def test_degree_boundaries(value, expected):
    assert degree(value) == expected


# Scenario 5a, 5b: normal air conduction is "normal" whatever bone conduction says
@pytest.mark.parametrize("ac", [12.5, 25])
@pytest.mark.parametrize("bc", [0, 10, 25])
def test_type_normal_when_air_conduction_normal(ac, bc):
    assert hearing_type(ac, bc) == "正常"


@pytest.mark.parametrize(
    "ac, bc, expected",
    [
        (26.25, 25, "感音神經性"),  # 5c: just past normal, gap 1.25
        (45, 40, "感音神經性"),  # 6: gap 5
        (45, 10, "傳導性"),  # 7: gap 35, bone normal
        (70, 45, "混合性"),  # 8: gap 25, bone abnormal
        (45, 30, "混合性"),  # 9: gap exactly 15 counts
        (45, 31.25, "感音神經性"),  # 9: gap 13.75 does not
        (45, 25, "傳導性"),  # 10: bone exactly 25 is normal
        (45, 26.25, "混合性"),  # 10: bone 26.25 is not
    ],
)
def test_type(ac, bc, expected):
    assert hearing_type(ac, bc) == expected


# Scenario 11, 12 at the calculation level
def test_pta_is_none_when_a_frequency_is_missing():
    assert pta({500: 10, 1000: 10, 2000: 15}) is None


def test_type_unknown_without_bone_conduction():
    assert hearing_type(45, None) is None
