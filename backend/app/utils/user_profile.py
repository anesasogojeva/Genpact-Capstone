import json
from typing import Any

from app.models.user import ExperienceLevel, Specialization, User


SPECIALIZATION_LABELS: dict[str, str] = {
    Specialization.frontend.value: "Frontend",
    Specialization.backend.value: "Backend",
    Specialization.fullstack.value: "Full Stack",
    Specialization.ai_ml.value: "AI / ML",
    Specialization.data_engineering.value: "Data Engineering",
    Specialization.data_science.value: "Data Science",
    Specialization.devops.value: "DevOps",
    Specialization.qa.value: "QA / Testing",
    Specialization.design.value: "Design",
    Specialization.product.value: "Product",
    Specialization.operations.value: "Operations",
    Specialization.general.value: "General",
}


def parse_skills(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return []
        if cleaned.startswith("["):
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in cleaned.split(",") if part.strip()]
    return []


def serialize_skills(skills: list[str] | None) -> list[str]:
    return parse_skills(skills)


def user_skills(user: User) -> list[str]:
    return parse_skills(user.skills)


def user_experience_level(user: User) -> str:
    if user.experience_level:
        return user.experience_level.value
    return ExperienceLevel.mid.value


def user_specialization(user: User) -> str | None:
    if user.specialization:
        return user.specialization.value
    return None


def resolve_availability(user: User, reservation_score: float) -> float:
    if user.availability is not None:
        return round(float(user.availability), 2)
    return reservation_score
