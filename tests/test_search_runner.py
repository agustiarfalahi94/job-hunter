import threading
import time
import unittest

from job_hunter.matching import MatchContext, MatchResult, MatchingConfig
from job_hunter.search import SearchCriteria
from job_hunter.search_runner import SearchRequest, SearchRunController
from job_hunter.session_workspace import SessionWorkspace


SEARCH_HTML = """
<html><body>
  {cards}
</body></html>
"""
CARD = """
<div class="base-search-card">
  <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/{job_id}">BI Analyst</a>
  <h3 class="base-search-card__title">BI Analyst {job_id}</h3>
  <h4 class="base-search-card__subtitle">Company {job_id}</h4>
  <span class="job-search-card__location">Kuala Lumpur</span>
</div>
"""


def _request() -> SearchRequest:
    return SearchRequest(
        criteria=SearchCriteria(
            title_terms=("BI Analyst",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            posted_within_days=None,
        ),
        match_context=MatchContext(
            mode="criteria",
            criteria={
                "target_roles": ["BI Analyst"],
                "primary_keywords": ["Power BI"],
                "minimum_score_to_apply": 90,
            },
        ),
        matching_config=MatchingConfig(api_key="test-key"),
    )


def _score(job, context, config, cache, *, cancel):
    del job, context, config, cache, cancel
    return MatchResult(
        score=92,
        decision="shortlist",
        reasons=("Relevant role",),
        remarks=(),
        engine="Gemini",
        model="test-model",
        limited=False,
    )


class SearchRunnerTest(unittest.TestCase):
    def test_cancel_stops_new_page_fetches_and_preserves_completed_results(self):
        first_completed = threading.Event()
        release_second = threading.Event()
        lock = threading.Lock()
        page_calls = 0

        def discovery_fetcher(url: str) -> str:
            del url
            return SEARCH_HTML.format(cards="".join(CARD.format(job_id=i) for i in range(10)))

        def page_fetcher(url: str) -> str:
            nonlocal page_calls
            with lock:
                page_calls += 1
                call = page_calls
            if call == 2:
                release_second.wait(1)
            return '<main class="description">Power BI dashboards and reporting.</main>'

        def scorer(*args, **kwargs):
            result = _score(*args, **kwargs)
            first_completed.set()
            time.sleep(0.05)
            return result

        controller = SearchRunController(
            discovery_fetcher=discovery_fetcher,
            page_fetcher=page_fetcher,
            scorer=scorer,
            max_workers=2,
        )
        run_id = controller.start(_request())
        self.assertTrue(first_completed.wait(1))
        time.sleep(0.02)
        controller.cancel()
        release_second.set()
        controller.wait(timeout=2)
        events, matches = controller.drain()
        snapshot = controller.snapshot()

        self.assertEqual(snapshot.run_id, run_id)
        self.assertEqual(snapshot.state, "cancelled")
        self.assertGreaterEqual(len(matches), 1)
        self.assertLess(page_calls, snapshot.discovered)
        self.assertTrue(any(event.stage == "cancelled" for event in events))

    def test_stale_run_results_are_rejected_by_session_workspace(self):
        controller = SearchRunController(
            discovery_fetcher=lambda url: SEARCH_HTML.format(cards=CARD.format(job_id=1)),
            page_fetcher=lambda url: '<main class="description">Power BI reporting role.</main>',
            scorer=_score,
        )
        workspace = SessionWorkspace()

        first_run = controller.start(_request())
        workspace.activate_run(first_run)
        controller.wait(timeout=2)
        _, first_matches = controller.drain()

        second_run = controller.start(_request())
        workspace.activate_run(second_run)
        self.assertFalse(workspace.accept_completed(first_matches[0]))
        controller.cancel()
        controller.wait(timeout=2)

    def test_controller_caps_unique_pages_and_workers(self):
        cards = "".join(CARD.format(job_id=i) for i in range(80))
        lock = threading.Lock()
        active = 0
        peak = 0
        page_calls = 0
        score_calls = 0

        def page_fetcher(url: str) -> str:
            nonlocal active, peak, page_calls
            del url
            with lock:
                active += 1
                peak = max(peak, active)
                page_calls += 1
            time.sleep(0.002)
            with lock:
                active -= 1
            return '<main class="description">Power BI reporting and dashboard ownership.</main>'

        def scorer(*args, **kwargs):
            nonlocal score_calls
            with lock:
                score_calls += 1
            return _score(*args, **kwargs)

        controller = SearchRunController(
            discovery_fetcher=lambda url: SEARCH_HTML.format(cards=cards),
            page_fetcher=page_fetcher,
            scorer=scorer,
            max_workers=2,
        )
        controller.start(_request())
        controller.wait(timeout=5)
        snapshot = controller.snapshot()

        self.assertEqual(snapshot.state, "completed")
        self.assertLessEqual(snapshot.discovery_requests, 12)
        self.assertLessEqual(page_calls, 50)
        self.assertLessEqual(score_calls, 50)
        self.assertLessEqual(snapshot.completed, 50)
        self.assertLessEqual(peak, 2)


if __name__ == "__main__":
    unittest.main()
