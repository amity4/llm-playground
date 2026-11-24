"""llm-playground: run one prompt at several temperatures and compare
TTFT, total time, tokens, cost and output. See PLAN.md for the design."""

import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

TEMPERATURES = [0, 0.7, 1.0]
RUNS_PER_TEMPERATURE = 1
PREVIEW_CHARS = 40

# --- Config: fail fast if anything is missing --------------------------------
load_dotenv()

names = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_PRICE_INPUT_PER_M", "LLM_PRICE_OUTPUT_PER_M"]
config = {name: os.getenv(name) for name in names}
missing = [name for name, value in config.items() if not value]
if missing:
    sys.exit(f"Missing in .env: {', '.join(missing)}")

try:
    price_in = float(config["LLM_PRICE_INPUT_PER_M"])
    price_out = float(config["LLM_PRICE_OUTPUT_PER_M"])
except ValueError:
    sys.exit("LLM_PRICE_INPUT_PER_M and LLM_PRICE_OUTPUT_PER_M must be numbers (USD per million tokens)")

if len(sys.argv) != 2:
    sys.exit('Usage: python main.py "your prompt"')
prompt = sys.argv[1]
model = config["LLM_MODEL"]

# max_retries=0: a hidden SDK retry would add the backoff wait to TTFT
client = OpenAI(base_url=config["LLM_BASE_URL"], api_key=config["LLM_API_KEY"], max_retries=0)


def read_usage(chunk):
    """Token counts from a chunk, or None. Standard field first, then Groq's x_groq."""
    if chunk.usage:
        return chunk.usage.prompt_tokens, chunk.usage.completion_tokens
    groq_usage = ((chunk.model_extra or {}).get("x_groq") or {}).get("usage")
    if groq_usage:
        return groq_usage["prompt_tokens"], groq_usage["completion_tokens"]
    return None

def print_chunks(chunks):
    """Print the first two and last two chunks as readable JSON."""
    for i in [0, 1, -2, -1]:
        print(f"--- chunks[{i}] ---")
        print(chunks[i].model_dump_json(indent=2))


def run_once(temperature):
    """One streamed call. Returns (ttft, total, tokens_in, tokens_out, text)."""
    t_start = time.perf_counter()
    t_first = None
    usage = None
    parts = []
    chunks = []

    request = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    stream = client.chat.completions.create(**request)
    
    for chunk in stream:
        chunks.append(chunk)
        if chunk.choices:
            text = chunk.choices[0].delta.content
            if text:  # the first chunk only carries the role, so skip empty content
                if t_first is None:
                    t_first = time.perf_counter()
                parts.append(text)
        usage = read_usage(chunk) or usage
    t_end = time.perf_counter()
    ttft = (t_first - t_start) if t_first else None
    tokens_in, tokens_out = usage if usage else (None, None)
    return ttft, t_end - t_start, tokens_in, tokens_out, "".join(parts), chunks


def show(value, number_format=""):
    """Format a number for the table, or '-' if the value is missing."""
    return "-" if value is None else format(value, number_format)


# --- Run and print each row as soon as it finishes -------------------------
print(f"Model: {model}")
print(f"Prompt: {prompt}\n")
print(f"{'Temp':<5} {'Run':<4} {'TTFT(s)':>7} {'Total(s)':>8} {'In':>5} {'Out':>5} {'Cost($)':>9}  Output (first {PREVIEW_CHARS} chars)")

for temperature in TEMPERATURES:
    for run in range(1, RUNS_PER_TEMPERATURE + 1):
        try:
            ttft, total, tokens_in, tokens_out, text, chunks = run_once(temperature)
        except RateLimitError:
            print(f"{temperature:<5} {run:<4} {'429':>7}  rate limited, no retry (see PLAN.md)", flush=True)
            continue

        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000 if tokens_in is not None else None
        preview = text.replace("\n", " ")[:PREVIEW_CHARS]
        print(
            f"{temperature:<5} {run:<4} {show(ttft, '.2f'):>7} {total:>8.2f} "
            f"{show(tokens_in):>5} {show(tokens_out):>5} {show(cost, '.6f'):>9}  {preview}",
            flush=True,
        )
        print() 
        if RUNS_PER_TEMPERATURE == 1:
            print() 
            print_chunks(chunks)
            print() 
        print() 

    print()  # blank line between temperature groups

