from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import MutableMapping

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from job_hunter.app_ui import filter_jobs, jobs_to_rows, provider_status_label
from job_hunter.application_links import (
    application_destination_hostname,
    application_destination_url,
)
from job_hunter.cv_parser import detect_cv_signals, extract_cv_text
from job_hunter.cv_store import format_size
from job_hunter.company_lookup import CompanyLookupError, CompanySite, lookup_company_site
from job_hunter.locations import company_region, fetch_malaysia_cities, is_global, location_options
from job_hunter.matching import MatchContext, MatchingConfig
from job_hunter.preferences import load_preferences
from job_hunter.provider_check import check_gemini_connection
from job_hunter.runtime_config import SearchProviderConfig, load_search_provider_config
from job_hunter.search import SearchCriteria
from job_hunter.search_runner import (
    MAX_UNIQUE_RESULTS,
    RunSnapshot,
    SearchRequest,
    SearchRunController,
)
from job_hunter.session_workspace import SessionWorkspace, get_session_workspace
from job_hunter.source_validation import (
    COMPANY_SOURCE_OPTIONS,
    COMPANY_SOURCE_DOMAINS,
    resolve_company_sources,
)
from job_hunter.search import APPLICATION_FILTERS


ROOT = Path(__file__).resolve().parents[1]
PREFERENCES_PATH = ROOT / "config" / "preferences.local.yaml"
HERO_IMAGE_URL = (
    "https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg"
    "?auto=compress&cs=tinysrgb&w=1600"
)
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
SOURCES = ["LinkedIn", "JobStreet", "Indeed", "Foundit"]
PAGES = ("Profile & CV", "Search jobs", "Job queue")
SEARCH_MODES = ("Criteria-based search", "CV-based search")
POSTING_AGE_OPTIONS = {
    "Past 24 hours": 1,
    "Past week": 7,
    "Past month": 30,
    "Any time": None,
}


def main() -> None:
    st.set_page_config(page_title="Job Hunter", page_icon=":material/work:", layout="wide")
    workspace = get_session_workspace(st.session_state)
    preferences = load_preferences(PREFERENCES_PATH)
    provider_config = load_search_provider_config(st.secrets)

    _inject_table_styles()
    _render_header()
    _render_sidebar(workspace, provider_config, preferences)
    _consume_page_request()
    visible_pages = PAGES if st.session_state.get("search_mode") == SEARCH_MODES[1] else PAGES[1:]
    if st.session_state.get("page") not in visible_pages:
        st.session_state["page"] = visible_pages[0]
    page = st.segmented_control("Page", visible_pages, key="page")
    if page == "Profile & CV":
        _render_profile(workspace, preferences)
    elif page == "Search jobs":
        _render_search_jobs(workspace, preferences, provider_config)
    else:
        _render_queue(workspace, preferences)


def _render_header() -> None:
    left, right = st.columns([1.7, 1], vertical_alignment="center")
    with left:
        st.title("Job Hunter")
        st.caption("Find, score, and review data jobs using criteria you control.")
        with st.container(horizontal=True, wrap=True):
            st.badge("Automated discovery", icon=":material/search:", color="green")
            st.badge("Gemini matching", icon=":material/auto_awesome:", color="blue")
            st.badge("Session-only privacy", icon=":material/lock:", color="gray")
    with right:
        st.image(HERO_IMAGE_URL)


