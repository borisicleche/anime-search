import os
import time

from dotenv import load_dotenv
from openai import OpenAI, omit
from pydantic import BaseModel, Field, field_validator

# Load variables from .env into os.environ (existing env vars take precedence)
load_dotenv()

PROMPT = "Recommend 3 anime similar to Cowboy Bebop."


# Structured output: the model must reply with JSON matching these models.
# The SDK turns them into a JSON schema and parses the reply back into objects.
class Recommendation(BaseModel):
    title: str
    reason: str = Field(description="One sentence on why it is similar.")
    # No ge/le here: Anthropic rejects minimum/maximum in the schema (400),
    # so the range lives in the description and is checked by the validator below.
    similarity_score: float = Field(
        description="0.0 (unrelated) to 1.0 (nearly identical)."
    )

    # Runs locally when the reply is parsed; never sent to the API
    @field_validator("similarity_score")
    @classmethod
    def check_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("similarity_score must be between 0.0 and 1.0")
        return value


# The top level has to be an object, so the list lives under "recommendations".
class RecommendationList(BaseModel):
    recommendations: list[Recommendation]


MODELS = ["claude-haiku-5-5"]

# USD per 1M tokens: (input, output). Update manually when prices change.
# claude-haiku-5-5 price applies to prompts up to 100K tokens ($0.50 / $2.50 beyond).
PRICES_PER_MTOK = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Sampling temperature (0.0 = deterministic, 1.0 = most varied).
# None means "don't send it" and the model uses its default.
# claude-haiku-5-5 rejects any temperature with a 400 ("deprecated for this model").
TEMPERATURE: float | None = None

# OpenAI SDK pointed at Anthropic's OpenAI-compatible endpoint.
# It does not read ANTHROPIC_API_KEY on its own, so pass it explicitly.
client = OpenAI(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    base_url="https://api.anthropic.com/v1/",
)


def run(model: str, temperature: float | None = None) -> None:
    # The compatibility layer supports Chat Completions, not the Responses API
    start = time.perf_counter()
    response = client.chat.completions.parse(
        model=model,
        max_tokens=1024,
        # `omit` leaves the field out of the request entirely
        temperature=omit if temperature is None else temperature,
        messages=[{"role": "user", "content": PROMPT}],
        # Pass the class itself; the SDK builds the json_schema from it
        response_format=RecommendationList,
    )
    latency_s = time.perf_counter() - start

    print(f"===== {model} (temperature={temperature}) =====")
    # `parsed` is already a validated RecommendationList (None on refusal)
    data = response.choices[0].message.parsed
    if data is None:
        print("No parsed output:", response.choices[0].message.refusal)
    else:
        print(f"Data: {data.model_dump()}")
        print()
        for rec in data.recommendations:
            print(f"- {rec.title} ({rec.similarity_score:.2f}): {rec.reason}")
    print(f"\nLatency:       {latency_s:.2f} s")
    print("Finish reason:", response.choices[0].finish_reason)

    usage = response.usage
    if usage:
        input_price, output_price = PRICES_PER_MTOK[model]
        cost = (
            usage.prompt_tokens * input_price + usage.completion_tokens * output_price
        ) / 1_000_000
        print(f"Input tokens:  {usage.prompt_tokens}")
        print(f"Output tokens: {usage.completion_tokens}")
        print(f"Total:         {usage.total_tokens}")
        print(f"Cost:          ${cost:.6f}")
    print()


# Only run when executed directly, not when imported from another module
if __name__ == "__main__":
    for model in MODELS:
        run(model, TEMPERATURE)
