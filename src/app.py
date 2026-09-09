from __future__ import annotations

import sys
import tempfile
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from job_hunter.app_ui import (
    editable_criteria_defaults,
    filter_jobs,
    jobs_to_rows,
    provider_status_label,
    queue_column_widths,
    search_summary_to_rows,
    status_counts,
)
from job_hunter.cv_parser import detect_cv_signals, extract_cv_text
from job_hunter.cv_store import CVStore, format_size
from job_hunter.locations import city_options, fetch_malaysia_cities
from job_hunter.preferences import load_preferences
from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput
from job_hunter.runtime_config import SearchProviderConfig, load_search_provider_config
from job_hunter.search import (
    SearchCriteria,
    build_direct_platform_queries,
    build_search_queries,
    build_serpapi_queries,
    run_public_search,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "applications.db"
PREFERENCES_PATH = ROOT / "config" / "preferences.local.yaml"
CV_STORAGE_DIR = ROOT / "data" / "private" / "cv"
HERO_IMAGE_URL = "https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg?auto=compress&cs=tinysrgb&w=1600"

TARGET_TITLES = [
    "Data Analyst",
    "Data Engineer",
    "BI Developer",
    "Reporting Analyst",
    "Reporting Engineer",
    "Business Intelligence Analyst",
    "BI Analyst",
    "BI Engineer",
]
PRIMARY_KEYWORDS = ["Power BI", "SSRS", "Google BigQuery"]
SOURCES = ["LinkedIn", "JobStreet", "Indeed", "Foundit", "Company career pages"]
SAMPLE_CSV = """title,company,location,description,source_url
BI Developer,Example Analytics,Kuala Lumpur,"Build Power BI dashboards, SSRS reports, and SQL datasets.",https://example.com/jobs/bi-developer
Data Engineer,Example Bank,Kuala Lumpur,"Maintain BigQuery pipelines with Python, Airflow, Docker, and CI/CD.",https://example.com/jobs/data-engineer
Reporting Analyst,Example Retail,Kuala Lumpur,"Prepare recurring business reports in SSRS and support MSSQL data checks.",https://example.com/jobs/reporting-analyst
"""


def main() -> None:
    st.set_page_config(page_title="Job Hunter", page_icon=":material/work:", layout="wide")

    queue = JobQueue(DB_PATH)
    preferences = load_preferences(PREFERENCES_PATH)
    cv_store = CVStore(CV_STORAGE_DIR)
    provider_config = load_search_provider_config(st.secrets)

    _inject_table_styles()
    _render_header()
    workflow = _render_sidebar(queue, cv_store, provider_config, preferences)

    if workflow == "Automated search":
        tabs = st.tabs([":material/person: Profile & CV", ":material/tune: Search setup", ":material/table_chart: Job queue"])
        with tabs[0]:
            _render_profile(cv_store, preferences)
        with tabs[1]:
            _render_search_setup(queue, preferences, cv_store, provider_config)
        with tabs[2]:
            _render_queue(queue)
    else:
        tabs = st.tabs([":material/add_circle: Add job", ":material/upload_file: Import CSV", ":material/table_chart: Job queue"])
        with tabs[0]:
            _render_add_job(queue, _active_preferences(preferences))
        with tabs[1]:
            _render_import(queue, _active_preferences(preferences))
        with tabs[2]:
            _render_queue(queue)


def _render_header() -> None:
    left, right = st.columns([1.7, 1], vertical_alignment="center")
    with left:
        st.title("Job Hunter")
        st.caption("A local-first Streamlit app for scoring Kuala Lumpur data jobs against your CV-backed criteria.")
        with st.container(horizontal=True, wrap=True):
            st.badge("Automated search + scoring", icon=":material/search:", color="green")
            st.badge("Manual scoring when needed", icon=":material/edit_note:", color="blue")
            st.badge("Private CV stays local", icon=":material/lock:", color="gray")
    with right:
        st.image(HERO_IMAGE_URL)


def _inject_table_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stDataFrame"] div {
            white-space: normal;
        }
        [data-testid="stDataFrame"] [role="gridcell"] {
            align-items: start;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(
    queue: JobQueue,
    cv_store: CVStore,
    provider_config: SearchProviderConfig,
    preferences: dict[str, object],
) -> str:
    jobs = queue.list_jobs()
    counts = status_counts(jobs)
    cv_status = cv_store.status()
    defaults = _criteria_defaults(preferences)
    with st.sidebar:
        workflow = st.radio("Workflow", ["Automated search", "Manual scoring"], horizontal=False)
        st.header("Today")
        st.metric("Queued jobs", len(jobs))
        st.metric("New", counts["new"])
        st.metric("Submitted", counts["submitted"])
        st.metric("Strong target", defaults["strong_target"])
        st.caption("Automated search finds jobs from platforms. Manual scoring is for jobs you already collected.")
        if cv_status.exists:
            st.success(f"CV saved locally ({format_size(cv_status.size_bytes)}).")
        else:
            st.caption("No local CV is saved yet.")
        st.caption(provider_status_label(provider_config.has_api_search))
    return str(workflow)


def _render_profile(cv_store: CVStore, preferences: dict[str, object]) -> None:
    st.subheader("Profile & CV")
    st.write(
        "This page is where your CV belongs. The repository never commits your actual CV; uploaded files are saved only under the local private data folder."
    )
    status = cv_store.status()
    with st.container(border=True):
        if status.exists:
            st.success(f"Saved CV: `{status.path.name}` - {format_size(status.size_bytes)}")
            if st.button("Remove saved CV", icon=":material/delete:"):
                cv_store.remove()
                st.toast("Saved CV removed.")
                st.rerun()
        else:
            st.info("No CV is saved for this local app yet.")

        uploaded = st.file_uploader("Upload or replace CV", type=["pdf", "docx", "doc"])
        if uploaded is not None and st.button("Save CV locally", icon=":material/save:"):
            content = uploaded.getvalue()
            cv_store.save_file(content, uploaded.name)
            try:
                extracted_text = extract_cv_text(content, uploaded.name)
                cv_store.save_text(extracted_text)
                st.toast("CV saved and readable text extracted.")
            except Exception as exc:
                st.warning(f"CV was saved, but text extraction failed: {exc}")
            st.rerun()

    with st.container(border=True):
        st.markdown("**What the app currently knows from your CV-backed profile**")
        cv_text = cv_store.load_text()
        if cv_text:
            signals = detect_cv_signals(cv_text, preferences)
            st.success(f"Extracted CV text is available. Detected {signals.total_matches} matching profile signals.")
            _render_keyword_chips("Detected primary CV signals", list(signals.primary_matches))
            _render_keyword_chips("Detected bonus CV signals", list(signals.bonus_matches))
        else:
            st.caption("Upload your CV to extract local text signals. The scoring fallback still uses the documented public profile.")
        st.caption("Search criteria are editable on the Search setup page.")


def _render_search_setup(
    queue: JobQueue,
    preferences: dict[str, object],
    cv_store: CVStore,
    provider_config: SearchProviderConfig,
) -> None:
    st.subheader("Search setup")
    st.write(
        "Set title, description keywords, exact location, and selected platforms, then run up to 50 public search-result checks in one session."
    )
    cv_text = cv_store.load_text()
    if cv_text:
        signals = detect_cv_signals(cv_text, preferences)
        st.success(f"CV text loaded for this session. Detected {signals.total_matches} matching signals.")
    else:
        st.warning("No extracted CV text is available yet. Upload a CV on the Profile & CV page, or continue with the documented profile fallback.")

    active_preferences = _render_editable_criteria(preferences)
    criteria_defaults = _criteria_defaults(active_preferences)
    cities = _cached_malaysia_cities()
    with st.container(border=True):
        title_contains = st.multiselect(
            "Job title contains",
            criteria_defaults["target_roles"],
            default=criteria_defaults["target_roles"][:4],
            accept_new_options=True,
        )
        description_contains = st.multiselect(
            "Job description contains at least one primary strength",
            criteria_defaults["primary_keywords"],
            default=criteria_defaults["primary_keywords"],
            accept_new_options=True,
        )
        location_options = _location_options(cities)
        location = st.selectbox("Location", location_options, index=0, accept_new_options=True)
        platforms = st.multiselect("Platforms to search", SOURCES, default=SOURCES)
        max_jobs = st.slider(
            "Maximum jobs in one session",
            min_value=1,
            max_value=50,
            value=min(50, int(criteria_defaults["session_cap"])),
        )
        st.caption(provider_status_label(provider_config.has_api_search))

        disabled = not title_contains or not description_contains or not platforms
        criteria = SearchCriteria(
            title_terms=tuple(str(item) for item in title_contains),
            description_terms=tuple(str(item) for item in description_contains),
            location=str(location),
            platforms=tuple(str(item) for item in platforms),
            max_results=int(max_jobs),
        )
        with st.expander("Queries that will run"):
            for query in _planned_queries(criteria, provider_config):
                st.markdown(f"**{query.platform}**")
                st.code(query.query, language="text")

        with st.container(horizontal=True, wrap=True):
            if st.button("Run search and score jobs", icon=":material/search:", disabled=disabled):
                with st.status("Searching public results and scoring jobs", expanded=True) as status:
                    summary = run_public_search(criteria, active_preferences, queue, provider_config=provider_config)
                    for log in summary.logs:
                        st.write(log)
                    status.update(label="Search run finished", state="complete")
                st.dataframe(search_summary_to_rows(summary), hide_index=True)
                st.success("Open Job queue to review the scored results.")
            if st.button("Preview search run", icon=":material/play_arrow:", disabled=disabled):
                _render_search_preview(max_jobs=max_jobs, location=str(location), platforms=platforms)

    with st.container(border=True):
        st.markdown("**Duplicate handling**")
        st.write(
            "If LinkedIn and Foundit show the same exact role at the same company and location, Job Hunter keeps one queue item and treats the other as a duplicate. Later we can store the extra platform links as alternate sources."
        )


def _render_search_preview(max_jobs: int, location: str, platforms: list[str]) -> None:
    progress = st.progress(0, text="Preparing search session")
    log_box = st.empty()
    sample_jobs = [
        "BI Developer at Example Analytics",
        "Data Engineer at Example Bank",
        "Reporting Analyst at Example Retail",
        "Business Intelligence Analyst at Example Insurance",
    ]
    logs = []
    for step, job in enumerate(sample_jobs, start=1):
        pct = min(100, int(step / min(max_jobs, len(sample_jobs)) * 100))
        source = platforms[(step - 1) % len(platforms)]
        logs.append(f"Checked {step}/{max_jobs}: {job} - {location} - {source}")
        progress.progress(pct, text=f"Preview only: {step}/{max_jobs} checked")
        log_box.code("\n".join(logs), language="text")
    st.info("This preview shows the intended search experience. It does not scrape or log in to job boards yet.")


def _render_queue(queue: JobQueue) -> None:
    st.subheader("Job queue")
    st.write("This is the ranked list after jobs are added or imported. Start here when you want to review the strongest matches first.")
    jobs = queue.list_jobs()
    if not jobs:
        st.info("No jobs are queued yet. Add one manually or import the sample CSV format from the Import CSV page.")
        _render_example_jobs()
        return

    col1, col2 = st.columns(2)
    with col1:
        decision = st.segmented_control("Decision", ["all", "shortlist", "review", "reject", "skip"], default="all")
    with col2:
        status = st.segmented_control("Status", ["all", "new", "reviewing", "drafted", "submitted", "rejected"], default="all")
    filtered = filter_jobs(jobs, decision=str(decision), status=str(status))

    if not filtered:
        st.info("No jobs match the current filters.")
        return

    st.dataframe(
        jobs_to_rows(filtered),
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            "Source URL": st.column_config.LinkColumn("Source"),
            **{
                column: st.column_config.TextColumn(column, width=width)
                for column, width in queue_column_widths().items()
                if column != "Source URL"
            },
        },
        hide_index=True,
        use_container_width=True,
        height=520,
    )
    _render_queue_actions(queue, filtered)