def _inject_table_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stDataFrame"] div { white-space: normal; }
        [data-testid="stDataFrame"] [role="gridcell"] {
            align-items: start;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(
    workspace: SessionWorkspace,
    provider_config: SearchProviderConfig,
    preferences: dict[str, object],
) -> None:
    hard_skips = _search_settings()["hard_skip_keywords"]
    jobs = filter_jobs(
        workspace.list_jobs(),
        decision="all",
        hard_skip_keywords=hard_skips,
        application_view="all",
    )
    with st.sidebar:
        st.header("Today")
        st.metric("Jobs in this session", len(jobs))
        st.radio(
            "Matching mode",
            SEARCH_MODES,
            key="search_mode",
            help="Criteria mode never reads or sends CV text.",
        )
        if workspace.cv is not None:
            st.success(f"CV Saved ({format_size(workspace.cv.size_bytes)})")
        else:
            st.caption("No CV saved in this session.")
        st.caption(provider_status_label(provider_config.has_api_search))
        st.caption("Gemini enabled" if provider_config.has_gemini else "Gemini fallback mode")


def _render_profile(workspace: SessionWorkspace, preferences: dict[str, object]) -> None:
    st.subheader("Profile & CV")
    st.write(
        "Your CV stays only in this app session. It is not written to the public repository "
        "or shared with other visitors, and it can disappear when the session resets."
    )
    with st.container(border=True):
        if workspace.cv is not None:
            st.success(
                f"CV Saved: `{workspace.cv.filename}` - {format_size(workspace.cv.size_bytes)}"
            )
            if st.button("Remove saved CV", icon=":material/delete:"):
                _remove_saved_cv(workspace)
                st.toast("Saved CV removed.")
                st.rerun()
        else:
            st.info("No readable CV is saved in this session yet.")

        uploaded = st.file_uploader(
            "Upload or replace CV",
            type=["pdf", "docx", "doc"],
            key=_cv_upload_key(st.session_state),
        )
        if uploaded is not None and st.button("Save CV", icon=":material/save:"):
            try:
                content = uploaded.getvalue()
                workspace.save_cv(uploaded.name, content, extract_cv_text(content, uploaded.name))
            except Exception as exc:
                st.warning(f"CV could not be saved because readable text was not extracted: {exc}")
            else:
                st.toast("CV Saved")
            st.rerun()

    if workspace.cv is not None:
        st.button(
            "Continue to Search jobs",
            icon=":material/arrow_forward:",
            type="primary",
            on_click=_open_page,
            args=("Search jobs",),
        )
        signals = detect_cv_signals(workspace.cv_text, preferences)
        with st.container(border=True):
            st.markdown("**CV evidence detected**")
            st.caption(
                f"{signals.total_matches} configured skill signals found in the readable CV text."
            )
            _render_keyword_chips("Primary", list(signals.primary_matches))
            _render_keyword_chips("Bonus", list(signals.bonus_matches))


def _render_search_jobs(
    workspace: SessionWorkspace,
    preferences: dict[str, object],
    provider_config: SearchProviderConfig,
) -> None:
    st.subheader("Search jobs")
    if provider_config.has_gemini:
        st.caption(f"Configured Gemini model: {provider_config.gemini_model}")
        if st.button("Check Gemini connection", icon=":material/health_and_safety:"):
            with st.spinner("Checking Gemini with synthetic data..."):
                result = check_gemini_connection(MatchingConfig(
                    api_key=provider_config.gemini_api_key, model=provider_config.gemini_model
                ))
            st.session_state["gemini_check_result"] = (
                f"Gemini connection succeeded. Model: {result.model}" if result.engine == "Gemini"
                else result.remarks[-1]
            )
        if message := st.session_state.get("gemini_check_result"):
            if message.startswith("Gemini connection succeeded."):
                st.success(message)
            else:
                st.warning(message)
    mode = str(st.session_state.get("search_mode", SEARCH_MODES[0]))
    if mode == "CV-based search" and workspace.cv is None:
        st.warning("CV-based search needs a readable CV saved in this session.")
        st.button(
            "Upload CV",
            icon=":material/upload_file:",
            on_click=_open_page,
            args=("Profile & CV",),
            key="open_profile",
        )
    elif mode == "CV-based search":
        st.success("CV-based matching will compare each job with your saved CV and criteria.")
    else:
        st.info("Criteria-based matching does not read or send CV text, even when a CV is saved.")

    defaults = _criteria_defaults(preferences)
    with st.container(border=True):
        st.markdown("**Search and scoring criteria**")
        title_terms = st.multiselect(
            "Target job titles",
            _setting_options("target_roles", defaults["target_roles"]),
            accept_new_options=True,
            **_setting_widget("target_roles"),
            help="A title match can discover a job even when description keywords are absent.",
        )
        description_terms = st.multiselect(
            "Required description keywords",
            _setting_options("primary_keywords", defaults["primary_keywords"]),
            accept_new_options=True,
            **_setting_widget("primary_keywords"),
            help="A description match can discover a job even when its title is unfamiliar.",
        )
        st.multiselect(
            "Bonus keywords",
            _setting_options("bonus_keywords", defaults["bonus_keywords"]),
            accept_new_options=True,
            **_setting_widget("bonus_keywords"),
        )
        st.multiselect(
            "Hard skip keywords",
            _setting_options("hard_skip_keywords", defaults["hard_skip_keywords"]),
            accept_new_options=True,
            **_setting_widget("hard_skip_keywords"),
            help="Matching titles, descriptions, or page text are excluded before scoring.",
        )
        locations = st.multiselect(
            "Location",
            _setting_options("search_location", _location_options(_cached_malaysia_cities())),
            accept_new_options=True,
            **_setting_widget("search_location"),
            help="Choose cities, countries, Europe, ASEAN, APAC, or Global. Any selected area can match (OR). Global removes the geographic restriction.",
        )
        platforms = st.multiselect(
            "Platforms to search", SOURCES, **_setting_widget("search_platforms")
        )
        application_filters = st.multiselect(
            "Platform application filters",
            _setting_options("application_filters", tuple(APPLICATION_FILTERS.values())),
            **_setting_widget("application_filters"),
            help="Optional, strict filters for their own platform only. Unverified quick-apply postings are skipped. This does not submit applications.",
        )
        company_values = st.multiselect(
            "Company career sites",
            _setting_options("company_sources", COMPANY_SOURCE_OPTIONS),
            accept_new_options=True,
            format_func=_company_source_label,
            **_setting_widget("company_sources"),
            help=(
                "Choose a listed company, type another company name, or enter a careers domain. "
                "New names use Gemini web search to verify official careers for your selected "
                "location. Up to five sites are searched through SerpAPI."
            ),
        )
        posting_age = st.selectbox(
            "Date posted", tuple(POSTING_AGE_OPTIONS), **_setting_widget("posting_age")
        )
        custom_sources, source_errors = resolve_company_sources(
            company_values, has_api_search=provider_config.has_api_search,
            lookup=lambda name: _lookup_company_for_locations(name, locations, provider_config),
            lookup_regions=len(_company_regions(locations)),
        )
        for error in source_errors:
            st.warning(error)
        if source_errors and provider_config.has_gemini and company_values:
            if st.button("Retry company lookup", icon=":material/refresh:"):
                st.session_state["company_lookups"] = {
                    key: result for key, result in st.session_state.get("company_lookups", {}).items()
                    if not isinstance(result, str)
                }
                st.rerun()
        _render_company_evidence(company_values, locations)
        st.caption(
            "Each run checks up to 50 unique candidates, then ranks the scored results. "
            "This is not a guarantee of the 50 best jobs. It stops earlier when sources run out, "
            "the five-minute scheduling limit is reached, or you press Stop."
        )
        st.caption(provider_status_label(provider_config.has_api_search))

        criteria = SearchCriteria(
            title_terms=tuple(str(value) for value in title_terms),
            description_terms=tuple(str(value) for value in description_terms),
            location="",
            locations=tuple(str(value) for value in locations),
            platforms=tuple(str(value) for value in platforms),
            max_results=MAX_UNIQUE_RESULTS,
            posted_within_days=POSTING_AGE_OPTIONS[str(posting_age)],
            custom_domains=tuple(source.hostname for source in custom_sources),
            custom_site_filters=tuple(source.site_filter for source in custom_sources),
            application_filters=tuple(application_filters),
        )
        ready, reason = _search_is_ready(mode, workspace, criteria)
        controller = _get_controller()
        running = controller.snapshot().state == "running"
        if st.button(
            "Run search and score jobs",
            icon=":material/search:",
            disabled=not ready or bool(source_errors) or running,
            type="primary",
            key="run_search",
            help=reason or None,
        ):
            active_preferences = _active_preferences(preferences)
            context = MatchContext(
                mode="cv" if mode == "CV-based search" else "criteria",
                criteria=active_preferences,
                cv_text=workspace.cv_text if mode == "CV-based search" else "",
            )
            run_id = controller.start(
                SearchRequest(
                    criteria=criteria,
                    match_context=context,
                    provider_config=provider_config,
                    matching_config=MatchingConfig(
                        api_key=provider_config.gemini_api_key,
                        model=provider_config.gemini_model,
                    ),
                )
            )
            workspace.activate_run(run_id)
            st.session_state["run_logs"] = []
            st.rerun()

    _render_run_fragment(workspace)


@st.fragment(run_every="1s")
def _render_run_fragment(workspace: SessionWorkspace) -> None:
    controller = _get_controller()
    events, matches = controller.drain()
    logs = list(st.session_state.get("run_logs", []))
    for match in matches:
        workspace.accept_completed(match)
    logs.extend(event.message for event in events)
    st.session_state["run_logs"] = logs[-30:]
    snapshot = controller.snapshot()

    left, right = st.columns([3, 1], vertical_alignment="bottom")
    with left:
        progress_value, progress_label = _run_progress(snapshot)
        st.progress(
            progress_value,
            text=progress_label,
        )
    with right:
        if st.button(
            "Stop search",
            icon=":material/stop_circle:",
            disabled=snapshot.state != "running",
            key="stop_search",
        ):
            controller.cancel()
            st.rerun(scope="fragment")

    if logs:
        st.code("\n".join(logs[-12:]), language="text")
    if snapshot.state == "completed":
        st.success(snapshot.message)
    elif snapshot.state == "cancelled":
        st.warning(snapshot.message)
    elif snapshot.state == "failed":
        st.error(snapshot.message)
    elif snapshot.state == "running":
        st.caption(
            f"Found {snapshot.discovered} unique candidates; scored {snapshot.completed}; "
            f"skipped {snapshot.skipped}."
        )
    else:
        st.caption("Ready to search. Progress and current activity will appear here.")

    if snapshot.completed or workspace.list_jobs():
        if st.button(
            "Review Job queue",
            icon=":material/table_chart:",
            type="primary",
            key="review_queue",
        ):
            _navigate_from_fragment("Job queue")


def _render_queue(workspace: SessionWorkspace, preferences: dict[str, object]) -> None:
    st.subheader("Job queue")
    st.write("Review scored matches, open an application page, and record applications manually.")
    all_jobs = filter_jobs(
        workspace.list_jobs(),
        decision="all",
        hard_skip_keywords=_active_preferences(preferences).get("hard_skip_keywords", ()),
        application_view="all",
    )
    if not all_jobs:
        st.info("No jobs are queued yet. Open Search jobs and run your first search.")
        return

    view = st.segmented_control(
        "Applications", ("Actionable", "All", "Already applied"), default="Actionable"
    )
    decision = st.segmented_control(
        "Match", ("all", "shortlist", "review", "reject", "skip"), default="all"
    )
    application_view = {
        "Actionable": "actionable",
        "All": "all",
        "Already applied": "applied",
    }[str(view)]
    filtered = filter_jobs(
        all_jobs,
        decision=str(decision),
        application_view=application_view,
    )
    if not filtered:
        st.info("No jobs match the current filters.")
        return

    rows = jobs_to_rows(filtered)
    if rows and "Location" not in rows[0]:
        st.caption("Posting locations could not be verified for these results.")
    st.dataframe(
        rows,
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            "Source URL": st.column_config.LinkColumn("Primary source"),
            **{
                column: st.column_config.TextColumn(column, width=width)
                for column, width in _queue_column_widths().items()
                if column != "Source URL" and column in rows[0]
            },
        },
        hide_index=True,
        width="stretch",
        height=560,
    )
    _render_queue_actions(workspace, filtered)


