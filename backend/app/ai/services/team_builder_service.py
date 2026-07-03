from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.prompts.team_builder_prompt import TEAM_BUILDER_SYSTEM_PROMPT
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User, UserRole
from app.schemas.ai import TeamBuilderResponse, TeamMemberSuggestion
from app.services.huggingface import generate_hf_chat
from app.utils.user_profile import (
    resolve_availability,
    user_experience_level,
    user_skills,
    user_specialization,
)

EXPERIENCE_RANK = {"senior": 3, "mid": 2, "junior": 1}

SKILL_ALIASES: dict[str, list[str]] = {
    "node.js": ["node", "nodejs", "javascript"],
    "react": ["frontend", "javascript"],
    "ui/ux": ["ux", "ui", "design", "figma"],
    "ux": ["ux design", "ui design", "design"],
    "ui": ["ux design", "ui design", "design"],
    "machine learning": ["ml", "ai", "tensorflow"],
    "python": ["django", "fastapi", "flask"],
}


@dataclass
class EmployeeCandidate:
    id: int
    name: str
    email: str
    job_title: str
    department: str | None
    specialization: str | None
    team_name: str | None
    access_role: str
    skills: list[str]
    experience_level: str
    availability_score: float
    skill_match_count: int


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _skill_tokens(skill: str) -> set[str]:
    normalized = _normalize_token(skill)
    tokens = {normalized}
    for part in re.split(r"[/,&+]", normalized):
        cleaned = part.strip()
        if cleaned:
            tokens.add(cleaned)
    for word in normalized.split():
        tokens.add(word)
    for alias in SKILL_ALIASES.get(normalized, []):
        tokens.add(alias)
    return tokens


def _candidate_skill_tokens(candidate_skills: list[str]) -> set[str]:
    tokens: set[str] = set()
    for skill in candidate_skills:
        tokens.update(_skill_tokens(skill))
        for word in _normalize_token(skill).split():
            tokens.add(word)
    return tokens


def _skills_match(required_skill: str, candidate_skills: list[str]) -> bool:
    required_tokens = _skill_tokens(required_skill)
    candidate_tokens = _candidate_skill_tokens(candidate_skills)

    for required in required_tokens:
        for candidate in candidate_tokens:
            if required in candidate or candidate in required:
                return True
    return False


def _matched_required_skills(candidate_skills: list[str], required_skills: list[str]) -> list[str]:
    return [skill for skill in required_skills if _skills_match(skill, candidate_skills)]


def _extract_skills_from_text(text: str, known_skills: list[str]) -> list[str]:
    normalized = _normalize_token(text)
    found: set[str] = set()

    for skill in known_skills:
        token = _normalize_token(skill)
        if token and token in normalized:
            found.add(skill)

    keyword_map = {
        "frontend": "React",
        "backend": "Python",
        "node.js": "Node.js",
        "nodejs": "Node.js",
        "ui/ux": "UI/UX",
        "ux": "UX Design",
        "ai": "Machine Learning",
        "ml": "Machine Learning",
        "machine learning": "Machine Learning",
        "data": "Data Analysis",
        "devops": "DevOps",
    }
    for keyword, skill in keyword_map.items():
        if keyword in normalized:
            found.add(skill)

    return sorted(found)


def _skill_match_count(candidate_skills: list[str], required_skills: list[str]) -> int:
    if not required_skills:
        return 0
    return len(_matched_required_skills(candidate_skills, required_skills))


def _matches_required_skills(
    candidate: EmployeeCandidate,
    required_skills: list[str],
) -> bool:
    if not required_skills:
        return True

    if _skill_match_count(candidate.skills, required_skills) > 0:
        return True

    searchable = " ".join(
        [
            candidate.job_title,
            candidate.access_role,
            candidate.department or "",
            candidate.specialization or "",
            candidate.team_name or "",
            " ".join(candidate.skills),
        ]
    ).lower()

    for required in required_skills:
        for token in _skill_tokens(required):
            if token in searchable:
                return True

    return False


