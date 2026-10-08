"""Audiogram geometry: where a (frequency, dB) point sits in the SVG."""

FREQUENCIES = (250, 500, 1000, 2000, 4000, 8000)
DB_MIN, DB_MAX = -10, 120

WIDTH, HEIGHT = 480, 430
LEFT, TOP = 50, 40
PLOT_WIDTH, PLOT_HEIGHT = 400, 360


def x(frequency):
    """Octaves are evenly spaced, as on a clinical audiogram."""
    return LEFT + FREQUENCIES.index(frequency) * PLOT_WIDTH / (len(FREQUENCIES) - 1)


def y(db):
    """dB HL increases downwards."""
    return TOP + (db - DB_MIN) * PLOT_HEIGHT / (DB_MAX - DB_MIN)


def points(thresholds):
    """[(x, y), ...] ordered by frequency."""
    return [(x(f), y(db)) for f, db in sorted(thresholds.items())]