def _render_queue_actions(workspace: SessionWorkspace, jobs) -> None:
    st.subheader("Apply")
    jobs = list(jobs)
    if not jobs:
        return
    options = _application_job_options(jobs)
    selected = st.selectbox("Job", list(options))
    job = options[selected]
    _render_posting_editor(workspace, job)
    applied = st.checkbox(
        "I have applied to this job",
        value=job.application_status == "applied",
        key=f"application_status_{job.id}",
    )
    desired_status = "applied" if applied else "not_applied"
    if desired_status != job.application_status:
        workspace.update_application_status(job.id, desired_status)
        st.toast("Application status updated.")
        st.rerun()

    destination = application_destination_url(job.apply_url, job.source_url)
    destination_host = application_destination_hostname(job.apply_url, job.source_url)
    st.caption(
        "Job Hunter found an official application destination."
        if job.apply_url and destination == job.apply_url
        else "Apply opens the safest available original posting."
    )
    if destination_host:
        st.caption(f"Destination: `{destination_host}`")
    st.link_button(
        "Apply",
        destination or "https://jobs-hunter.streamlit.app/",
        icon=":material/open_in_new:",
        type="primary",
        disabled=not destination or job.availability == "expired",
        help="Opens the application page in a new browser tab.",
    )
    st.info(
        "Review the destination before submitting. Login, CAPTCHA, and required questions "
        "remain in the platform page. Opening Apply does not mark the job as applied."
    )


