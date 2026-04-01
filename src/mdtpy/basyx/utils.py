from __future__ import annotations

from typing import Optional
import re

from dateutil.relativedelta import relativedelta


_ISO8601_DURATION_RE = re.compile(
    r"""
    ^\s*
    (?P<sign>[+-])?
    P
    (?:
        (?:(?P<years>\d+(?:[.,]\d+)?)Y)?
        (?:(?P<months>\d+(?:[.,]\d+)?)M)?
        (?:(?P<weeks>\d+(?:[.,]\d+)?)W)?
        (?:(?P<days>\d+(?:[.,]\d+)?)D)?
    )?
    (?:T
        (?:(?P<hours>\d+(?:[.,]\d+)?)H)?
        (?:(?P<minutes>\d+(?:[.,]\d+)?)M)?
        (?:(?P<seconds>\d+(?:[.,]\d+)?)S)?
    )?
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _to_number(s: Optional[str]) -> float:
    if not s:
        return 0.0
    return float(s.replace(",", "."))


def parse_iso8601_to_relativedelta(duration: str) -> relativedelta:
    """
    Parse an ISO 8601 duration string and return a dateutil.relativedelta.relativedelta.

    Examples:
      - "P1Y2M3DT4H5M6S"
      - "PT15M"
      - "P2W"
      - "-P3DT12H"
      - "PT0.5S"
    """
    m = _ISO8601_DURATION_RE.match(duration)
    if not m:
        raise ValueError(f"Invalid ISO 8601 duration: {duration!r}")

    sign = -1 if (m.group("sign") == "-") else 1

    years = _to_number(m.group("years"))
    months = _to_number(m.group("months"))
    weeks = _to_number(m.group("weeks"))
    days = _to_number(m.group("days"))
    hours = _to_number(m.group("hours"))
    minutes = _to_number(m.group("minutes"))
    seconds = _to_number(m.group("seconds"))

    # ISO 8601 allows fractional values; relativedelta expects integers for Y/M
    # (fractional months/years are ambiguous). We reject fractional Y/M explicitly.
    if years and not years.is_integer():
        raise ValueError(f"Fractional years not supported for relativedelta: {duration!r}")
    if months and not months.is_integer():
        raise ValueError(f"Fractional months not supported for relativedelta: {duration!r}")

    # For weeks/days/hours/minutes/seconds, we can carry fractions down to smaller units.
    # Convert weeks to days.
    total_days = days + (weeks * 7.0)

    # Split fractional days into seconds
    day_int = int(total_days)
    day_frac = total_days - day_int

    total_seconds = seconds + (minutes * 60.0) + (hours * 3600.0) + (day_frac * 86400.0)

    sec_int = int(total_seconds)
    sec_frac = total_seconds - sec_int
    microseconds = int(round(sec_frac * 1_000_000))

    # Handle rounding overflow (e.g., 0.9999996 rounds to 1_000_000)
    if microseconds == 1_000_000:
        sec_int += 1
        microseconds = 0

    rd = relativedelta(
        years=sign * int(years),
        months=sign * int(months),
        days=sign * day_int,
        seconds=sign * sec_int,
        microseconds=sign * microseconds,
    )
    return rd


def relativedelta_to_iso8601(rd: relativedelta) -> str:
    """
    Convert dateutil.relativedelta.relativedelta to an ISO 8601 duration string.

    Examples:
      relativedelta(years=1, months=2, days=3,
                    hours=4, minutes=5, seconds=6)
      -> "P1Y2M3DT4H5M6S"
    """

    # Determine sign (ISO-8601 uses a single leading sign)
    def _sign(x: int) -> int:
        return -1 if x < 0 else 1

    signs = [
        _sign(rd.years),
        _sign(rd.months),
        _sign(rd.days),
        _sign(rd.hours),
        _sign(rd.minutes),
        _sign(rd.seconds),
        _sign(rd.microseconds),
    ]
    sign = "-" if any(s < 0 for s in signs) else ""

    # Use absolute values (ISO-8601 sign is global)
    years = abs(rd.years)
    months = abs(rd.months)
    days = abs(rd.days)

    hours = abs(rd.hours)
    minutes = abs(rd.minutes)

    seconds = abs(rd.seconds)
    microseconds = abs(rd.microseconds)

    # Combine seconds + microseconds
    if microseconds:
        seconds = seconds + microseconds / 1_000_000

    date_parts = []
    time_parts = []

    if years:
        date_parts.append(f"{years}Y")
    if months:
        date_parts.append(f"{months}M")
    if days:
        date_parts.append(f"{days}D")

    if hours:
        time_parts.append(f"{hours}H")
    if minutes:
        time_parts.append(f"{minutes}M")
    if seconds:
        # Strip trailing .0 for integers
        if float(seconds).is_integer():
            time_parts.append(f"{int(seconds)}S")
        else:
            time_parts.append(f"{seconds:.6f}".rstrip("0").rstrip(".") + "S")

    # ISO-8601 requires at least one component
    if not date_parts and not time_parts:
        return "PT0S"

    result = sign + "P"
    result += "".join(date_parts)

    if time_parts:
        result += "T" + "".join(time_parts)

    return result