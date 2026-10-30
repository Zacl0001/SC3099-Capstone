#!/usr/bin/env python
r"""Evaluate summary, action-item, decision and RAG quality end to end.

Runs each transcript in ``evaluation/meetings`` through module2 (which proxies
module3 for analysis and module4/KAS for retrieval), compares the output with
``evaluation/expected/<name>.json``, and prints precision/recall style scores.

Usage (with the stack running - see docs/testing-guide.md), from the
meeting-intelligence-assistant folder:

    ..\.venv\Scripts\python.exe evaluation\evaluate.py
    ..\.venv\Scripts\python.exe evaluation\evaluate.py --threshold 0.6
    ..\.venv\Scripts\python.exe evaluation\evaluate.py --delete

Expected file format:

    {
      "summary_keywords": ["19 December", "Android 14"],
      "decisions": ["the beta goes out on 19 December"],
      "action_items": [{"task": "fix the crash", "assignee": "Daniel"}],
      "qa": [{
        "question": "When does the beta ship?",
        "expected_terms": ["19 December"],
        "citation_times": ["00:01:01"]
      }]
    }

Matching is keyword based: tasks/decisions are matched when enough of the
expected words appear in the generated item, so a paraphrase still scores.
Case, ordinals and plurals are normalised, and one generated decision row may
cover several expected decisions (recaps often bundle them).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_MEETINGS = EVAL_DIR / "meetings"
DEFAULT_EXPECTED = EVAL_DIR / "expected"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "then", "there", "this", "to", "was", "were", "will", "with", "we", "our",
    "i", "you", "they", "he", "she", "not", "no", "so", "but", "if", "do",
}


# ---------------------------------------------------------------------------
# Text matching
# ---------------------------------------------------------------------------


ORDINAL = re.compile(r"^(\d+)(st|nd|rd|th)$")


def stem(word: str) -> str:
    """Very light stemming so '19th' == '19' and 'weeks' == 'week'."""
    match = ORDINAL.match(word)
    if match:
        return match.group(1)
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {stem(word) for word in words if word not in STOPWORDS}


def similarity(expected: str, candidate: str) -> float:
    """Share of the expected words that appear in the candidate (0..1)."""
    wanted = tokens(expected)
    if not wanted:
        return 1.0
    return len(wanted & tokens(candidate)) / len(wanted)


def contains_term(text: str, term: str) -> bool:
    """True when every meaningful word of the term appears in the text.

    Order and formatting don't matter, so "19 December" also matches
    "December 19th" and "two weeks" matches "two-week".
    """
    wanted = tokens(term)
    return bool(wanted) and wanted <= tokens(text)


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class EvaluationError(RuntimeError):
    pass


class API:
    def __init__(self, base_url: str, email: str, password: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self.token: str | None = None

    def close(self) -> None:
        self.client.close()

    # -- auth -------------------------------------------------------------

    def login(self) -> None:
        self.client.post(
            "/api/auth/register",
            json={"email": self.email, "password": self.password},
        )
        response = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        self._check(response, "login")
        token = response.json().get("access_token")
        if not token:
            raise EvaluationError("login did not return an access_token")
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    # -- pipeline ---------------------------------------------------------

    def upload(self, transcript: Path, title: str) -> int:
        response = self.client.post(
            "/api/meetings/upload",
            headers=self.headers,
            data={"title": title},
            files={"file": (transcript.name, transcript.read_bytes(), "text/plain")},
        )
        self._check(response, f"upload {transcript.name}")
        return int(response.json()["id"])

    def process(self, meeting_id: int) -> list[dict]:
        response = self.client.post(
            f"/api/meetings/{meeting_id}/transcript/process",
            headers=self.headers,
        )
        self._check(response, f"process meeting {meeting_id}")
        return response.json()["sections"]

    def transcript(self, meeting_id: int) -> list[dict]:
        response = self.client.get(
            f"/api/meetings/{meeting_id}/transcript", headers=self.headers
        )
        self._check(response, f"transcript {meeting_id}")
        return response.json()["sections"]

    def index(self, meeting_id: int) -> None:
        response = self.client.post(
            f"/api/meetings/{meeting_id}/index", headers=self.headers
        )
        self._check(response, f"index meeting {meeting_id}")

    def summary(self, meeting_id: int) -> dict:
        return self._get_json(f"/api/meetings/{meeting_id}/summary")

    def action_items(self, meeting_id: int) -> list[dict]:
        return self._get_json(f"/api/meetings/{meeting_id}/action-items").get(
            "action_items", []
        )

    def decisions(self, meeting_id: int) -> list[dict]:
        return self._get_json(f"/api/meetings/{meeting_id}/decisions").get(
            "decisions", []
        )

    def chat(self, meeting_id: int, question: str) -> dict:
        response = self.client.post(
            f"/api/meetings/{meeting_id}/chat",
            headers=self.headers,
            json={"question": question},
        )
        self._check(response, f"chat {meeting_id}")
        return response.json()

    def delete_meeting(self, meeting_id: int) -> None:
        response = self.client.delete(
            f"/api/meetings/{meeting_id}", headers=self.headers
        )
        if response.status_code >= 400:
            print(f"  warning: could not delete meeting {meeting_id}")


    def _get_json(self, path: str) -> dict:
        response = self.client.get(path, headers=self.headers)
        self._check(response, path)
        return response.json()

    @staticmethod
    def _check(response: httpx.Response, what: str) -> None:
        if response.status_code >= 400:
            raise EvaluationError(
                f"{what} failed ({response.status_code}): {response.text[:300]}"
            )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class Counts:
    """How many expected items were covered and how many generated items were used.

    Kept separate because one generated item may legitimately cover several
    expected items (e.g. a recap sentence listing three decisions).
    """

    expected_matched: int = 0
    generated_matched: int = 0
    generated: int = 0
    expected: int = 0

    @property
    def precision(self) -> float:
        return self.generated_matched / self.generated if self.generated else 0.0

    @property
    def recall(self) -> float:
        return self.expected_matched / self.expected if self.expected else 0.0

    @property
    def f1(self) -> float:
        if not (self.precision + self.recall):
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    def add(self, other: "Counts") -> None:
        self.expected_matched += other.expected_matched
        self.generated_matched += other.generated_matched
        self.generated += other.generated
        self.expected += other.expected


@dataclass
class RagCounts:
    questions: int = 0
    grounded: int = 0
    relevant: int = 0
    citations: int = 0
    valid_citations: int = 0


@dataclass
class MeetingScore:
    name: str
    meeting_id: int
    summary_hits: int = 0
    summary_total: int = 0
    actions: Counts = field(default_factory=Counts)
    decisions: Counts = field(default_factory=Counts)
    rag: RagCounts = field(default_factory=RagCounts)
    missing_actions: list[str] = field(default_factory=list)
    missing_decisions: list[str] = field(default_factory=list)


def item_text(item: dict | str, field_name: str) -> str:
    """Expected items may be a plain string or a dict with the field."""
    if isinstance(item, str):
        return item
    return str(item.get(field_name, ""))


def score_list(
    expected_items: list[dict | str],
    generated_items: list[dict],
    field_name: str,
    *,
    allow_merged: bool = False,
) -> tuple[Counts, list[str]]:
    """Greedy keyword match with a 0.5 word-overlap threshold.

    With ``allow_merged`` a single generated item may satisfy several expected
    items. That is the right model for decisions, where a recap sentence often
    bundles three decisions into one row. Action items stay one-to-one so a
    vague catch-all row cannot inflate the score.
    """
    counts = Counts(generated=len(generated_items), expected=len(expected_items))
    matched: set[int] = set()
    missing: list[str] = []

    for expected in expected_items:
        expected_text = item_text(expected, field_name)
        assignee = expected.get("assignee") if isinstance(expected, dict) else None

        best_score = 0.0
        best_index: int | None = None
        for index, item in enumerate(generated_items):
            if not allow_merged and index in matched:
                continue
            score = similarity(expected_text, item_text(item, field_name))
            if assignee and item.get("assignee"):
                if similarity(assignee, item["assignee"]) < 0.5:
                    score *= 0.5
            if score > best_score:
                best_score, best_index = score, index

        if best_index is not None and best_score >= 0.5:
            counts.expected_matched += 1
            matched.add(best_index)
        else:
            missing.append(expected_text)

    counts.generated_matched = len(matched)
    return counts, missing


def evaluate_meeting(
    api: API,
    transcript_path: Path,
    expected: dict,
    title: str,
    delete: bool,
) -> MeetingScore:
    meeting_id = api.upload(transcript_path, title)
    try:
        sections = api.process(meeting_id)
        try:
            api.index(meeting_id)
        except EvaluationError as exc:
            print(f"  warning: indexing failed: {exc}")

        summary = api.summary(meeting_id)
        actions = api.action_items(meeting_id)
        decisions = api.decisions(meeting_id)

        score = MeetingScore(name=transcript_path.stem, meeting_id=meeting_id)

        summary_text = " ".join(
            [summary.get("summary", ""), *summary.get("key_points", [])]
        )
        keywords = expected.get("summary_keywords", [])
        score.summary_total = len(keywords)
        score.summary_hits = sum(contains_term(summary_text, kw) for kw in keywords)

        score.actions, score.missing_actions = score_list(
            expected.get("action_items", []), actions, "task"
        )
        score.decisions, score.missing_decisions = score_list(
            expected.get("decisions", []), decisions, "decision", allow_merged=True
        )

        section_ids = {section.get("section_id") for section in sections}
        for qa in expected.get("qa", []):
            answer = api.chat(meeting_id, qa["question"])
            score.rag.questions += 1

            text = answer.get("answer", "")
            terms = qa.get("expected_terms", [])
            if terms and any(contains_term(text, term) for term in terms):
                score.rag.grounded += 1

            citations = answer.get("citations", [])
            times = set(qa.get("citation_times", []))
            relevant = any(
                any(contains_term(citation.get("text", ""), term) for term in terms)
                or citation.get("start_time") in times
                for citation in citations
            )
            if relevant:
                score.rag.relevant += 1

            score.rag.citations += len(citations)
            score.rag.valid_citations += sum(
                citation.get("chunk_id") in section_ids for citation in citations
            )

        return score
    finally:
        if delete:
            api.delete_meeting(meeting_id)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def print_meeting(score: MeetingScore) -> None:
    print(f"\n--- {score.name} (meeting {score.meeting_id}) ---")
    print(
        f"  Summary keywords: {score.summary_hits}/{score.summary_total}"
        + (
            f" ({pct(score.summary_hits / score.summary_total)})"
            if score.summary_total
            else ""
        )
    )
    print(
        "  Action items:     "
        f"precision {pct(score.actions.precision)}  "
        f"recall {pct(score.actions.recall)}  "
        f"F1 {pct(score.actions.f1)}"
    )
    print(
        "  Decisions:        "
        f"precision {pct(score.decisions.precision)}  "
        f"recall {pct(score.decisions.recall)}  "
        f"F1 {pct(score.decisions.f1)}"
    )
    rag = score.rag
    if rag.questions:
        print(
            f"  RAG grounded:     {rag.grounded}/{rag.questions}  "
            f"relevant retrieval: {rag.relevant}/{rag.questions}  "
            f"valid citations: {rag.valid_citations}/{rag.citations}"
        )
    for task in score.missing_actions:
        print(f"    missed action: {task}")
    for decision in score.missing_decisions:
        print(f"    missed decision: {decision}")


def print_report(scores: list[MeetingScore]) -> dict[str, float]:
    summary_hits = sum(score.summary_hits for score in scores)
    summary_total = sum(score.summary_total for score in scores)

    actions = Counts()
    decisions = Counts()
    rag = RagCounts()
    for score in scores:
        actions.add(score.actions)
        decisions.add(score.decisions)
        rag.questions += score.rag.questions
        rag.grounded += score.rag.grounded
        rag.relevant += score.rag.relevant
        rag.citations += score.rag.citations
        rag.valid_citations += score.rag.valid_citations

    print("\n" + "=" * 29)
    print("Meeting Intelligence Evaluation")
    print("=" * 29)

    summary_rate = summary_hits / summary_total if summary_total else 0.0
    action_f1 = actions.f1
    decision_f1 = decisions.f1
    grounded = rag.grounded / rag.questions if rag.questions else 0.0
    relevance = rag.relevant / rag.questions if rag.questions else 0.0
    citation_accuracy = rag.valid_citations / rag.citations if rag.citations else 0.0

    print("\nSummary")
    print("-------")
    print(f"Correctness: {pct(summary_rate)}")

    print("\nAction Items")
    print("------------")
    print(f"Precision: {pct(actions.precision)}")
    print(f"Recall:    {pct(actions.recall)}")
    print(f"F1:        {pct(actions.f1)}")

    print("\nDecisions")
    print("---------")
    print(f"Precision: {pct(decisions.precision)}")
    print(f"Recall:    {pct(decisions.recall)}")
    print(f"F1:        {pct(decisions.f1)}")

    print("\nRAG")
    print("---")
    print(f"Retrieval relevance: {pct(relevance)}")
    print(f"Citation accuracy:   {pct(citation_accuracy)}")
    print(f"Grounded answers:    {pct(grounded)}")

    return {
        "summary": summary_rate,
        "action_f1": action_f1,
        "decision_f1": decision_f1,
        "grounded": grounded,
        "relevance": relevance,
        "citation_accuracy": citation_accuracy,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the AI pipeline end to end.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="tester@example.com")
    parser.add_argument("--password", default="password123")
    parser.add_argument("--meetings-dir", type=Path, default=DEFAULT_MEETINGS)
    parser.add_argument("--expected-dir", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="fail if the average of the main metrics is below this (0..1). Default: report only.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="per-request timeout in seconds (LLM calls are slow on CPU).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="delete the evaluation meetings afterwards (default: keep them).",
    )
    args = parser.parse_args()

    expected_files = sorted(args.expected_dir.glob("*.json"))
    if not expected_files:
        print(f"No expected outputs found in {args.expected_dir}")
        return 1

    api = API(args.base_url, args.email, args.password, args.timeout)
    try:
        api.login()
    except (EvaluationError, httpx.HTTPError) as exc:
        print(f"Cannot reach the backend at {args.base_url}: {exc}")
        print("Start the stack with .\\scripts\\start-all.ps1 first.")
        return 1

    print(f"Backend: {args.base_url}")
    scores: list[MeetingScore] = []
    try:
        for expected_file in expected_files:
            transcript = args.meetings_dir / f"{expected_file.stem}.txt"
            if not transcript.exists():
                print(f"Skipping {expected_file.stem}: {transcript.name} not found")
                continue

            expected = json.loads(expected_file.read_text(encoding="utf-8"))
            print(f"\nRunning {transcript.name} ...")
            try:
                score = evaluate_meeting(
                    api,
                    transcript,
                    expected,
                    title=f"Evaluation {expected_file.stem}",
                    delete=args.delete,
                )
            except (EvaluationError, httpx.HTTPError) as exc:
                print(f"  FAILED: {exc}")
                return 1
            scores.append(score)
            print_meeting(score)

        if not scores:
            print("Nothing was evaluated.")
            return 1

        metrics = print_report(scores)
        if args.threshold > 0:
            main_metrics = [
                metrics["summary"],
                metrics["action_f1"],
                metrics["decision_f1"],
                metrics["grounded"],
            ]
            average = sum(main_metrics) / len(main_metrics)
            verdict = "PASS" if average >= args.threshold else "FAIL"
            print(
                f"\nOverall: {verdict} (average {pct(average)}, "
                f"threshold {pct(args.threshold)})"
            )
            if verdict == "FAIL":
                return 2

        if args.delete:
            print("\nEvaluation meetings were deleted.")
        else:
            print("\nMeetings kept; open http://localhost:3000/meetings/<id> to inspect them.")
        return 0
    finally:
        api.close()


if __name__ == "__main__":
    sys.exit(main())