def _render_posting_editor(workspace: SessionWorkspace, job) -> None:
    with st.expander("Posting date & expiry"):
        st.caption(job.availability_evidence or "Expiry has not been verified.")
        with st.form(f"posting_evidence_{job.id}"):
            try:
                current_date = date.fromisoformat(job.posted_date) if job.posted_date else None
            except ValueError:
                current_date = None
            if current_date and current_date > date.today():
                current_date = None
            posted = st.date_input("Posting date", value=current_date, max_value=date.today(),
                                   key=f"posting_date_{job.id}", format="YYYY-MM-DD")
            labels = {"unknown": "Unknown", "not_expired": "Not expired", "expired": "Expired"}
            expiry = st.selectbox("Expiry", tuple(labels),
                                  index=tuple(labels).index(job.availability),
                                  format_func=labels.get, key=f"posting_expiry_{job.id}")
            if st.form_submit_button("Save posting details", icon=":material/save:"):
                workspace.update_posting_evidence(job.id, posted.isoformat() if posted else "", str(expiry))
                st.toast("Posting details saved. User corrections are not platform-verified.")
                st.rerun()


def _search_is_ready(
    mode: str, workspace: SessionWorkspace, criteria: SearchCriteria
) -> tuple[bool, str]:
    if mode == "CV-based search" and not workspace.cv_text.strip():
        return False, "Upload a readable CV before using CV-based search."
    if not criteria.title_terms and not criteria.description_terms:
        return False, "Add at least one title or description keyword."
    if not criteria.location_targets:
        return False, "Choose or type a location."
    if not criteria.platforms and not criteria.custom_domains:
        return False, "Select at least one platform or valid custom source."
    return True, ""


