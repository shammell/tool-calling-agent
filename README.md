# Tool-Calling AI Agent (Groq)

Production-quality Python CLI agent with tool calling, structured responses, and robust error handling.

## Features

- Groq SDK integration (`llama-3.3-70b-versatile`)
- 5 real tools:
  - Weather (Open-Meteo)
  - Safe calculator (AST-based, no `eval`)
  - Dictionary lookup (DictionaryAPI)
  - Time by timezone (`zoneinfo`)
  - Unit conversion (length/weight/temperature/speed)
- Multi-round tool-calling loop
- Parallel tool-call handling (multiple tool calls in one assistant turn)
- Structured Pydantic response models
- Rich CLI with `/reset`, `/history`, `/stats`, `/quit`

## Project Structure

```text
task1_tool_agent/
├── main.py
├── agent.py
├── tools.py
├── schemas.py
├── response_models.py
├── error_handler.py
├── logger.py
├── .env.example
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.11+
- Groq API key

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
```

Set in `.env`:

```env
GROQ_API_KEY=your_real_key
```

## Run

```bash
python main.py
```

## Example Prompts

1. `What's the weather like in Tokyo right now?`
2. `Calculate (15.7 * 83) / (2 ** 8) to 4 decimal places`
3. `What does ephemeral mean?`
4. `What time is it in Istanbul?`
5. `Convert 100 miles per hour to km/h and also tell me what 72 fahrenheit is in celsius`

## Tool Error Behavior

All tool failures return structured error payloads with:
- `tool_name`
- `error_type`
- `error_message`
- `suggestion`
- `timestamp`

Tracebacks are logged in console, not exposed to model output.

## Notes

- HTTP calls use `timeout=10`.
- Calculator allows only numeric literals and operators: `+ - * / ** %`.
- Invalid timezone values return clear error messages.
