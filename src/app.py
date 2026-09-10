from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from job_hunter.app_ui import (
    application_destination,
    application_destination_host,
    filter_jobs,
    jobs_to_rows,
    provider_status_label,
    search_summary_to_rows,
)
from job_hunter.cv_parser import detect_cv_signals, extract_cv_text
from job_hunter.cv_store import CVStore, format_size
from job_hunter.locations import city_options, fetch_malaysia_cities
from job_hunter.preferences import load_preferences
from job_hunter.queue import JobQueue
from job_hunter.runtime_config import SearchProviderConfig, load_search_provider_config
from job_hunter.search import (
    SearchCriteria,
    SearchProgress,
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
PAGES = ("Profile & CV", "Search jobs", "Job queue")
POSTING_AGE_OPTIONS = {
    "Past 24 hours": 1,
    "Past week": 7,
    "Past month": 30,
    "Any time": None,
}
DEFAULT_STRONG_TARGET = 20
DEFAULT_SESSION_CAP = 50


def main() -> None:
    st.set_page_config(page_title="Job Hunter", page_icon=":material/work:", layout="wide")

    queue = JobQueue(DB_PATH)
    preferences = load_preferences(PREFERENCES_PATH)
    cv_store = CVStore(CV_STORAGE_DIR)
    provider_config = load_search_provider_config(st.secrets)

    _inject_table_styles()
    _render_header()
    _render_sidebar(queue, cv_store, provider_config, preferences)

    st.session_state.setdefault("page", PAGES[0])
    page = st.segmented_control("Page", PAGES, key="page")
    if page == "Profile & CV":
        _render_profile(cv_store, preferences)
    elif page == "Search jobs":
        _render_search_jobs(queue, preferences, cv_store, provider_config)
    else:
        _render_queue(queue)


def _render_header() -> None:
    left, right = st.columns([1.7, 1], vertical_alignment="center")
    with left:
        st.title("Job Hunter")
        st.caption("Search, score, and review Kuala Lumpur data jobs using criteria you control.")
        with st.container(horizontal=True, wrap=True):
            st.badge("Automated search + scoring", icon=":material/search:", color="green")
            st.badge("CV is optional", icon=":material/description:", color="blue")
            st.badge("Official application links", icon=":material/open_in_new:", color="gray")
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
) -> None:
    jobs = queue.list_jobs()
    cv_status = cv_store.status()
    defaults = _criteria_defaults(preferences)
    with st.sidebar:
        st.header("Today")
        st.metric("Queued jobs", len(jobs))
        st.metric(
            "Strong-match goal",
            st.session_state.get("strong_target", defaults["strong_target"]),
            help="A goal for how many high-scoring jobs you want to find. It does not stop or limit the search.",
        )
        st.caption("Search and scoring work with or without a CV.")
        if cv_status.exists:
            st.success(f"CV saved locally ({format_size(cv_status.size_bytes)}).")
        else:
            st.caption("No CV saved. You can still search using your criteria.")
        st.caption(provider_status_label(provider_config.has_api_search))


def _render_profile(cv_store: CVStore, preferences: dict[str, object]) -> None:
    st.subheader("Profile & CV")
    st.write(
        "A CV is optional. Upload one for private profile reference, or skip this page and search using editable keywords. The repository never commits your actual CV."
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
            st.caption("No CV text is needed for keyword-based searching and scoring.")
        st.caption("Search criteria are editable on the Search jobs page.")


def _render_search_jobs(
    queue: JobQueue,
    preferences: dict[str, object],
    cv_store: CVStore,
    provider_config: SearchProviderConfig,
) -> None:
    st.subheader("Search jobs")
    st.write(
        "Set title, description keywords, exact location, and selected platforms, then run up to 50 public search-result checks in one session."
    )
    cv_text = cv_store.load_text()
    if cv_text:
        signals = detect_cv_signals(cv_text, preferences)
        st.success(
            f"CV available for profile reference. Detected {signals.total_matches} matching signals; scoring uses the editable criteria below."
        )
    else:
        st.info("No CV is saved, and that is fine. Search and scoring use the editable criteria below.")

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
        posting_age = st.selectbox(
            "Date posted",
            tuple(POSTING_AGE_OPTIONS),
            index=2,
            help="Limits results to newer postings where the selected search provider supports a date filter.",
        )
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
            posted_within_days=POSTING_AGE_OPTIONS[str(posting_age)],
        )
        with st.expander("Queries that will run"):
            for query in _planned_queries(criteria, provider_config):
                st.markdown(f"**{query.platform}**")
                st.code(query.query, language="text")

        if st.button(
            "Run search and score jobs",
            icon=":material/search:",
            disabled=disabled,
            type="primary",
        ):
            with st.status("Searching public results and scoring jobs", expanded=True) as status:
                progress_bar = st.progress(0, text=f"0/{max_jobs} jobs checked - preparing search")
                activity_box = st.empty()
                live_logs: list[str] = []

                def show_progress(event: SearchProgress) -> None:
                    live_logs.append(event.message)
                    short_message = (
                        event.message if len(event.message) <= 120 else f"{event.message[:117]}..."
                    )
                    percent = (
                        100
                        if event.stage == "complete"
                        else min(99, int(event.checked / max(1, event.total) * 100))
                    )
                    progress_bar.progress(
                        percent,
                        text=f"{event.checked}/{event.total} jobs checked - {short_message}",
                    )
                    activity_box.code("\n".join(live_logs[-12:]), language="text")

                summary = run_public_search(
                    criteria,
                    active_preferences,
                    queue,
                    provider_config=provider_config,
                    progress_callback=show_progress,
                )
                status.update(label="Search run finished", state="complete", expanded=True)
            st.session_state["last_search_summary"] = summary

        summary = st.session_state.get("last_search_summary")
        if summary is not None:
            st.dataframe(search_summary_to_rows(summary), hide_index=True)
            st.button(
                "Review Job queue",
                icon=":material/table_chart:",
                type="primary",
                on_click=_open_page,
                args=("Job queue",),
            )

    with st.container(border=True):
        st.markdown("**Duplicate handling**")
        st.write(
            "If LinkedIn and Foundit show the same exact role at the same company and location, Job Hunter keeps one queue item and treats the other as a duplicate. Later we can store the extra platform links as alternate sources."
        )

