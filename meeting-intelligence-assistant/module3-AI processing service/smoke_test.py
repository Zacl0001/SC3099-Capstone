"""Live smoke test: exercises every endpoint against the real Ollama model.

Run with:  python smoke_test.py
Requires the LLM model to be pulled and Ollama to be running.
"""

import asyncio

from app.core.config import get_settings
from app.services import action_service, decision_service, summarization_service, topic_service
from app.services.llm_service import LLMService

TRANSCRIPT = """
Alice: Let's talk about the Q3 release timeline.
Bob: We should target October 1st.
Alice: Agreed, October 1st works. Carol, can you prepare the release notes?
Carol: Sure, I'll have them done by Friday.
Alice: We've decided to drop the mobile app feature from this release.
Bob: OK, mobile app goes to Q4.
Alice: Let's move on to the budget.
Carol: The budget is approved at 50k.
"""


async def main() -> None:
    settings = get_settings()
    llm = LLMService(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
    )
    try:
        summary = await summarization_service.summarize(TRANSCRIPT, llm)
        print("== SUMMARY ==")
        print(summary.model_dump_json(indent=2))

        actions = await action_service.extract_action_items(TRANSCRIPT, llm)
        print("\n== ACTION ITEMS ==")
        print(actions.model_dump_json(indent=2))

        decisions = await decision_service.extract_decisions(TRANSCRIPT, llm)
        print("\n== DECISIONS ==")
        print(decisions.model_dump_json(indent=2))

        topics = await topic_service.extract_topics(TRANSCRIPT, llm)
        print("\n== TOPICS ==")
        print(topics.model_dump_json(indent=2))
    finally:
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())