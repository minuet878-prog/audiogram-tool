"""Rule-based audiogram classification. No web or I/O code in here."""

PTA_FREQUENCIES = (500, 1000, 2000, 4000)
NORMAL_LIMIT = 25  # dB HL; applies to both air and bone conduction averages
AIR_BONE_GAP = 15  # dB; a gap this large or larger is significant

# Upper limit (inclusive) of each degree, checked in order.
DEGREES = (
    (NORMAL_LIMIT, "正常"),
    (40, "輕度"),
    (55, "中度"),
    (70, "中重度"),
    (90, "重度"),
)


def pta(thresholds):
    """Four-frequency average, or None if any of the four is missing."""
    values = [thresholds.get(f) for f in PTA_FREQUENCIES]
    if None in values:
        return None
    return sum(values) / len(values)


def degree(ac_pta):
    for limit, name in DEGREES:
        if ac_pta <= limit:
            return name
    return "極重度"


def hearing_type(ac_pta, bc_pta):
    """Type of loss, or None when bone conduction is needed but missing."""
    if ac_pta <= NORMAL_LIMIT:
        return "正常"
    if bc_pta is None:
        return None
    if ac_pta - bc_pta < AIR_BONE_GAP:
        return "感音神經性"
    return "傳導性" if bc_pta <= NORMAL_LIMIT else "混合性"
