import colorsys
from html import escape


CYCLE_SECTOR_COLORS = (
    "#DD4C4F",
    "#2F7FB8",
    "#07A35A",
    "#A88400",
    "#A75E9B",
    "#4F8A87",
    "#B7677A",
    "#7A837E",
)
CYCLE_SECTOR_COLOR_BY_NAME = {
    "电力": "#DD4C4F",
    "半导体": "#2F7FB8",
    "电池": "#07A35A",
    "证券": "#A75E9B",
    "国产芯片替代": "#A88400",
    "光通信/CPO": "#4F8A87",
}


def cycle_sector_color(mainline):
    text = str(mainline or "").strip()
    if not text:
        return CYCLE_SECTOR_COLORS[0]
    if text in CYCLE_SECTOR_COLOR_BY_NAME:
        return CYCLE_SECTOR_COLOR_BY_NAME[text]
    return CYCLE_SECTOR_COLORS[sum(ord(char) for char in text) % len(CYCLE_SECTOR_COLORS)]


def cycle_sector_color_for_index(index, used_colors=None):
    used_colors = used_colors or set()
    if index < len(CYCLE_SECTOR_COLORS):
        color = CYCLE_SECTOR_COLORS[index]
        if color not in used_colors:
            return color
    attempt = 0
    while True:
        hue = ((index + attempt * 0.17) * 0.618033988749895) % 1.0
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.38, 0.58)
        color = "#{:02X}{:02X}{:02X}".format(round(red * 255), round(green * 255), round(blue * 255))
        if color not in used_colors:
            return color
        attempt += 1


def is_cycle_calendar_placeholder_mainline(mainline):
    return str(mainline or "").strip() in {"主线记录待核验", "主线待确认", "主线待累计"}


def cycle_sector_color_map_from_calendar_rows(rows):
    color_by_mainline = {}
    used_colors = set()
    day_fields = ("monday", "tuesday", "wednesday", "thursday", "friday")

    def collect(cell):
        if isinstance(cell, (list, tuple)):
            for item in cell:
                collect(item)
            return
        if not isinstance(cell, dict):
            return
        mainline = str(cell.get("mainline") or cell.get("primary_mainline") or cell.get("sector") or "-").strip()
        if not mainline or mainline == "-" or is_cycle_calendar_placeholder_mainline(mainline):
            return
        if mainline not in color_by_mainline:
            preferred_color = CYCLE_SECTOR_COLOR_BY_NAME.get(mainline)
            if preferred_color and preferred_color not in used_colors:
                color = preferred_color
            else:
                color = cycle_sector_color_for_index(len(color_by_mainline), used_colors)
            color_by_mainline[mainline] = color
            used_colors.add(color)

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for field in day_fields:
            collect(row.get(field))
    return color_by_mainline


def cycle_sector_label(mainline, color_by_mainline=None):
    text = str(mainline or "-").strip() or "-"
    color = (color_by_mainline or {}).get(text) or cycle_sector_color(text)
    sector = escape(text, quote=True)
    return f'<span class="cycle-sector-label" style="color:{color};border-color:{color}">[{sector}]</span>'
