import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# Read LLM_BASE_URL, LLM_API_KEY and LLM_MODEL from .env into environment variables
load_dotenv()

base_url = os.getenv("LLM_BASE_URL")
api_key = os.getenv("LLM_API_KEY")
model = os.getenv("LLM_MODEL")

# Fail fast: stop with a clear message if config is missing
missing = [name for name, value in [("LLM_BASE_URL", base_url), ("LLM_API_KEY", api_key), ("LLM_MODEL", model)] if not value]
if missing:
    sys.exit(f"Missing in .env: {', '.join(missing)}")

client = OpenAI(base_url=base_url, api_key=api_key)


def ask(messages):
    """One stateless request: the model only sees what is in this messages list."""
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content, response.usage.prompt_tokens


first_question = {"role": "user", "content": "Explain what a token is in one sentence."}
follow_up = {"role": "user", "content": "Give me an example of one."}

# Call 1: the first question
first_answer, tokens_1 = ask([first_question])
print(f"--- Call 1: first question ({tokens_1} prompt tokens)\n{first_answer}\n")

# Call A: the follow-up alone, with no history
answer_a, tokens_a = ask([follow_up])
print(f"--- Call A: follow-up WITHOUT history ({tokens_a} prompt tokens)\n{answer_a}\n")

# Call B: the same follow-up, with the history our code keeps and resends
history = [
    first_question,
    {"role": "assistant", "content": first_answer},
    follow_up,
]
answer_b, tokens_b = ask(history)
print(f"--- Call B: follow-up WITH history ({tokens_b} prompt tokens)\n{answer_b}")
