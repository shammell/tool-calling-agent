from __future__ import annotations

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Use this when the user asks for current weather in a city. It returns city name, temperature in requested unit, weather condition, humidity, and wind speed using live Open-Meteo data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name to lookup."},
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "default": "celsius",
                        "description": "Temperature output unit.",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Use this when the user asks for arithmetic evaluation. It safely evaluates a math expression and returns the rounded numeric result plus operation steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression with +,-,*,/,**,%.",
                    },
                    "precision": {
                        "type": "integer",
                        "default": 2,
                        "description": "Decimal places for rounded output.",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_dictionary",
            "description": "Use this when the user asks for word meaning, pronunciation, or synonyms. It returns phonetic, part of speech, top definitions, examples, and synonyms from DictionaryAPI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "Word to search."},
                    "language": {
                        "type": "string",
                        "default": "en",
                        "description": "Language code supported by DictionaryAPI.",
                    },
                },
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Use this when the user asks current time in a timezone. It returns ISO timestamp, unix time, weekday, weekend flag, and UTC offset using Python zoneinfo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "default": "UTC",
                        "description": "IANA timezone, e.g. Asia/Karachi.",
                    }
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unit_converter",
            "description": "Use this when the user asks to convert units for length, weight, temperature, or speed. It returns converted value, detected category, and formula details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "Input numeric value."},
                    "from_unit": {"type": "string", "description": "Source unit."},
                    "to_unit": {"type": "string", "description": "Target unit."},
                },
                "required": ["value", "from_unit", "to_unit"],
            },
        },
    },
]
