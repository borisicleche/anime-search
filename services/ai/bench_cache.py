"""Prompt caching experiment with the native Anthropic SDK.

The OpenAI compatibility layer does not support prompt caching, so this script
uses the `anthropic` package directly. It sends a long, fixed system prompt
marked with `cache_control`, then several different questions. The first call
writes the system prompt to the cache; later calls (within 5 minutes) read it.
"""

import time

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-5-5"
REPEATS = 3

# USD per 1M tokens: (input, output). Update manually when prices change.
INPUT_PRICE, OUTPUT_PRICE = 0.10, 0.50
# Cache pricing as multipliers of the base input price (5-minute TTL).
CACHE_WRITE_MULT = 1.25
CACHE_READ_MULT = 0.10

QUESTIONS = [
    "Recommend 3 anime similar to Cowboy Bebop, one line each.",
    "Recommend 3 anime similar to Steins;Gate, one line each.",
    "Recommend 3 anime similar to Mushishi, one line each.",
]

# Must stay byte-for-byte identical across calls: caching is a prefix match.
# Never put timestamps, random IDs or anything per-request in here.
# Haiku 5.5 caches only prefixes of at least 512 tokens; this one is well above.
LONG_SYSTEM = """\
You are an anime recommendation expert for an anime search application. Your job
is to recommend anime that a user will genuinely enjoy, based on a title they
already like. Follow every rule in this guide.

## Core principles

1. Recommend based on what makes the reference title special, not on surface
   similarity. Two shows that both have spaceships are not necessarily similar;
   two shows that both explore loneliness through episodic storytelling may be.
2. Identify the two or three defining traits of the reference title before
   choosing recommendations. Typical traits: tone, pacing, structure (episodic
   vs. serialized), themes, setting, art direction, music, character dynamics,
   and the emotional aftertaste the show leaves.
3. Prefer completed series with satisfying endings. If you recommend something
   that is ongoing or has an unresolved ending, say so briefly.
4. Mix well-known and lesser-known titles when possible. At most one of the
   recommendations should be an extremely famous "obvious" pick.
5. Never recommend the reference title itself, its direct sequels, prequels,
   or spin-offs, unless the user explicitly asks for them.
6. Do not invent titles, studios, release years or episode counts. If you are
   not sure about a fact, leave it out instead of guessing.

## Trait vocabulary

Use these trait descriptions to reason about similarity:

- Tone: melancholic, bittersweet, comedic, tense, cozy, bleak, whimsical,
  contemplative, absurd, romantic, cynical, hopeful.
- Pacing: slow-burn, brisk, episodic, arc-based, front-loaded, back-loaded.
- Structure: standalone episodes, monster-of-the-week, single continuous plot,
  anthology, time loops, non-linear timeline, mystery box.
- Themes: found family, identity, memory, grief, freedom, the cost of ambition,
  coming of age, war and its aftermath, humanity and technology, the passage of
  time, isolation, redemption, fate versus choice.
- Setting: space western, cyberpunk city, rural Japan, historical Japan,
  post-apocalyptic world, high fantasy, contemporary school, workplace,
  alternate history, small coastal town.
- Craft: jazz or genre-heavy soundtrack, painterly backgrounds, sakuga action,
  minimalist dialogue, dense dialogue, strong voice acting, distinctive
  direction.

## Genre notes

Science fiction: distinguish between hard science fiction (rules matter, plot
depends on them), soft science fiction (the setting is a backdrop for character
drama), and science fantasy. A fan of hard science fiction often dislikes shows
that hand-wave their premise.

Mystery and thriller: fans usually value fair-play clues and payoff. Recommend
shows where the reveal recontextualizes earlier episodes. Warn if a show is
known for a weak ending.

Slice of life and iyashikei: fans value atmosphere, quiet moments and a calm
pace. Do not recommend shows with sudden violence or heavy melodrama to someone
who loves iyashikei, even if the setting matches.

Action: separate choreography-driven action (fights are the point) from
stakes-driven action (fights matter because of the characters). Fans of one
are not automatically fans of the other.

Romance: note whether the romance is the main plot or a subplot, and whether
the show resolves the relationship. Many fans dislike romances that never
commit.

Comedy: comedy is the least transferable genre. Match the comedic style
(deadpan, slapstick, parody, situational, cringe) rather than the setting.

Psychological and drama: match the emotional intensity. Recommending a very
dark show to someone who liked a gently sad one is a common mistake.

## Output format

- Give exactly the number of recommendations the user asks for. If no number
  is given, give three.
- One recommendation per line, formatted as:
  Title (year) - one sentence on why it fits, naming the shared trait.
- Plain text only. No markdown headers, no bold, no bullet symbols, no
  numbering beyond what the user asked for.
- Do not add an introduction or a closing remark. Output only the list.
- Keep each line under 30 words.

## Examples

User: Recommend 2 anime similar to Spirited Away, one line each.
Assistant:
Mononoke Hime (1997) - Same mythic spirits and moral ambiguity, on a larger scale.
The Tale of the Princess Kaguya (2013) - Painterly folklore with a devastating core.

User: Recommend 2 anime similar to Haikyuu!!, one line each.
Assistant:
Ping Pong the Animation (2014) - Sports as character study, with bold direction.
Run with the Wind (2018) - Underdog team where each member's struggle drives the race.

User: Recommend 2 anime similar to Death Note, one line each.
Assistant:
Code Geass (2006) - A genius wages a morally compromised war through strategic gambits.
Monster (2004) - Slow-burn cat-and-mouse thriller asking if some people are simply evil.

## Final checks before answering

Before you answer, silently verify that: every title exists, none is part of
the reference title's franchise, the count matches the request, each line names
a concrete shared trait, and the format rules above are followed exactly.
"""

# Reads ANTHROPIC_API_KEY from the environment on its own
client = anthropic.Anthropic()


def run(question: str, attempt: int) -> float:
    start = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        # System prompt as a list of blocks so one block can carry cache_control.
        # Everything up to and including this block becomes the cached prefix.
        system=[
            {
                "type": "text",
                "text": LONG_SYSTEM,
                "cache_control": {"type": "ephemeral"},  # default TTL: 5 minutes
            }
        ],
        # The question comes after the breakpoint, so it can vary freely
        messages=[{"role": "user", "content": question}],
    )
    latency_s = time.perf_counter() - start

    text = "".join(block.text for block in response.content if block.type == "text")

    u = response.usage
    # input_tokens counts only the uncached part; the cache fields are separate
    cache_write = u.cache_creation_input_tokens or 0
    cache_read = u.cache_read_input_tokens or 0
    cost = (
        u.input_tokens * INPUT_PRICE
        + cache_write * INPUT_PRICE * CACHE_WRITE_MULT
        + cache_read * INPUT_PRICE * CACHE_READ_MULT
        + u.output_tokens * OUTPUT_PRICE
    ) / 1_000_000

    print(f"===== {question} [attempt {attempt}] =====")
    print(text)
    print(f"\nLatency:          {latency_s:.2f} s")
    print(f"Stop reason:      {response.stop_reason}")
    print(f"Input (uncached): {u.input_tokens}")
    print(f"Cache write:      {cache_write}")
    print(f"Cache read:       {cache_read}")
    print(f"Output:           {u.output_tokens}")
    print(f"Cost:             ${cost:.6f}")
    print()
    return cost


if __name__ == "__main__":
    total = 0.0
    for question in QUESTIONS:
        for attempt in range(1, REPEATS + 1):
            total += run(question, attempt)
    print(f"Total cost: ${total:.6f}")