def _fetch_reservation_availability(db: Session, user_ids: list[int]) -> dict[int, float]:
    if not user_ids:
        return {}

    today = date.today()
    window_end = today + timedelta(days=14)

    rows = (
        db.query(Reservation.user_id, func.count(Reservation.id))
        .filter(
            Reservation.user_id.in_(user_ids),
            Reservation.status == ReservationStatus.active,
            Reservation.date >= today,
            Reservation.date <= window_end,
        )
        .group_by(Reservation.user_id)
        .all()
    )

    counts = {user_id: count for user_id, count in rows}
    scores: dict[int, float] = {}
    for user_id in user_ids:
        reservation_count = counts.get(user_id, 0)
        scores[user_id] = round(max(0.1, 1.0 - (reservation_count / 10)), 2)
    return scores


def _load_candidates(db: Session) -> list[EmployeeCandidate]:
    users = (
        db.query(User)
        .filter(User.role.in_([UserRole.employee, UserRole.team_leader, UserRole.manager]))
        .order_by(User.full_name)
        .all()
    )

    reservation_availability = _fetch_reservation_availability(db, [user.id for user in users])

    candidates: list[EmployeeCandidate] = []
    for user in users:
        skills = user_skills(user)
        reservation_score = reservation_availability.get(user.id, 1.0)
        candidates.append(
            EmployeeCandidate(
                id=user.id,
                name=user.full_name,
                email=user.email,
                job_title=user.job_title or "Employee",
                department=user.department,
                specialization=user_specialization(user),
                team_name=user.team_name,
                access_role=user.role.value,
                skills=skills,
                experience_level=user_experience_level(user),
                availability_score=resolve_availability(user, reservation_score),
                skill_match_count=0,
            )
        )
    return candidates


def rank_candidates(
    candidates: list[EmployeeCandidate],
    *,
    required_skills: list[str],
    team_size: int,
) -> list[EmployeeCandidate]:
    normalized_required = [skill.strip() for skill in required_skills if skill.strip()]

    ranked: list[EmployeeCandidate] = []
    for candidate in candidates:
        if not candidate.skills:
            continue
        if not _matches_required_skills(candidate, normalized_required):
            continue

        candidate.skill_match_count = _skill_match_count(candidate.skills, normalized_required)
        ranked.append(candidate)

    if not ranked:
        ranked = [candidate for candidate in candidates if candidate.skills]
        for candidate in ranked:
            candidate.skill_match_count = _skill_match_count(candidate.skills, normalized_required)

    ranked.sort(
        key=lambda item: (
            item.skill_match_count,
            EXPERIENCE_RANK.get(item.experience_level, 0),
            item.availability_score,
        ),
        reverse=True,
    )

    limit = min(max(team_size * 3, 12), 30)
    return ranked[:limit]


def _build_user_message(
    *,
    prompt: str,
    required_skills: list[str],
    team_size: int,
    candidates: list[EmployeeCandidate],
) -> str:
    skills_text = ", ".join(required_skills) if required_skills else "Infer from the project prompt"
    available_count = len(candidates)
    candidate_lines = []
    for candidate in candidates:
        candidate_lines.append(
            "- "
            f"{candidate.name} | access_role={candidate.access_role} | title={candidate.job_title} | "
            f"department={candidate.department or 'Unassigned'} | "
            f"specialization={candidate.specialization or 'general'} | "
            f"team={candidate.team_name or 'Unassigned'} | "
            f"experience={candidate.experience_level} | "
            f"availability={candidate.availability_score} | "
            f"skills={', '.join(candidate.skills)}"
        )

    return (
        f"Project request: {prompt}\n"
        f"Required skills: {skills_text}\n"
        f"Target team size: {team_size}\n"
        f"Available matching candidates in pool: {available_count}\n\n"
        "Candidate pool (select only from this list):\n"
        + "\n".join(candidate_lines)
    )


