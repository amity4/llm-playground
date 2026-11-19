# llm-playground — plan

A CLI that runs one prompt at several temperatures and shows tokens, cost, latency and time-to-first-token (TTFT).

## What it does
1. Read config from `.env`: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, plus `LLM_PRICE_INPUT_PER_M` and `LLM_PRICE_OUTPUT_PER_M` (USD per million tokens). Fail fast if any are missing.
2. Take the prompt as a command-line argument.
3. For each temperature in **0, 0.7, 1.0**, run the prompt **3 times**: 9 calls, **sequential**.
4. For each call, stream the response and record:
   - `t_start` just before the request
   - `t_first` at the first chunk that has **non-empty content** (the first chunk only carries the role, so it doesn't count)
   - `t_end` after the last chunk
   - usage from the final chunk (empty `choices`, so guard with `if chunk.choices`; fall back to `x_groq.usage` if `usage` is missing)
5. Print one table.

## Calculations
- TTFT = `t_first − t_start` (queue + prefill)
- Total = `t_end − t_start`
- Decode = Total − TTFT
- Cost = input_tokens × input_price / 1M + output_tokens × output_price / 1M

## Output table
One row per run, 9 rows grouped by temperature, kept narrow enough for the terminal:

```
Temp  Run  TTFT(s)  Total(s)  In  Out  Cost($)   Output (first 40 chars)
0.0   1    0.31     2.40      42  180  0.00012   A token is a chunk of text...
...
```

Averages are left out on purpose: they would hide the variation between runs, and seeing that variation is the point of the tool.

## Test prompts
- **Control (peaked distribution):** "What is the capital of France? One word." Expect the same output at every temperature.
- **Open-ended (flat distribution):** "Write a one-line tagline for a telecom company." Expect the outputs to vary as the temperature rises.

## Decisions and what they cost
| Decision | Why | What we give up |
|---|---|---|
| Prices in `.env` | Config, not code; change the model without editing code | Model and prices can drift out of sync (later: `models.json`) |
| Sequential calls | Simple; avoids 429 rate limits | 9 calls ≈ 9 × total time (slow) |
| 3 runs per temperature | Shows variation within one temperature | 3x the cost and time of 1 run |
| Streaming | Needed to measure TTFT (two timestamps) | More code than one non-streaming call |
| Output truncated to 40 chars | Fits the terminal | Can't compare full outputs in the table |
| Print each row as soon as its call finishes | A crash on call 6 doesn't lose calls 1–5 | Can't sort or align the table at the end |
| `max_retries=0`; catch `RateLimitError` → row shows "429" | A hidden SDK retry would inflate TTFT and corrupt the measurement | A 429 means a missing row instead of a slow one |

## Out of scope (YAGNI)
Parallel calls, retries, `models.json`, saving results to a file.
