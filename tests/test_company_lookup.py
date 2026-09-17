import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from job_hunter.company_lookup import CompanyLookupError, lookup_company_site, resolve_grounding_url
from job_hunter.matching import MatchingConfig


CAREERS = "https://jobs.deloitte.com/sea/go/Malaysia/"
OFFICIAL = "https://www.deloitte.com/my/en/careers.html"
PAYLOAD = {
    "company": "Deloitte", "official_url": OFFICIAL, "careers_url": CAREERS,
    "region": "Malaysia", "region_evidence_url": OFFICIAL,
    "region_evidence_quote": "Explore careers in Malaysia",
}


def response(payload=PAYLOAD, *, grounding=True):
    metadata = SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri=url)) for url in (OFFICIAL, CAREERS)],
        web_search_queries=["Deloitte Malaysia careers"],
        search_entry_point=SimpleNamespace(rendered_content="<div>Google Search</div>"),
    ) if grounding else None
    return SimpleNamespace(text=json.dumps(payload), candidates=[SimpleNamespace(grounding_metadata=metadata)])


class CompanyLookupTest(unittest.TestCase):
    def lookup(self, reply=None, pages=None):
        client = SimpleNamespace(model="gemini-test", generate=lambda *args, **kwargs: reply or response())
        def fetch(url, allowed_domains=()):
            return (pages or {
                OFFICIAL: f'<title>Deloitte Careers</title>Explore careers in Malaysia <a href="{CAREERS}">Search jobs</a>',
                CAREERS: "<title>Deloitte Careers</title>Jobs in Malaysia",
            })[url]
        return lookup_company_site("deloitte", "Malaysia", MatchingConfig(api_key="test"),
                                   client=client, fetcher=fetch, citation_resolver=lambda url: url)

    def test_official_regional_careers_are_verified_from_grounded_sources(self):
        result = self.lookup()
        self.assertEqual(result.hostname, "jobs.deloitte.com")
        self.assertEqual(result.careers_url, CAREERS)
        self.assertEqual(result.region, "Malaysia")
        self.assertEqual(result.model, "gemini-test")

    def test_ungrounded_domain_guess_is_rejected(self):
        with self.assertRaisesRegex(CompanyLookupError, "grounded"):
            self.lookup(response(grounding=False))

    def test_wrong_region_is_rejected(self):
        with self.assertRaisesRegex(CompanyLookupError, "region"):
            self.lookup(response({**PAYLOAD, "region": "United States"}))

    def test_regional_quote_must_be_in_official_page(self):
        with self.assertRaisesRegex(CompanyLookupError, "regional"):
            self.lookup(pages={OFFICIAL: f'Deloitte Careers in USA <a href="{CAREERS}">Jobs</a>', CAREERS: "Deloitte Careers"})

    def test_careers_link_must_be_confirmed_on_official_page(self):
        with self.assertRaisesRegex(CompanyLookupError, "official"):
            self.lookup(response({**PAYLOAD, "careers_url": "https://jobs.deloitte.com/unlinked"}),
                        pages={OFFICIAL: "Deloitte Careers Explore careers in Malaysia",
                               "https://jobs.deloitte.com/unlinked": "Deloitte Careers Malaysia"})

    def test_private_candidate_url_is_rejected_before_fetch(self):
        with self.assertRaises(CompanyLookupError):
            self.lookup(response({**PAYLOAD, "careers_url": "https://127.0.0.1/jobs"}))

    def test_name_lookup_sends_only_company_and_region(self):
        recorded = []
        def generate(payload, prompt, **kwargs):
            recorded.append(payload)
            return response()
        with patch("job_hunter.company_lookup.GoogleGeminiClient") as factory:
            factory.return_value = SimpleNamespace(generate=generate, model="test-model")
            result = lookup_company_site("Deloitte", "Malaysia", MatchingConfig(api_key="test"),
                                         fetcher=lambda *args, **kwargs: f'Deloitte Careers Explore careers in Malaysia <a href="{CAREERS}">Jobs</a>',
                                         citation_resolver=lambda url: url)
        self.assertEqual(recorded, [{"company": "Deloitte", "region": "Malaysia"}])
        self.assertEqual(result.hostname, "jobs.deloitte.com")

    def test_missing_key_has_actionable_error(self):
        with self.assertRaisesRegex(CompanyLookupError, "GEMINI_API_KEY"):
            lookup_company_site("Deloitte", "Malaysia", MatchingConfig())

    def test_grounded_aggregator_cannot_impersonate_official_company(self):
        url = "https://careers-aggregator.example/jobs"
        payload = {**PAYLOAD, "official_url": url, "careers_url": url, "region_evidence_url": url}
        reply = response(payload)
        reply.candidates[0].grounding_metadata.grounding_chunks = [SimpleNamespace(web=SimpleNamespace(uri=url))]
        with self.assertRaisesRegex(CompanyLookupError, "corporate"):
            self.lookup(reply, pages={url: "Deloitte Careers Explore careers in Malaysia"})

    def test_shared_ats_query_scope_is_rejected(self):
        with self.assertRaises(CompanyLookupError):
            self.lookup(response({**PAYLOAD, "careers_url": "https://ats.example/jobs?company=Deloitte&location=Malaysia"}))

    def test_corporate_scope_does_not_exclude_sibling_job_paths(self):
        self.assertEqual(self.lookup().site_filter, "site:jobs.deloitte.com")

    def test_destination_must_confirm_requested_region(self):
        with self.assertRaisesRegex(CompanyLookupError, "destination.*region"):
            self.lookup(pages={OFFICIAL: f'Deloitte Careers Explore careers in Malaysia <a href="{CAREERS}">Jobs</a>',
                               CAREERS: "Deloitte Careers Jobs in United States"})

    def test_relevant_seventh_citation_is_prioritized(self):
        reply = response()
        metadata = reply.candidates[0].grounding_metadata
        metadata.grounding_chunks = [SimpleNamespace(web=SimpleNamespace(uri=f"https://example.org/unrelated/{i}")) for i in range(6)] + metadata.grounding_chunks
        self.assertEqual(self.lookup(reply).hostname, "jobs.deloitte.com")

    def test_differently_scoped_citation_is_not_same_evidence(self):
        reply = response()
        reply.candidates[0].grounding_metadata.grounding_chunks[0].web.uri = OFFICIAL + "?region=US"
        with self.assertRaisesRegex(CompanyLookupError, "backed"):
            self.lookup(reply)

    def test_retryable_lookup_stays_within_two_provider_calls(self):
        from job_hunter.matching import GeminiServiceError
        calls = []
        def generate(*args, **kwargs):
            calls.append(1)
            raise GeminiServiceError("temporary", "private provider detail", retryable=True)
        with self.assertRaisesRegex(CompanyLookupError, "temporarily"):
            lookup_company_site("Deloitte", "Malaysia", MatchingConfig(api_key="test"),
                client=SimpleNamespace(generate=generate), sleep=lambda _: None)
        self.assertEqual(len(calls), 2)

    def test_unrelated_malformed_links_do_not_reject_valid_careers(self):
        self.assertEqual(self.lookup(pages={
            OFFICIAL: f'Deloitte Careers Explore careers in Malaysia <a href="https://bad:port/">Bad</a><a href="{CAREERS}">Jobs</a>',
            CAREERS: "Deloitte Careers Jobs in Malaysia",
        }).hostname, "jobs.deloitte.com")

    def test_grounding_redirect_cannot_reach_private_destination(self):
        reply = SimpleNamespace(is_redirect=True, headers={"Location": "https://127.0.0.1/"}, close=lambda: None)
        with patch("job_hunter.company_lookup._hostname_resolves_public", return_value=True), patch("requests.get", return_value=reply):
            with self.assertRaises(CompanyLookupError):
                resolve_grounding_url("https://vertexaisearch.cloud.google.com/grounding-api-redirect/test")

    def test_sdk_grounded_request_uses_search_without_json_mode(self):
        from job_hunter.matching import GoogleGeminiClient
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.return_value = response()
            client = GoogleGeminiClient(MatchingConfig(api_key="test", model="gemini-3.8-flash"))
            reply = client.generate({"company": "Deloitte", "region": "Malaysia"}, "Find careers", grounded=True)
            config = factory.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertIsNotNone(reply.candidates[0].grounding_metadata)
        self.assertIsNotNone(config.tools[0].google_search)
        self.assertIsNone(config.response_json_schema)
        self.assertIsNone(config.response_mime_type)