def _json_candidates(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []

    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        sliced = text[start : end + 1]
        if sliced != text:
            candidates.append(sliced)
    return candidates


def _candidate_lookup(candidates: list[EmployeeCandidate]) -> dict[str, EmployeeCandidate]:
    lookup: dict[str, EmployeeCandidate] = {}
    for candidate in candidates:
        lookup[_normalize_token(candidate.name)] = candidate
    return lookup


def _resolve_candidate(name: str, lookup: dict[str, EmployeeCandidate]) -> EmployeeCandidate | None:
    cleaned = _normalize_token(name)
    if cleaned in lookup:
        return lookup[cleaned]

    for key, candidate in lookup.items():
        if cleaned in key or key in cleaned:
            return candidate
    return None


def _member_reason(candidate: EmployeeCandidate, required_skills: list[str]) -> str:
    matched = _matched_required_skills(candidate.skills, required_skills)
    parts: list[str] = []
    if matched:
        parts.append(f"Matches required skills: {', '.join(matched)}.")
    parts.append(
        f"{candidate.experience_level.capitalize()}-level {candidate.job_title}"
        f" ({candidate.specialization or 'general'})."
    )
    if candidate.availability_score >= 0.8:
        parts.append("High availability.")
    return " ".join(parts)


def _missing_skill_summary(required_skills: list[str], selected: list[EmployeeCandidate]) -> str:
    if not required_skills:
        return ""

    covered: set[str] = set()
    for candidate in selected:
        covered.update(_matched_required_skills(candidate.skills, required_skills))

    missing = [skill for skill in required_skills if skill not in covered]
    if not missing:
        return "All requested skills are covered by the recommended team."
    return f"Skill gaps remain for: {', '.join(missing)}."


def _build_partial_summary(
    *,
    selected_count: int,
    requested_team_size: int,
    required_skills: list[str],
    selected: list[EmployeeCandidate],
    extra: str | None = None,
) -> str:
    parts: list[str] = []
    if selected_count < requested_team_size:
        parts.append(
            f"Only {selected_count} of {requested_team_size} requested team members could be matched "
            f"from current employee profiles."
        )
    else:
        parts.append(
            f"Recommended team of {selected_count} members based on skills, experience, and availability."
        )

    parts.append(_missing_skill_summary(required_skills, selected))
    if extra:
        parts.append(extra.strip())
    return " ".join(part for part in parts if part)


def _build_team_from_candidates(
    ranked: list[EmployeeCandidate],
    *,
    team_size: int,
    required_skills: list[str],
    summary_extra: str | None = None,
) -> TeamBuilderResponse:
    selected = ranked[:team_size]
    matched_count = len(selected)
    is_partial = matched_count < team_size

    team = [
        TeamMemberSuggestion(
            name=candidate.name,
            role=candidate.job_title,
            skills=candidate.skills,
            experienceLevel=candidate.experience_level,
            reason=_member_reason(candidate, required_skills),
        )
        for candidate in selected
    ]

    summary = _build_partial_summary(
        selected_count=matched_count,
        requested_team_size=team_size,
        required_skills=required_skills,
        selected=selected,
        extra=summary_extra,
    )

    return TeamBuilderResponse(
        team=team,
        summary=summary,
        requestedTeamSize=team_size,
        matchedCount=matched_count,
        isPartialMatch=is_partial,
    )


def _normalize_ai_member(member: object, lookup: dict[str, EmployeeCandidate]) -> TeamMemberSuggestion | None:
    if not isinstance(member, dict):
        return None

    name = str(member.get("name") or "").strip()
    if not name:
        return None

    candidate = _resolve_candidate(name, lookup)
    if not candidate:
        return None

    raw_skills = member.get("skills")
    skills = candidate.skills
    if isinstance(raw_skills, list) and raw_skills:
        parsed = [str(item).strip() for item in raw_skills if str(item).strip()]
        if parsed:
            skills = parsed

    experience = member.get("experienceLevel", member.get("experience_level", candidate.experience_level))
    reason = str(member.get("reason") or "").strip() or _member_reason(candidate, [])

    return TeamMemberSuggestion(
        name=candidate.name,
        role=str(member.get("role") or candidate.job_title).strip() or candidate.job_title,
        skills=skills,
        experienceLevel=str(experience).strip().lower() if experience else candidate.experience_level,
        reason=reason,
    )


def _parse_team_builder_response(
    raw: str,
    *,
    ranked: list[EmployeeCandidate],
    team_size: int,
    required_skills: list[str],
) -> TeamBuilderResponse | None:
    lookup = _candidate_lookup(ranked)

    for candidate in _json_candidates(raw):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        raw_team = payload.get("team")
        if not isinstance(raw_team, list):
            continue

        team: list[TeamMemberSuggestion] = []
        seen_names: set[str] = set()
        for member in raw_team:
            normalized = _normalize_ai_member(member, lookup)
            if not normalized:
                continue
            key = _normalize_token(normalized.name)
            if key in seen_names:
                continue
            seen_names.add(key)
            team.append(normalized)
            if len(team) >= team_size:
                break

        if not team:
            continue

        selected_candidates = [
            lookup[_normalize_token(member.name)]
            for member in team
            if _normalize_token(member.name) in lookup
        ]
        ai_summary = str(payload.get("summary") or "").strip()
        summary = _build_partial_summary(
            selected_count=len(team),
            requested_team_size=team_size,
            required_skills=required_skills,
            selected=selected_candidates,
            extra=ai_summary,
        )

        return TeamBuilderResponse(
            team=team,
            summary=summary,
            requestedTeamSize=team_size,
            matchedCount=len(team),
            isPartialMatch=len(team) < team_size,
        )

    return None


def build_project_team(
    db: Session,
    *,
    prompt: str,
    required_skills: list[str] | None = None,
    team_size: int | None = None,
) -> TeamBuilderResponse:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    resolved_team_size = team_size or 5
    resolved_skills = [
        skill.strip()
        for skill in (required_skills or [])
        if isinstance(skill, str) and skill.strip()
    ]

    all_candidates = _load_candidates(db)
    if not all_candidates:
        raise HTTPException(status_code=404, detail="No employees found to build a team")

    known_skills = sorted({skill for candidate in all_candidates for skill in candidate.skills})
    if not resolved_skills:
        resolved_skills = _extract_skills_from_text(cleaned_prompt, known_skills)

    ranked_candidates = rank_candidates(
        all_candidates,
        required_skills=resolved_skills,
        team_size=resolved_team_size,
    )

    if not ranked_candidates:
        raise HTTPException(
            status_code=404,
            detail=(
                "No employees matched the required skills. "
                "Update user profiles in Admin → Users or broaden the skill requirements."
            ),
        )

    selectable_count = min(len(ranked_candidates), resolved_team_size)
    if selectable_count == 0:
        raise HTTPException(status_code=404, detail="No suitable employees found for this request.")

    user_message = _build_user_message(
        prompt=cleaned_prompt,
        required_skills=resolved_skills,
        team_size=resolved_team_size,
        candidates=ranked_candidates,
    )

    try:
        raw_response = generate_hf_chat(
            system_prompt=TEAM_BUILDER_SYSTEM_PROMPT,
            user_message=user_message,
        )
        parsed = _parse_team_builder_response(
            raw_response,
            ranked=ranked_candidates,
            team_size=resolved_team_size,
            required_skills=resolved_skills,
        )
        if parsed:
            return parsed
    except HTTPException:
        raise
    except Exception:
        pass

    return _build_team_from_candidates(
        ranked_candidates,
        team_size=resolved_team_size,
        required_skills=resolved_skills,
        summary_extra="Recommendations were generated from ranked employee profiles.",
    )