def _render_add_job(queue: JobQueue, preferences: dict[str, object]) -> None:
    st.subheader("Add job")
    st.write(
        "Use this for one job you already found. Yes, this means copy-pasting the job description for now; the automated platform search is the next major version."
    )
    with st.expander("Example job data", expanded=True):
        st.code(
            """Title: BI Developer
Company: Example Analytics
Location: Kuala Lumpur
Source URL: https://example.com/jobs/bi-developer
Description: Build Power BI dashboards, SSRS reports, SQL datasets, and reporting automation for business teams.""",
            language="text",
        )

    with st.form("add_job"):
        title = st.text_input("Job title", placeholder="BI Developer")
        company = st.text_input("Company", placeholder="Example Analytics")
        cities = _cached_malaysia_cities()
        location = st.selectbox("Location", _location_options(cities), index=0, accept_new_options=True)
        source_url = st.text_input("Source URL", placeholder="https://...")
        description = st.text_area(
            "Job description",
            height=240,
            placeholder="Paste the job description here. Power BI / SSRS / BigQuery are treated as primary match signals.",
        )
        submitted = st.form_submit_button("Score and add", icon=":material/add_circle:")

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Job title and description are required.")
            return
        result = queue.add_job(
            JobInput(
                title=title,
                company=company,
                location=str(location),
                description=description,
                source_url=source_url,
            ),
            preferences,
        )
        if result.created:
            st.success(f"Added job #{result.job_id}: {result.score}/100 - {result.decision}")
        else:
            st.warning(f"Duplicate job #{result.job_id}: {result.score}/100 - {result.decision}")


