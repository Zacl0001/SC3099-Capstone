"""Live smoke test for module3: short LLM analyses + real KAS chunk legs.

Run from the module root (recommended, checks nothing else):
    python run_tests.py --tier smoke
Run standalone:
    $env:PYTHONPATH='.'; python tests/smoke_test.py

What it covers (cheap live checks only, ~2-4 minutes):
  1. preflight  - Ollama reachable and the configured model is pulled
  2. LLM path   - summary / actions / decisions / topics on a short transcript
                  (these stay on the direct path: transcript is below the
                  chunk threshold, so no KAS call happens)
  3. chunk path - the REAL KAS /chunk endpoint splits a sample meeting
                  (>= 2 chunks, every chunk non-empty)
  4. gate check - a transcript over CHUNK_THRESHOLD_CHARS goes through
                  chunk_analysis_input() and comes back as multiple pieces

Legs 3 and 4 require the KAS HTTP API on the configured port. If it is down they are SKIPPED
with a warning instead of failing, so this smoke still works on a
module3-only machine.
"""

import asyncio
import sys

import httpx

from app.core.config import get_settings
from app.services import (
    action_service,
    decision_service,
    summarization_service,
    topic_service,
)
from app.services.chunked_extraction import chunk_analysis_input
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

BASE_TRANSCRIPT = """
Alice: Let's talk about the Q3 release timeline.
Bob: We should target October 1st.
Alice: Agreed, October 1st works. Carol, can you prepare the release notes?
Carol: Sure, I'll have them done by Friday.
Alice: We've decided to drop the mobile app feature from this release.
Bob: OK, mobile app goes to Q4.
Alice: Let's move on to the budget.
Carol: The budget is approved at 50k.
"""

MEETING_SECTIONS = [
    """
Alice: Let's review the infrastructure migration.
David: The staging migration is complete, and database validation passed.
Bob: What is the rollback plan if production migration fails?
David: We'll restore the latest verified snapshot and redirect traffic.
Carol: I'll document the recovery procedure in the operational runbook.
Alice: Please complete that documentation before the release.
""",
    """
Alice: Let's discuss customer feedback.
Carol: We received 240 responses during the beta program.
Bob: The most common complaints concern dashboard loading and navigation.
David: The dashboard currently loads in 3.2 seconds.
Alice: Our target is below two seconds.
David: I'll optimize the summary query and add an index.
Carol: I'll update the customer feedback tracker.
""",
    """
Alice: Let's review security requirements.
David: The security review identified two medium-priority findings.
Bob: Are either of them release blockers?
David: No, but both should be resolved before the next quarterly review.
Alice: I'll assign session expiration to David and access-control review to Bob.
Bob: I'll complete the access-control review by next Tuesday.
Carol: I'll record the owners and deadlines in the meeting minutes.
""",
    """
Alice: Let's confirm release communication.
Carol: I'll prepare internal announcements and customer-facing release notes.
Bob: The announcement should mention dashboard performance improvements.
Alice: Do not promise that every page will load in under two seconds.
Carol: I'll send the draft for review on Thursday.
Alice: The mobile app feature must remain out of the Q3 announcement.
Bob: Agreed. The mobile app is deferred to Q4.
""",
    """
Alice: Let's review the budget and remaining risks.
Carol: The approved budget is 50k.
Bob: Engineering has 30k, QA has 10k, and documentation has 10k.
David: Regression testing may be delayed if additional defects appear.
Alice: No production deployment without QA sign-off.
Bob: I'll arrange additional engineering support if needed.
Carol: I'll schedule the release readiness meeting for September 26th.
""",
]

# Two distinct topics -> the semantic splitter should find a breakpoint and
# produce at least two chunks.
CHUNK_SAMPLE = "\n".join(section.strip() for section in MEETING_SECTIONS[:2])


def build_large_transcript(target_chars: int) -> str:
    """Build a realistic transcript at least target_chars long."""
    parts = [BASE_TRANSCRIPT.strip()]
    index = 0

    while len("\n\n".join(parts)) < target_chars:
        section = MEETING_SECTIONS[index % len(MEETING_SECTIONS)]
        round_number = index // len(MEETING_SECTIONS) + 1
        parts.append(
            f"Discussion round {round_number}:\n{section.strip()}"
        )
        index += 1

    transcript = "\n\n".join(parts)

    # Trim only the final excess characters to test exact boundaries.
    return transcript[:target_chars]


# ----------------------------------------------------------------------
# Results bookkeeping
# ----------------------------------------------------------------------

