from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import ExperienceLevel, Specialization, UserRole
from app.utils.user_profile import parse_skills, serialize_skills


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, value: str) -> str:
        return _normalize_email(value)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.employee
    job_title: str | None = None
    team_name: str | None = None
    team_leader_id: int | None = None
    department: str | None = None
    specialization: Specialization | None = None
    experience_level: ExperienceLevel | None = None
    skills: list[str] = Field(default_factory=list)
    availability: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        return serialize_skills(value)

    @field_validator("department", "job_title", "team_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    job_title: str | None = None
    team_name: str | None = None
    team_leader_id: int | None = None
    profile_image_path: str | None = None
    department: str | None = None
    specialization: Specialization | None = None
    experience_level: ExperienceLevel | None = None
    skills: list[str] | None = None
    availability: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        if value is None:
            return None
        return serialize_skills(value)

    @field_validator("department", "job_title", "team_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class UserSelfUpdate(BaseModel):
    full_name: str | None = None
    job_title: str | None = None
    department: str | None = None
    specialization: Specialization | None = None
    experience_level: ExperienceLevel | None = None
    skills: list[str] | None = None
    availability: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        if value is None:
            return None
        return serialize_skills(value)

    @field_validator("department", "job_title", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class PasswordResetRequest(BaseModel):
    token: str
    password: str


class PasswordResetEmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    job_title: str | None = None
    team_name: str | None = None
    department: str | None = None
    specialization: Specialization | None = None
    experience_level: ExperienceLevel | None = None
    skills: list[str] = Field(default_factory=list)
    availability: float | None = None
    profile_image_path: str | None = None
    team_leader_id: int | None = None

    model_config = {"from_attributes": True}

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        return parse_skills(value)


class UserCreateResponse(UserOut):
    temporary_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
