from __future__ import annotations

import ast
import operator
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from error_handler import NetworkError, ToolError


def get_weather(city: str, unit: str = "celsius") -> dict:
    """Fetch current weather for a city from Open-Meteo APIs.

    Args:
        city: City name.
        unit: celsius or fahrenheit.

    Returns:
        Weather payload.

    Raises:
        ToolError: For invalid city or bad weather payload.
        NetworkError: For network failures.
    """
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        )
        geo.raise_for_status()
        geo_data = geo.json()
    except requests.RequestException as exc:
        raise NetworkError(f"Geocoding request failed: {exc}") from exc

    results = geo_data.get("results") or []
    if not results:
        raise ToolError(f"City '{city}' not found.")

    location = results[0]
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is None or lon is None:
        raise ToolError("Geocoding response missing latitude/longitude.")

    normalized_unit = unit.strip().lower()
    if normalized_unit not in {"celsius", "fahrenheit"}:
        raise ToolError("unit must be either 'celsius' or 'fahrenheit'.")

    temp_unit = normalized_unit
    windspeed_unit = "kmh"

    try:
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "hourly": "relative_humidity_2m",
                "temperature_unit": temp_unit,
                "windspeed_unit": windspeed_unit,
            },
            timeout=10,
        )
        weather.raise_for_status()
        weather_data = weather.json()
    except requests.RequestException as exc:
        raise NetworkError(f"Weather request failed: {exc}") from exc

    current = weather_data.get("current_weather")
    if not current:
        raise ToolError("Weather response missing current_weather data.")

    humidity = None
    hourly_time = weather_data.get("hourly", {}).get("time", [])
    hourly_humidity = weather_data.get("hourly", {}).get("relative_humidity_2m", [])
    if hourly_time and hourly_humidity and current.get("time") in hourly_time:
        idx = hourly_time.index(current["time"])
        humidity = hourly_humidity[idx]

    weather_code = current.get("weathercode")
    condition = _weather_code_to_condition(weather_code)

    return {
        "city": location.get("name", city),
        "temperature": current.get("temperature"),
        "unit": normalized_unit,
        "condition": condition,
        "humidity": humidity,
        "wind_speed": current.get("windspeed"),
    }


def calculate(expression: str, precision: int = 2) -> dict:
    """Safely evaluate arithmetic expression using AST.

    Args:
        expression: Arithmetic expression.
        precision: Decimal precision.

    Returns:
        Calculation payload with steps.

    Raises:
        ToolError: For invalid/unsafe expressions.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"Invalid expression syntax: {exc}") from exc

    steps: list[str] = []
    result = _eval_ast(tree.body, steps)
    rounded = round(result, precision)

    return {
        "expression": expression,
        "result": rounded,
        "steps": steps,
    }


def search_dictionary(word: str, language: str = "en") -> dict:
    """Search dictionary definitions using DictionaryAPI.

    Args:
        word: Word to lookup.
        language: Language code.

    Returns:
        Dictionary payload.

    Raises:
        ToolError: For missing entries.
        NetworkError: For network failures.
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/{language}/{word}"
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        raise NetworkError(f"Dictionary request failed: {exc}") from exc

    if resp.status_code == 404:
        raise ToolError(f"Word '{word}' not found for language '{language}'.")

    try:
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise NetworkError(f"Dictionary API error: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise ToolError("Dictionary response format invalid.")

    entry = data[0]
    meanings = entry.get("meanings") or []
    if not meanings:
        raise ToolError("No meanings found in dictionary response.")

    first_meaning = meanings[0]
    definitions_data = first_meaning.get("definitions") or []

    definitions = [d.get("definition") for d in definitions_data if d.get("definition")][:3]
    examples = [d.get("example") for d in definitions_data if d.get("example")][:2]

    synonyms: list[str] = []
    for meaning in meanings:
        synonyms.extend(meaning.get("synonyms") or [])
    synonyms = list(dict.fromkeys(synonyms))[:5]

    phonetic = entry.get("phonetic")
    if not phonetic:
        phonetics = entry.get("phonetics") or []
        for p in phonetics:
            text = p.get("text")
            if text:
                phonetic = text
                break

    return {
        "word": entry.get("word", word),
        "phonetic": phonetic,
        "part_of_speech": first_meaning.get("partOfSpeech"),
        "definitions": definitions,
        "example_sentences": examples,
        "synonyms": synonyms,
    }


def get_current_time(timezone: str = "UTC") -> dict:
    """Get current time details for an IANA timezone.

    Args:
        timezone: IANA timezone string.

    Returns:
        Time payload.

    Raises:
        ToolError: For invalid timezone.
    """
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ToolError(
            f"Invalid timezone '{timezone}'. Use IANA timezone like 'UTC' or 'Asia/Karachi'."
        ) from exc

    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "current_time": now.isoformat(),
        "unix_timestamp": int(now.timestamp()),
        "day_of_week": now.strftime("%A"),
        "is_weekend": now.weekday() >= 5,
        "utc_offset": now.strftime("%z"),
    }