def _render_import(queue: JobQueue, preferences: dict[str, object]) -> None:
    st.subheader("Import CSV")
    st.write(
        "Use this when you already have many job rows from a spreadsheet, export, or manual research list. It saves you from adding job descriptions one by one."
    )
    with st.container(border=True):
        st.markdown("**Expected columns**")
        st.code("title, company, location, description, source_url", language="text")
        st.download_button("Download example CSV", SAMPLE_CSV, file_name="job-hunter-example.csv", mime="text/csv", icon=":material/download:")
        st.dataframe(pd.read_csv(StringIO(SAMPLE_CSV)), hide_index=True)

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is None:
        return

    if st.button("Import and score CSV", icon=":material/upload_file:"):
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as handle:
            handle.write(uploaded.getbuffer())
            temp_path = Path(handle.name)
        summary = queue.import_csv(temp_path, preferences)
        st.success(f"Imported {summary.created}; skipped {summary.duplicates} duplicates.")


def _render_queue_actions(queue: JobQueue, jobs) -> None:
    st.subheader("Application actions")
    jobs = list(jobs)
    if not jobs:
        return

    options = {f"#{job.id} - {job.title} - {job.company}": job.id for job in jobs}
    selected = st.selectbox("Job", list(options))
    job_id = options[selected]

    with st.container(horizontal=True, wrap=True):
        if st.button("Export draft", icon=":material/edit_document:"):
            path = queue.export_draft(job_id, ROOT / "exports" / "drafts")
            queue.update_status(job_id, "drafted")
            st.success(f"Draft exported to {path}")
        if st.button("Export packet", icon=":material/folder:"):
            path = queue.export_application_packet(job_id, ROOT / "exports" / "application-packets")
            queue.update_status(job_id, "reviewing")
            st.success(f"Packet exported to {path}")

    st.caption("Apply buttons are intentionally disabled until real platform login and browser submission flows are implemented.")
    with st.container(horizontal=True, wrap=True):
        st.button("Apply selected", icon=":material/send:", disabled=True)
        st.button("Apply all shortlisted", icon=":material/done_all:", disabled=True)

    new_status = st.selectbox("Set status", ["new", "reviewing", "drafted", "submitted", "rejected"])
    if st.button("Update status", icon=":material/save:"):
        queue.update_status(job_id, new_status)
        st.success(f"Job #{job_id} is now {new_status}.")