class Results:
    """Collect PASS/FAIL/SKIP per leg so the exit code is meaningful."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def passed(self, leg: str) -> None:
        print(f"  [PASS] {leg}")

    def skipped(self, leg: str, reason: str) -> None:
        print(f"  [SKIP] {leg} - {reason}")

    def failed(self, leg: str, reason: str) -> None:
        print(f"  [FAIL] {leg} - {reason}")
        self.failures.append(leg)


# ----------------------------------------------------------------------
# Preflight
# ----------------------------------------------------------------------


def check_ollama(settings) -> bool:
    """Ollama reachable and the configured model pulled."""
    base = settings.llm_base_url.rsplit("/v1", 1)[0]
    try:
        response = httpx.get(f"{base}/api/tags", timeout=10.0)
        response.raise_for_status()
        names = [model["name"] for model in response.json().get("models", [])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"  [FAIL] preflight - cannot reach Ollama at {base}: {exc}")
        return False

    pulled = any(
        name == settings.llm_model or name.startswith(f"{settings.llm_model}:")
        for name in names
    )
    if not pulled:
        print(
            f"  [FAIL] preflight - model '{settings.llm_model}' not pulled "
            f"(available: {names or 'none'})"
        )
        return False

    print(f"  [PASS] preflight - Ollama up, model '{settings.llm_model}' pulled")
    return True


def check_kas(settings) -> bool:
    """KAS HTTP API reachable? (chunk legs depend on it)."""
    try:
        response = httpx.get(f"{settings.kas_base_url}/health", timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(
            f"  [WARN] KAS not reachable at {settings.kas_base_url} ({exc}). "
            "Chunk legs will be SKIPPED; only the LLM legs will run."
        )
        return False
    print(f"  [PASS] preflight - KAS healthy at {settings.kas_base_url}")
    return True


# ----------------------------------------------------------------------
# Test legs
# ----------------------------------------------------------------------


async def run_llm_legs(llm: LLMService, results: Results) -> None:
    """The four structured analyses on a short (direct-path) transcript."""
    transcript = BASE_TRANSCRIPT.strip()

    print("\n-- LLM leg: summary --")
    summary = await summarization_service.summarize(transcript, llm)
    print(summary.model_dump_json(indent=2))
    if summary.summary.strip():
        results.passed("llm:summary")
    else:
        results.failed("llm:summary", "empty summary text")

    print("\n-- LLM leg: action items --")
    actions = await action_service.extract_action_items(transcript, llm)
    print(actions.model_dump_json(indent=2))
    if actions.action_items:
        results.passed(f"llm:actions ({len(actions.action_items)} items)")
    else:
        results.failed("llm:actions", "no action items extracted")

    print("\n-- LLM leg: decisions --")
    decisions = await decision_service.extract_decisions(transcript, llm)
    print(decisions.model_dump_json(indent=2))
    if decisions.decisions:
        results.passed(f"llm:decisions ({len(decisions.decisions)} items)")
    else:
        results.failed("llm:decisions", "no decisions extracted")

    print("\n-- LLM leg: topics --")
    topics = await topic_service.extract_topics(transcript, llm)
    print(topics.model_dump_json(indent=2))
    if topics.topics:
        results.passed(f"llm:topics ({len(topics.topics)} items)")
    else:
        results.failed("llm:topics", "no topics extracted")


async def run_chunk_legs(kas: KASClient, results: Results) -> None:
    """Real /chunk call + the >20k threshold gate (no LLM maps)."""
    print("\n-- Chunk leg: direct /chunk on a two-topic sample --")
    try:
        chunks = await kas.chunk("smoke-chunk-sample", CHUNK_SAMPLE)
    except Exception as exc:
        results.failed("chunk:/chunk", f"{type(exc).__name__}: {exc}")
        return

    sizes = [len(chunk) for chunk in chunks]
    print(f"  chunks: {len(chunks)}  sizes: {sizes}")
    for chunk in chunks[:2]:
        preview = chunk[:120].replace("\n", " ")
        print(f"  first chunks preview: {preview}...")

    if len(chunks) >= 2 and all(sizes):
        results.passed(f"chunk:/chunk ({len(chunks)} chunks)")
    elif len(chunks) < 2:
        results.failed("chunk:/chunk", f"expected >= 2 chunks, got {len(chunks)}")
    else:
        results.failed("chunk:/chunk", "at least one chunk was empty")

    print("\n-- Chunk leg: >20k gate via chunk_analysis_input --")
    threshold = get_settings().chunk_threshold_chars
    long_transcript = build_large_transcript(threshold + 1)
    print(f"  transcript chars: {len(long_transcript):,}")
    try:
        pieces = await chunk_analysis_input(
            long_transcript, kas, meeting_id="smoke-gate-check"
        )
    except Exception as exc:
        results.failed("chunk:gate", f"{type(exc).__name__}: {exc}")
        return

    print(f"  pieces returned: {len(pieces)}  sizes: {[len(p) for p in pieces]}")
    if len(pieces) >= 2:
        results.passed(f"chunk:gate ({len(pieces)} pieces)")
    else:
        results.failed(
            "chunk:gate",
            "transcript over the threshold was not split (expected >= 2 pieces)",
        )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


async def main() -> int:
    settings = get_settings()
    results = Results()

    print("=" * 60)
    print("MODULE3 SMOKE TEST")
    print("=" * 60)

    print("\n[preflight]")
    if not check_ollama(settings):
        print("\nSmoke FAILED - fix preflight before anything else.")
        return 1
    kas_available = check_kas(settings)

    llm = LLMService(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
    )
    kas: KASClient | None = None
    if kas_available:
        kas = KASClient(
            base_url=settings.kas_base_url,
            timeout_seconds=settings.kas_timeout_seconds,
            max_retries=settings.kas_max_retries,
        )

    try:
        await run_llm_legs(llm, results)
        if kas is not None:
            await run_chunk_legs(kas, results)
        else:
            results.skipped("chunk:/chunk", "KAS not reachable")
            results.skipped("chunk:gate", "KAS not reachable")
    finally:
        await llm.close()
        if kas is not None:
            await kas.close()

    print("\n" + "=" * 60)
    if results.failures:
        print(f"SMOKE FAILED ({len(results.failures)} leg(s)): {results.failures}")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
