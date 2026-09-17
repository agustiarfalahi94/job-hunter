import unittest
from dataclasses import replace
from datetime import date
from unittest.mock import patch

from job_hunter.search import extract_job_metadata, SearchCriteria, build_direct_platform_queries
from job_hunter.queue_types import JobInput
from job_hunter.session_workspace import SessionWorkspace
from job_hunter.scoring import score_job
from job_hunter.app_ui import jobs_to_rows, filter_jobs


class PostingEvidenceTest(unittest.TestCase):
    def test_indeed_header_location_and_platform_apply_link(self):
        page = '<main><div data-testid="job-location">Kuala Lumpur</div><a href="https://smartapply.indeed.com/beta/indeedapply/form">Apply now</a></main>'
        metadata = extract_job_metadata(page, "https://malaysia.indeed.com/viewjob?jk=123")
        self.assertEqual(metadata.locations, ("Kuala Lumpur",))
        self.assertEqual(metadata.quick_apply, "Indeed Apply")
        self.assertFalse(metadata.posted_date)

    def test_location_does_not_use_related_jobs_or_description(self):
        page = '<main><div id="jobDescriptionText">Work with Kuala Lumpur</div></main><aside><div data-testid="job-location">Jakarta</div></aside>'
        self.assertEqual(extract_job_metadata(page, "https://malaysia.indeed.com/viewjob?jk=123").locations, ())

    def test_apply_evidence_does_not_use_description_words(self):
        page = '<main><div id="jobDescriptionText">Build an Easy Apply feature.</div></main>'
        self.assertEqual(extract_job_metadata(page, "https://www.linkedin.com/jobs/view/123").quick_apply, "")
        button = '<main><button class="jobs-apply-button">Easy Apply</button></main>'
        self.assertEqual(extract_job_metadata(button, "https://www.linkedin.com/jobs/view/123").quick_apply, "LinkedIn Easy Apply")

    def test_structured_expiry_is_not_inferred_from_posted_age(self):
        page = '<script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-09-01","validThrough":"2026-09-16"}</script>'
        metadata = extract_job_metadata(page, "https://example.com/jobs/1", today=date(2026, 9, 17))
        self.assertEqual(metadata.availability, "expired")
        self.assertIn("validThrough", metadata.availability_evidence)
        no_expiry = page.replace(',"validThrough":"2026-09-16"', '')
        self.assertEqual(extract_job_metadata(no_expiry, "https://example.com/jobs/1").availability, "unknown")

    def test_linkedin_easy_apply_request_parameter_is_exclusive(self):
        criteria = SearchCriteria(("Analyst",), (), "Kuala Lumpur", ("LinkedIn",), application_filters=("LinkedIn Easy Apply",))
        self.assertIn("f_AL=true", build_direct_platform_queries(criteria)[0].url)

    def test_user_date_and_expiry_edits_are_labelled_and_persist(self):
        workspace = SessionWorkspace()
        job_id = workspace.add_job(JobInput("Analyst", location="Kuala Lumpur"), {}).job_id
        workspace.update_posting_evidence(job_id, "2026-09-17", "expired")
        job = workspace.list_jobs()[0]
        self.assertEqual(job.posted_date, "2026-09-17")
        self.assertFalse(job.posted_date_verified)
        self.assertIn("User", job.posted_date_source)
        self.assertEqual(job.availability, "expired")
        self.assertEqual(filter_jobs([job], "all"), [])
        self.assertEqual(len(filter_jobs([job], "all", application_view="all")), 1)
        self.assertNotIn("Alternate sources", jobs_to_rows([job])[0])
        self.assertIn("Expiry", jobs_to_rows([job])[0])
        for invalid in ("tomorrow", "2026-99-99", "2999-01-01"):
            with self.assertRaises(ValueError):
                workspace.update_posting_evidence(job_id, invalid, "unknown")

    def test_unknown_location_column_is_hidden_only_if_all_rows_unknown(self):
        workspace = SessionWorkspace()
        workspace.add_job(JobInput("Analyst"), {})
        self.assertNotIn("Location", jobs_to_rows(workspace.list_jobs())[0])
        workspace.add_job(JobInput("Engineer", location="Jakarta"), {})
        self.assertIn("Location", jobs_to_rows(workspace.list_jobs())[0])

    def test_known_job_positive_and_negative_criteria(self):
        job = {"title": "Senior Data Analyst (Analytics & Business Intelligence)", "location": "Kuala Lumpur",
               "description": "Develop reports and dashboards. Strong proficiency in SQL and Power BI. Data pipelines and stakeholder management."}
        positive = {"target_roles": ["Data Analyst"], "primary_keywords": ["Power BI"],
                    "target_locations": ["Kuala Lumpur"], "bonus_keywords": ["SQL"], "remote_policy": []}
        self.assertEqual(score_job(job, positive).decision, "shortlist")
        self.assertEqual(score_job(job, {**positive, "hard_skip_keywords": ["power bi"]}).decision, "skip")
        self.assertLess(score_job(job, {"target_roles": ["Accountant"], "primary_keywords": ["SAP"],
                                      "target_locations": ["Berlin"]}).score, 50)

    def test_indeed_result_title_location_is_evidence_not_company(self):
        import json
        from job_hunter.search import parse_serpapi_results
        result = {"organic_results": [{"title": "Senior Data Analyst - Kuala Lumpur - Indeed.com",
                  "link": "https://malaysia.indeed.com/viewjob?jk=123"}]}
        job = parse_serpapi_results(json.dumps(result), "Indeed", "Jakarta", 50)[0]
        self.assertEqual(job.location, "Kuala Lumpur")
        self.assertEqual(job.company, "")

    def test_apply_job_id_cannot_belong_to_related_vacancy(self):
        page = '<main><button data-indeed-apply-jobid="456">Indeed Apply</button></main>'
        self.assertEqual(extract_job_metadata(page, "https://malaysia.indeed.com/viewjob?jk=123").quick_apply, "")
        parent = '<main><div data-job-id="456"><button>Easy Apply</button></div></main>'
        self.assertEqual(extract_job_metadata(parent, "https://www.linkedin.com/jobs/view/123").quick_apply, "")

    def test_structured_state_cannot_be_treated_as_city(self):
        import json
        from job_hunter.locations import location_matches
        for address, expected in (({"addressLocality": "Buffalo", "addressRegion": "New York", "addressCountry": "US"}, False),
                                  ({"addressRegion": "New York", "addressCountry": "US"}, None)):
            page = '<script type="application/ld+json">' + json.dumps({"@type": "JobPosting", "jobLocation": {"address": address}}) + '</script>'
            metadata = extract_job_metadata(page, "https://example.com/jobs/1")
            place, locality = metadata.locality_locations[0]
            target = "New York" if "addressLocality" in address else "Buffalo"
            self.assertIs(location_matches(place, (target,), locality=locality), expected)

    def test_associated_structured_record_without_location_uses_header(self):
        page = '<script type="application/ld+json">{"@type":"JobPosting","url":"https://www.linkedin.com/jobs/view/123","description":"SQL"}</script><main><span class="topcard__flavor--bullet">Jakarta</span></main>'
        self.assertEqual(extract_job_metadata(page, "https://www.linkedin.com/jobs/view/123").locations, ("Jakarta",))

    def test_indeed_tracking_parameters_do_not_detach_vacancy_metadata(self):
        page = '<script type="application/ld+json">{"@type":"JobPosting","url":"https://malaysia.indeed.com/viewjob?jk=123","jobLocation":{"address":{"addressLocality":"Kuala Lumpur","addressCountry":"MY"}}}</script>'
        source = "https://malaysia.indeed.com/viewjob?jk=123&from=mobRdr&tk=tracking"
        self.assertEqual(extract_job_metadata(page, source).locations, ("Kuala Lumpur, MY",))

    def test_legacy_search_rejects_city_match_in_state_field(self):
        from unittest.mock import MagicMock
        from job_hunter.search import run_public_search
        queue = MagicMock()
        cards = '<div class="base-search-card"><a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123">Analyst</a><h3 class="base-search-card__title">Analyst</h3></div>'
        page = '<script type="application/ld+json">{"@type":"JobPosting","jobLocation":{"address":{"addressLocality":"Buffalo","addressRegion":"New York","addressCountry":"US"}}}</script>'
        run_public_search(SearchCriteria(("Analyst",), (), "New York", ("LinkedIn",), posted_within_days=None), {}, queue,
                          fetcher=lambda url: cards if "/jobs/search" in url else page)
        queue.add_job.assert_not_called()

    def test_duplicate_does_not_verify_a_different_user_edited_date(self):
        workspace = SessionWorkspace()
        job = JobInput("Analyst", source_url="https://malaysia.indeed.com/viewjob?jk=123", posted_date="2026-09-01", posted_date_verified=True, platform="Indeed")
        job_id = workspace.add_job(job, {}).job_id
        workspace.update_posting_evidence(job_id, "2026-09-02", "unknown")
        workspace.add_job(job, {})
        record = workspace.list_jobs()[0]
        self.assertEqual(record.posted_date, "2026-09-02")
        self.assertFalse(record.posted_date_verified)
        self.assertIn("User", record.posted_date_source)
