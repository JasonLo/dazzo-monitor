import re
from typing import Dict, List, Optional

LABELS = [
    "Temperature:",
    "Pressure:",
    "Altitude:",
    "Accel:",
    "Mag:",
    "Gyro:",
    "Euler:",
    "Quat:",
    "Lin Accel:",
    "Gravity:",
    "Battery:",
]

_label_group = r"(" + r"|".join(map(re.escape, LABELS)) + r")"


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def _parse_vector(text: str, expected_len: int) -> Optional[List[float]]:
    m = re.search(r"\(([^)]*)\)", text)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    vals: List[float] = []
    for p in parts:
        if p == "":
            continue
        f = _to_float(p)
        if f is None:
            return None
        vals.append(f)
    if len(vals) != expected_len:
        return None
    return vals


def _normalize(raw: str) -> str:
    # Remove carriage returns and newlines entirely to undo mid-token breaks
    s = re.sub(r"[\r\n]+", "", raw)
    # Collapse repeated spaces
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    # Insert a newline before each known label to segment fields
    s = re.sub(_label_group, r"\n\1", s)
    # Remove a leading newline if we inserted one at the very start
    s = s.lstrip("\n").strip()
    return s


def parse_telemetry(raw: str) -> Dict[str, object]:
    """
    Parse a noisy BLE text block into a dictionary of numeric fields.

    The parser tolerates:
    - Labels split across newlines (e.g., "G\nyro" -> "Gyro")
    - Numbers split across newlines (e.g., "0.\n004" -> "0.004")
    - Extra whitespace and trailing noise
    - Joined samples: it extracts the last full sample worth of fields

    Returns an empty dict if no fields recognized.
    """
    s = _normalize(raw)

    # Keep only the last occurrence of each field by iterating lines left-to-right
    fields: Dict[str, str] = {}
    for line in s.split("\n"):
        line = line.strip()
        for label in LABELS:
            if line.startswith(label):
                fields[label] = line[len(label) :].strip()
                break

    out: Dict[str, object] = {}

    # Scalars
    temp_m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*C", fields.get("Temperature:", ""))
    if temp_m:
        out["temperature_c"] = float(temp_m.group(1))

    press_m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*hPa", fields.get("Pressure:", ""))
    if press_m:
        out["pressure_hpa"] = float(press_m.group(1))

    alt_m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*m", fields.get("Altitude:", ""))
    if alt_m:
        out["altitude_m"] = float(alt_m.group(1))

    batt_m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*V", fields.get("Battery:", ""))
    if batt_m:
        out["battery_v"] = float(batt_m.group(1))

    # Vectors
    v = _parse_vector(fields.get("Accel:", ""), 3)
    if v:
        out["accel"] = v

    v = _parse_vector(fields.get("Mag:", ""), 3)
    if v:
        out["mag"] = v

    v = _parse_vector(fields.get("Gyro:", ""), 3)
    if v:
        out["gyro"] = v

    v = _parse_vector(fields.get("Euler:", ""), 3)
    if v:
        out["euler"] = v

    v = _parse_vector(fields.get("Quat:", ""), 4)
    if v:
        out["quat"] = v

    v = _parse_vector(fields.get("Lin Accel:", ""), 3)
    if v:
        out["lin_accel"] = v

    v = _parse_vector(fields.get("Gravity:", ""), 3)
    if v:
        out["gravity"] = v

    return out