def _render_keyword_chips(label: str, values: list[str]) -> None:
    st.markdown(f"**{label}**")
    st.pills(label, values, selection_mode="multi", default=values, disabled=True, label_visibility="collapsed", wrap=True)


def _render_example_jobs() -> None:
    st.dataframe(pd.read_csv(StringIO(SAMPLE_CSV)), hide_index=True)


@st.cache_data(ttl=3600)
def _cached_malaysia_cities() -> tuple[str, ...]:
    return fetch_malaysia_cities()


def _criteria_defaults(preferences: dict[str, object]) -> dict[str, object]:
    defaults = editable_criteria_defaults(preferences)
    if not defaults["target_roles"]:
        defaults["target_roles"] = TARGET_TITLES
    if not defaults["primary_keywords"]:
        defaults["primary_keywords"] = PRIMARY_KEYWORDS
    return defaults


def _active_preferences(preferences: dict[str, object]) -> dict[str, object]:
    defaults = _criteria_defaults(preferences)
    active = dict(preferences)
    active["target_roles"] = st.session_state.get("target_roles", defaults["target_roles"])
    active["primary_keywords"] = st.session_state.get("primary_keywords", defaults["primary_keywords"])
    active["bonus_keywords"] = st.session_state.get("bonus_keywords", defaults["bonus_keywords"])
    active["hard_skip_keywords"] = st.session_state.get("hard_skip_keywords", defaults["hard_skip_keywords"])
    active["daily_targets"] = {
        "strong_matches": st.session_state.get("strong_target", defaults["strong_target"]),
        "suitable_matches": st.session_state.get("session_cap", defaults["session_cap"]),
    }
    return active


