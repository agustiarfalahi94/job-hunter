"""Versioned private account snapshots, excluding runtime and provider state."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field, fields
import json
import re

from job_hunter.queue import JobRecord
from job_hunter.session_workspace import SessionCV, SessionWorkspace


MAX_CV_BYTES = 5 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 12 * 1024 * 1024
MODES = ("Criteria-based search", "CV-based search")
LIST_SETTINGS = (
    "target_roles", "primary_keywords", "bonus_keywords", "hard_skip_keywords",
    "search_location", "search_platforms", "company_sources", "application_filters",
)
POSTING_AGES = ("Past 24 hours", "Past week", "Past month", "Any time")
BOOL_FIELDS = {"posted_date_verified", "score_limited", "cache_hit"}


class SnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class RestoredAccount:
    workspace: SessionWorkspace = field(repr=False)
    settings: dict[str, object] = field(repr=False)
    mode: str


def encode_snapshot(owner_id: str, workspace: SessionWorkspace, settings: dict[str, object], mode: str) -> str:
    cv = workspace.cv
    if cv is not None and cv.size_bytes > MAX_CV_BYTES:
        raise SnapshotError("Account CVs must be 5 MB or smaller. Replace the CV with a smaller file.")
    raw = {
        "version": 1, "owner_id": owner_id, "mode": mode,
        "settings": _settings(settings),
        "cv": {"filename": cv.filename, "content": base64.b64encode(cv.content).decode(), "text": cv.text} if cv else None,
        "jobs": [asdict(job) for job in workspace.list_jobs()],
    }
    try:
        payload = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError):
        raise SnapshotError("Account data could not be serialized safely.") from None
    decode_snapshot(owner_id, payload)
    return payload


def decode_snapshot(owner_id: str, content: str) -> RestoredAccount:
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise SnapshotError("Account data exceeds the 12 MB storage limit; it has not been saved or replaced.")
    try:
        raw = json.loads(content)
        if (not isinstance(raw, dict) or type(raw.get("version")) is not int or raw["version"] != 1
                or not re.fullmatch(r"[a-f0-9]{64}", owner_id) or raw.get("owner_id") != owner_id
                or raw.get("mode") not in MODES):
            raise ValueError()
        settings = _settings(raw["settings"])
        cv = _cv(raw.get("cv"))
        records = raw["jobs"]
        if not isinstance(records, list) or len(records) > 5000:
            raise ValueError()
        jobs = [_job(record) for record in records]
        if len({job.id for job in jobs}) != len(jobs):
            raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise SnapshotError("Saved account data is invalid or belongs to another account. It has not been replaced.") from None
    return RestoredAccount(SessionWorkspace.from_account(cv, jobs), settings, raw["mode"])


def _settings(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SnapshotError("Account search settings are invalid.")
    result: dict[str, object] = {}
    for name in LIST_SETTINGS:
        selected = value.get(name, [])
        if (not isinstance(selected, list) or len(selected) > 100
                or any(not isinstance(item, str) or not item.strip() or len(item) > 2000 for item in selected)):
            raise SnapshotError("Account search settings require lists of up to 100 text values.")
        result[name] = list(selected)
    age = value.get("posting_age", "Past month")
    if age not in POSTING_AGES:
        raise SnapshotError("Account posting-age setting is invalid.")
    result["posting_age"] = age
    cv_profile_digest = value.get("cv_profile_digest", "")
    if (not isinstance(cv_profile_digest, str)
            or (cv_profile_digest and not re.fullmatch(r"[a-f0-9]{64}", cv_profile_digest))):
        raise SnapshotError("Account CV search profile fingerprint is invalid.")
    result["cv_profile_digest"] = cv_profile_digest
    return result


def _cv(value: object) -> SessionCV | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError()
    filename, text, content = value["filename"], value["text"], value["content"]
    if (not isinstance(filename, str) or not filename or len(filename) > 1024
            or filename.rsplit(".", 1)[-1].casefold() not in {"pdf", "doc", "docx"}
            or not isinstance(text, str) or not text.strip() or not isinstance(content, str)
            or len(content) > (MAX_CV_BYTES + 2) // 3 * 4):
        raise ValueError()
    decoded = base64.b64decode(content, validate=True)
    if not decoded or len(decoded) > MAX_CV_BYTES:
        raise ValueError()
    return SessionCV(filename, decoded, text)


def _job(value: object) -> JobRecord:
    if not isinstance(value, dict) or set(value) != {item.name for item in fields(JobRecord)}:
        raise ValueError()
    for name, item in value.items():
        expected = int if name in {"id", "score"} else bool if name in BOOL_FIELDS else str
        if type(item) is not expected:
            raise ValueError()
    if (not 0 < value["id"] < 2**31 or not 0 <= value["score"] <= 100
            or value["decision"] not in {"shortlist", "review", "reject", "skip"}
            or value["application_status"] not in {"applied", "not_applied"}
            or value["availability"] not in {"unknown", "not_expired", "expired"}):
        raise ValueError()
    return JobRecord(**value)