def _get_controller() -> SearchRunController:
    controller = st.session_state.get("search_controller")
    if not isinstance(controller, SearchRunController):
        controller = SearchRunController()
        st.session_state["search_controller"] = controller
    return controller


def _render_keyword_chips(label: str, values: list[str]) -> None:
    st.markdown(f"**{label}**")
    if values:
        st.pills(
            label,
            values,
            selection_mode="multi",
            default=values,
            disabled=True,
            label_visibility="collapsed",
            wrap=True,
        )
    else:
        st.caption("No configured signals detected.")


@st.cache_data(ttl=3600)
def _cached_malaysia_cities() -> tuple[str, ...]:
    return fetch_malaysia_cities()


def _criteria_defaults(preferences: dict[str, object]) -> dict[str, list[str]]:
    target_roles = _string_list(preferences.get("target_roles")) or TARGET_TITLES
    primary = _string_list(preferences.get("primary_keywords")) or PRIMARY_KEYWORDS
    return {
        "target_roles": target_roles,
        "primary_keywords": primary,
        "bonus_keywords": _string_list(preferences.get("bonus_keywords")),
        "hard_skip_keywords": _string_list(preferences.get("hard_skip_keywords")),
    }


def _queue_column_widths() -> dict[str, str]:
    return {
        "Title": "large",
        "Company": "medium",
        "Location": "medium",
        "Posted": "medium",
        "Application status": "medium",
        "Reasons": "large",
        "Remarks": "large",
        "Description": "large",
        "Source URL": "medium",
        "Expiry": "medium",
        "Expiry evidence": "large",
        "Quick apply": "medium",
        "Scoring": "medium",
        "Description quality": "large",
        "Date details": "large",
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _active_preferences(preferences: dict[str, object]) -> dict[str, object]:
    settings = _search_settings()
    active = dict(preferences)
    for field in ("target_roles", "primary_keywords", "bonus_keywords", "hard_skip_keywords"):
        active[field] = list(settings[field])
    active["target_locations"] = list(settings["search_location"])
    active["avoid_keywords"] = []
    active["remote_policy"] = []
    active.pop("preferred_keywords", None)
    return active


def _search_settings() -> dict[str, object]:
    settings = st.session_state.get("search_settings")
    if not isinstance(settings, dict):
        settings = {
            "target_roles": [], "primary_keywords": [], "bonus_keywords": [],
            "hard_skip_keywords": [], "search_platforms": [], "company_sources": [],
            "search_location": [], "posting_age": "Past month", "application_filters": [],
        }
        st.session_state["search_settings"] = settings
    settings.setdefault("application_filters", [])
    location = settings.get("search_location")
    if not isinstance(location, list):
        settings["search_location"] = [location] if isinstance(location, str) and location else []
    return settings


def _save_search_setting(field: str) -> None:
    value = st.session_state[f"_{field}"]
    _search_settings()[field] = list(value) if isinstance(value, list) else value


def _setting_widget(field: str) -> dict[str, object]:
    # Widget keys disappear off-page; permanent settings do not belong to a widget.
    key = f"_{field}"
    value = _search_settings()[field]
    st.session_state[key] = list(value) if isinstance(value, list) else value
    return {"key": key, "on_change": _save_search_setting, "args": (field,)}


def _setting_options(field: str, suggestions) -> list[str]:
    saved = _search_settings()[field]
    values = saved if isinstance(saved, list) else [saved] if saved else []
    return list(dict.fromkeys([*suggestions, *values]))


def _company_source_label(value: str) -> str:
    domain = COMPANY_SOURCE_DOMAINS.get(value)
    return f"{value} ({domain})" if domain else value


def _company_region(location: str) -> str:
    cities = _cached_malaysia_cities()
    return "Malaysia" if location.casefold() in {city.casefold() for city in cities} else company_region(location)


def _company_regions(locations) -> tuple[str, ...]:
    if is_global(locations):
        return ("Global",)
    return tuple(dict.fromkeys(_company_region(str(value)) for value in locations if str(value).strip()))


def _lookup_company_for_locations(name: str, locations, config: SearchProviderConfig) -> tuple[CompanySite, ...]:
    regions = _company_regions(locations)
    if not regions:
        raise CompanyLookupError("Select a location before looking up company names.")
    return tuple(_lookup_company(name, region, config) for region in regions)


def _lookup_company(name: str, location: str, config: SearchProviderConfig) -> CompanySite:
    if not location:
        raise CompanyLookupError("Select a location before looking up company names.")
    if not config.has_gemini:
        raise CompanyLookupError("Company-name lookup needs GEMINI_API_KEY; enter a careers domain instead.")
    region = _company_region(location)
    key = (name.strip().casefold(), region.casefold(), config.gemini_model)
    cache = st.session_state.setdefault("company_lookups", {})
    if key not in cache:
        with st.spinner(f"Verifying official {name} careers for {region}..."):
            try:
                cache[key] = lookup_company_site(name, region, MatchingConfig(
                    api_key=config.gemini_api_key, model=config.gemini_model
                ))
            except CompanyLookupError as exc:
                cache[key] = str(exc)
    result = cache[key]
    if isinstance(result, str):
        raise CompanyLookupError(result)
    return result


def _render_company_evidence(values, locations) -> None:
    cache = st.session_state.get("company_lookups", {})
    regions = {region.casefold() for region in _company_regions(locations)}
    for value in values:
        matches = [result for (name, scope, _), result in cache.items()
                   if name == str(value).strip().casefold() and scope in regions
                   and isinstance(result, CompanySite)]
        for matched in matches:
            st.link_button(f"{matched.company} ({matched.hostname}) - {matched.region}",
                           matched.careers_url, icon=":material/verified:")
            with st.expander(f"{matched.company} verification sources"):
                for index, url in enumerate(matched.evidence_urls, start=1):
                    st.link_button(f"Source {index}: {urlparse_hostname(url)}", url,
                                   icon=":material/open_in_new:")
                if matched.search_suggestions:
                    st.html(matched.search_suggestions)


def urlparse_hostname(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or "Official source"


def _open_page(page: str) -> None:
    st.session_state["page"] = page


def _application_job_options(jobs) -> dict[str, object]:
    return {
        f"#{job.id} - {job.title} - {job.company}": job
        for job in sorted(jobs, key=lambda job: job.id)
    }


def _navigate_from_fragment(page: str) -> None:
    st.session_state["requested_page"] = page
    st.rerun()


def _consume_page_request() -> None:
    requested = st.session_state.pop("requested_page", None)
    if requested in PAGES:
        st.session_state["page"] = requested


def _cv_upload_key(state: MutableMapping[str, object]) -> str:
    revision = state.get("cv_upload_revision", 0)
    return f"cv_upload_{revision if isinstance(revision, int) else 0}"


def _remove_saved_cv(workspace: SessionWorkspace) -> None:
    current_key = _cv_upload_key(st.session_state)
    workspace.remove_cv()
    st.session_state.pop(current_key, None)
    revision = st.session_state.get("cv_upload_revision", 0)
    st.session_state["cv_upload_revision"] = (
        revision + 1 if isinstance(revision, int) else 1
    )


def _run_progress(snapshot: RunSnapshot) -> tuple[int, str]:
    if snapshot.state == "completed":
        return (
            100,
            f"{snapshot.checked} jobs checked - Search complete "
            f"({MAX_UNIQUE_RESULTS}-job maximum).",
        )
    value = min(100, int(snapshot.checked / MAX_UNIQUE_RESULTS * 100))
    return value, f"{snapshot.checked}/{MAX_UNIQUE_RESULTS} jobs checked - {snapshot.message}"


def _location_options(cities: tuple[str, ...]) -> tuple[str, ...]:
    return location_options(cities)


if __name__ == "__main__":
    main()