def _render_editable_criteria(preferences: dict[str, object]) -> dict[str, object]:
    defaults = _criteria_defaults(preferences)
    with st.expander("Edit search and scoring criteria", expanded=True):
        st.multiselect("Target titles", defaults["target_roles"], default=defaults["target_roles"], accept_new_options=True, key="target_roles")
        st.multiselect(
            "Primary strengths / description keywords",
            defaults["primary_keywords"],
            default=defaults["primary_keywords"],
            accept_new_options=True,
            key="primary_keywords",
        )
        st.multiselect("Bonus keywords", defaults["bonus_keywords"], default=defaults["bonus_keywords"], accept_new_options=True, key="bonus_keywords")
        st.multiselect(
            "Hard skip keywords",
            defaults["hard_skip_keywords"],
            default=defaults["hard_skip_keywords"],
            accept_new_options=True,
            key="hard_skip_keywords",
        )
        left, right = st.columns(2)
        left.number_input("Strong target", min_value=1, max_value=50, value=int(defaults["strong_target"]), key="strong_target")
        right.number_input("Session cap", min_value=1, max_value=50, value=min(50, int(defaults["session_cap"])), key="session_cap")
    return _active_preferences(preferences)


def _location_options(cities: tuple[str, ...]) -> tuple[str, ...]:
    options = city_options("", cities=cities, limit=300)
    if "Kuala Lumpur" not in options:
        return ("Kuala Lumpur",) + options
    return ("Kuala Lumpur",) + tuple(city for city in options if city != "Kuala Lumpur")


def _planned_queries(criteria: SearchCriteria, provider_config: SearchProviderConfig):
    if provider_config.has_api_search:
        return build_serpapi_queries(criteria, provider_config.serpapi_key)
    queries = build_direct_platform_queries(criteria)
    direct_platforms = {query.platform for query in queries}
    queries.extend(query for query in build_search_queries(criteria) if query.platform not in direct_platforms)
    return queries


if __name__ == "__main__":
    main()