def _render_queue(queue: JobQueue) -> None:
    st.subheader("Job queue")
    st.write("Review the strongest matches first, then open the official application destination.")
    jobs = queue.list_jobs()
    if not jobs:
        st.info("No jobs are queued yet. Open Search jobs and run your first search.")
        return

    decision = st.segmented_control(
        "Decision", ["all", "shortlist", "review", "reject", "skip"], default="all"
    )
    filtered = filter_jobs(jobs, decision=str(decision))

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
                for column, width in _queue_column_widths().items()
                if column != "Source URL"
            },
        },
        hide_index=True,
        width="stretch",
        height=520,
    )
    _render_queue_actions(filtered)


def _render_queue_actions(jobs) -> None:
    st.subheader("Apply")
    jobs = list(jobs)
    if not jobs:
        return

    options = {f"#{job.id} - {job.title} - {job.company}": job for job in jobs}
    selected = st.selectbox("Job", list(options))
    job = options[selected]
    destination = application_destination(job)
    destination_host = application_destination_host(job)
    if job.apply_url and destination == job.apply_url:
        st.caption("Job Hunter found an official application destination for this role.")
    else:
        st.caption("No separate application destination was found, so Apply opens the original posting.")
    if destination_host:
        st.caption(f"Destination: `{destination_host}`")
    st.link_button(
        "Apply",
        destination or "https://jobs-hunter.streamlit.app/",
        icon=":material/open_in_new:",
        type="primary",
        disabled=not destination,
        help="Opens the safest available application page in a new tab.",
    )
    st.info(
        "Review the destination before submitting. Platform login, CAPTCHA, and required questions stay in your browser."
    )


def _render_keyword_chips(label: str, values: list[str]) -> None:
    st.markdown(f"**{label}**")
    st.pills(label, values, selection_mode="multi", default=values, disabled=True, label_visibility="collapsed", wrap=True)


@st.cache_data(ttl=3600)
def _cached_malaysia_cities() -> tuple[str, ...]:
    return fetch_malaysia_cities()


def _criteria_defaults(preferences: dict[str, object]) -> dict[str, object]:
    defaults = _editable_criteria_defaults(preferences)
    if not defaults["target_roles"]:
        defaults["target_roles"] = TARGET_TITLES
    if not defaults["primary_keywords"]:
        defaults["primary_keywords"] = PRIMARY_KEYWORDS
    return defaults


def _editable_criteria_defaults(preferences: dict[str, object]) -> dict[str, object]:
    daily_targets = preferences.get("daily_targets", {})
    if not isinstance(daily_targets, dict):
        daily_targets = {}
    return {
        "target_roles": _string_list(preferences.get("target_roles")),
        "primary_keywords": _string_list(preferences.get("primary_keywords")),
        "bonus_keywords": _string_list(preferences.get("bonus_keywords")),
        "hard_skip_keywords": _string_list(preferences.get("hard_skip_keywords")),
        "strong_target": int(daily_targets.get("strong_matches", DEFAULT_STRONG_TARGET)),
        "session_cap": int(daily_targets.get("suitable_matches", DEFAULT_SESSION_CAP)),
    }


def _queue_column_widths() -> dict[str, str]:
    return {
        "Title": "large",
        "Company": "medium",
        "Location": "medium",
        "Posted": "medium",
        "Reasons": "large",
        "Remarks": "large",
        "Description": "large",
        "Source URL": "medium",
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


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
        strong_target = left.number_input(
            "Strong-match goal",
            min_value=1,
            max_value=50,
            value=int(defaults["strong_target"]),
            key="strong_target",
            help="Your goal for the number of jobs that meet the strong-match score. This is not a minimum, maximum, or stopping rule.",
        )
        right.number_input(
            "Session cap",
            min_value=1,
            max_value=50,
            value=min(50, int(defaults["session_cap"])),
            key="session_cap",
            help="The maximum number of job results checked during one search run.",
        )
        minimum_score = int(preferences.get("minimum_score_to_apply", 90))
        st.caption(
            f"Goal: find {strong_target} jobs scoring at least {minimum_score}%. "
            "The search continues until it reaches the session cap or runs out of results."
        )
    return _active_preferences(preferences)


def _open_page(page: str) -> None:
    st.session_state["page"] = page


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