def unit_converter(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert units across supported categories.

    Args:
        value: Numeric value.
        from_unit: Source unit.
        to_unit: Target unit.

    Returns:
        Conversion payload.

    Raises:
        ToolError: For unknown/incompatible units.
    """
    from_u = _normalize_unit_alias(from_unit)
    to_u = _normalize_unit_alias(to_unit)

    category = _get_unit_category(from_u)
    if category is None:
        raise ToolError(f"Unsupported from_unit '{from_unit}'.")

    target_category = _get_unit_category(to_u)
    if target_category is None:
        raise ToolError(f"Unsupported to_unit '{to_unit}'.")

    if category != target_category:
        raise ToolError("Units belong to different categories and cannot be converted.")

    if category == "temperature":
        converted, formula = _convert_temperature(value, from_u, to_u)
    else:
        factors = _CATEGORY_FACTORS[category]
        base_value = value * factors[from_u]
        converted = base_value / factors[to_u]
        formula = f"({value} * {factors[from_u]}) / {factors[to_u]}"

    return {
        "original_value": value,
        "original_unit": from_u,
        "converted_value": converted,
        "converted_unit": to_u,
        "category": category,
        "formula_used": formula,
    }


_ALLOWED_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_ast(node: ast.AST, steps: list[str], depth: int = 0) -> float:
    if depth > 50:
        raise ToolError("Expression too deeply nested (max depth 50).")
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Num):
        return float(node.n)

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BIN_OPS:
            raise ToolError("Expression contains unsupported binary operator.")
        left = _eval_ast(node.left, steps, depth + 1)
        right = _eval_ast(node.right, steps, depth + 1)
        if op_type is ast.Div and right == 0:
            raise ToolError("Division by zero is not allowed.")
        result = _ALLOWED_BIN_OPS[op_type](left, right)
        steps.append(f"{left} {node.op.__class__.__name__} {right} = {result}")
        return float(result)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARY_OPS:
            raise ToolError("Expression contains unsupported unary operator.")
        value = _eval_ast(node.operand, steps, depth + 1)
        result = _ALLOWED_UNARY_OPS[op_type](value)
        steps.append(f"{node.op.__class__.__name__} {value} = {result}")
        return float(result)

    raise ToolError(
        "Unsafe expression detected. Only numbers and +,-,*,/,**,% operators are allowed."
    )


def _weather_code_to_condition(code: int | None) -> str:
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        95: "Thunderstorm",
    }
    return mapping.get(code, "Unknown")


_CATEGORY_FACTORS: dict[str, dict[str, float]] = {
    "length": {
        "mm": 0.001,
        "cm": 0.01,
        "m": 1.0,
        "km": 1000.0,
        "inch": 0.0254,
        "foot": 0.3048,
        "yard": 0.9144,
        "mile": 1609.344,
    },
    "weight": {
        "mg": 0.001,
        "g": 1.0,
        "kg": 1000.0,
        "tonne": 1_000_000.0,
        "ounce": 28.349523125,
        "pound": 453.59237,
    },
    "speed": {
        "mps": 1.0,
        "kph": 0.2777777778,
        "mph": 0.44704,
        "knot": 0.514444,
    },
}

_TEMPERATURE_UNITS = {"celsius", "fahrenheit", "kelvin"}

_UNIT_ALIASES = {
    "km/h": "kph",
    "m/s": "mps",
    "mi": "mile",
    "miles": "mile",
    "kilometers": "km",
    "kilometres": "km",
    "meters": "m",
    "metres": "m",
    "feet": "foot",
    "inches": "inch",
    "lbs": "pound",
    "f": "fahrenheit",
    "c": "celsius",
    "k": "kelvin",
}


def _normalize_unit_alias(unit: str) -> str:
    normalized = unit.strip().lower()
    return _UNIT_ALIASES.get(normalized, normalized)


def _get_unit_category(unit: str) -> str | None:
    if unit in _TEMPERATURE_UNITS:
        return "temperature"
    for category, factors in _CATEGORY_FACTORS.items():
        if unit in factors:
            return category
    return None


def _convert_temperature(value: float, from_u: str, to_u: str) -> tuple[float, str]:
    celsius_value: float
    if from_u == "celsius":
        celsius_value = value
    elif from_u == "fahrenheit":
        celsius_value = (value - 32) * 5 / 9
    elif from_u == "kelvin":
        celsius_value = value - 273.15
    else:
        raise ToolError(f"Unsupported temperature from_unit '{from_u}'.")

    if to_u == "celsius":
        result = celsius_value
        formula = f"{value} {from_u} -> celsius = {result}"
    elif to_u == "fahrenheit":
        result = (celsius_value * 9 / 5) + 32
        formula = f"({celsius_value} * 9/5) + 32 = {result}"
    elif to_u == "kelvin":
        result = celsius_value + 273.15
        formula = f"{celsius_value} + 273.15 = {result}"
    else:
        raise ToolError(f"Unsupported temperature to_unit '{to_u}'.")

    return result, formula
