"""Small shared timelines and geometry for SVG and Pillow animations."""

import math


SPEED_SETTINGS = {
    "slow": {"reveal": 9.0, "loop": 9.0},
    "normal": {"reveal": 5.5, "loop": 5.5},
    "fast": {"reveal": 2.8, "loop": 2.8},
}
REVEALS = {
    "row-reveal", "column-reveal", "diagonal-reveal", "aperture-reveal",
    "circular-reveal", "fade", "typewriter", "dissolve",
}
VALID_ANIMATIONS = REVEALS | {
    "instant", "twinkle", "sparkle-wave", "flag-wave", "breathing",
}
DISSOLVE_GROUPS = 32
BREATHING_VALUES = tuple(1 - .14 * math.sin(math.pi * i / 16) ** 2 for i in range(17))


def clamp(value):
    return max(0.0, min(1.0, value))


def repeats(animation, loop):
    return animation != "instant" and (animation == "flag-wave" or loop == "yes")


def duration(animation, speed):
    value = SPEED_SETTINGS[speed]["loop"]
    return max(4.0, value) if animation == "flag-wave" else value


def reveal_progress(progress, repeat=False):
    p = clamp(progress)
    if not repeat:
        return p
    if p < .65:
        return p / .65
    if p < .80:
        return 1.0
    return (1.0 - p) / .20


def reveal_times(start=0.0, end=1.0, repeat=False):
    if repeat:
        return sorted({0.0, .65 * start, .65 * end,
                       1 - .20 * end, 1 - .20 * start, 1.0})
    return sorted({0.0, start, end, 1.0})


def interpolate(values, progress):
    position = clamp(progress) * (len(values) - 1)
    left = min(len(values) - 2, int(position))
    return values[left] + (values[left + 1] - values[left]) * (position - left)


def twinkle_window(index, count):
    start = .70 * index / max(1, count - 1)
    return start, start + .11, start + .22


def twinkle_factor(progress, index, count):
    start, peak, end = twinkle_window(index, count)
    if progress <= start or progress >= end:
        return 1.0
    amount = (progress - start) / (peak - start) if progress < peak else (end - progress) / (end - peak)
    return 1.0 - .35 * amount


def dissolve_group(x, y):
    # Stable integer mixing; neither Python's randomized hash nor mutable RNG.
    value = ((x + 1) * 0x45D9F3B) ^ ((y + 1) * 0x119DE1F3)
    value = (value ^ (value >> 16)) * 0x45D9F3B
    return (value ^ (value >> 16)) % DISSOLVE_GROUPS


def group_visibility(progress, group, count):
    return clamp(progress * count - group)


def aperture_points(width, height, progress):
    radius = math.hypot(width / 2, height / 2) / math.cos(math.pi / 8) * progress
    return [(width / 2 + math.cos(-math.pi / 8 + i * math.pi / 4) * radius,
             height / 2 + math.sin(-math.pi / 8 + i * math.pi / 4) * radius)
            for i in range(8)]


def flag_strips(cols, cell_h, pad=20):
    count = min(20, max(8, cols // 6))
    result = []
    for i in range(count):
        x0, x1 = round(i * cols / count), round((i + 1) * cols / count)
        t = ((x0 + x1 - 1) / 2) / max(1, cols - 1)
        amplitude = min(pad - 1, cell_h * 1.25) * (max(0, (t - .16) / .84) ** 1.65)
        values = [amplitude * math.sin(math.tau * (j / 16 - t * .8)) for j in range(17)]
        result.append((x0, x1, values))
    return result


def gif_timeline(animation, speed, loop):
    if animation == "instant":
        return [1.0], [100]
    ticks = round(duration(animation, speed) * 100)
    count = max(24, min(90, math.ceil(ticks / 10)))
    repeat = repeats(animation, loop)
    positions = [i / (count if repeat else count - 1) for i in range(count)]
    # GIF stores hundredths of a second. Distribute whole ticks without drift.
    boundaries = [round(i * ticks / count) for i in range(count + 1)]
    durations = [(boundaries[i + 1] - boundaries[i]) * 10 for i in range(count)]
    return positions, durations
