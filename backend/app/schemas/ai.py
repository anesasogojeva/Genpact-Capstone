from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class BookingIntentType(StrEnum):
    book_meeting_room = "book_meeting_room"
    book_desk = "book_desk"
    search_meeting_rooms = "search_meeting_rooms"
    search_desks = "search_desks"
    cancel_reservation = "cancel_reservation"
    find_colleague = "find_colleague"


class BookingIntent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: BookingIntentType | None = None
    people: int | None = None
    date: str | None = None
    time: str | None = None
    duration: str | None = None
    equipment: list[str] = Field(default_factory=list)
    preferred_location: str | None = None
    coworker: str | None = None
    book_for: str | None = None
    follow_up_question: str | None = None

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "cancel": "cancel_reservation",
            "cancel_booking": "cancel_reservation",
            "cancel_reservations": "cancel_reservation",
            "book_room": "book_meeting_room",
            "book_meeting_room": "book_meeting_room",
            "reserve_room": "book_meeting_room",
            "reserve_meeting_room": "book_meeting_room",
            "meeting_room": "book_meeting_room",
            "book_desk": "book_desk",
            "reserve_desk": "book_desk",
            "reserve": "book_desk",
            "reservation": "book_desk",
            "book": "book_desk",
            "make_reservation": "book_desk",
            "search_rooms": "search_meeting_rooms",
            "search_desks": "search_desks",
            "find_desk": "search_desks",
            "find_room": "search_meeting_rooms",
            "find_colleague": "find_colleague",
            "colleague_location": "find_colleague",
            "where_is_colleague": "find_colleague",
        }
        return aliases.get(normalized, normalized)

    @field_validator("people", mode="before")
    @classmethod
    def normalize_people(cls, value):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            if cleaned.isdigit():
                return int(cleaned)
            return None
        return None

    @field_validator(
        "date",
        "time",
        "duration",
        "preferred_location",
        "coworker",
        "book_for",
        "follow_up_question",
        mode="before",
    )
    @classmethod
    def normalize_optional_string(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("equipment", mode="before")
    @classmethod
    def normalize_equipment(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def to_chat_response(self) -> "ChatResponse":
        return ChatResponse(**self.model_dump(mode="json"))


class ChatResourceSummary(BaseModel):
    id: int
    name: str
    floor: str
    zone: str
    capacity: int
    is_available: bool = True


class ColleagueLocationSummary(BaseModel):
    name: str
    date: str
    in_office: bool = False
    desk_name: str | None = None
    floor: str | None = None
    zone: str | None = None


class BookingConfirmationFacts(BaseModel):
    room_name: str | None = None
    desk_name: str | None = None
    reservation_id: int
    reservation_date: str


class TeamBuilderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(..., min_length=1, max_length=2000)
    required_skills: list[str] = Field(
        default_factory=list,
        max_length=20,
        alias="requiredSkills",
    )
    team_size: int | None = Field(default=None, ge=2, le=20, alias="teamSize")


class TeamMemberSuggestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    role: str
    skills: list[str] = Field(default_factory=list)
    experience_level: str = Field(default="mid", alias="experienceLevel")
    reason: str

    @field_validator("experience_level", mode="before")
    @classmethod
    def normalize_experience_level(cls, value):
        if value is None:
            return "mid"
        cleaned = str(value).strip().lower()
        if cleaned in {"junior", "mid", "senior"}:
            return cleaned
        return "mid"

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class TeamBuilderResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    team: list[TeamMemberSuggestion] = Field(default_factory=list)
    summary: str
    requested_team_size: int = Field(alias="requestedTeamSize")
    matched_count: int = Field(alias="matchedCount")
    is_partial_match: bool = Field(alias="isPartialMatch")


class EmergencyStaffingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_name: str = Field(..., min_length=1, max_length=200, alias="projectName")
    problem: str = Field(..., min_length=1, max_length=2000)
    required_skills: list[str] = Field(
        default_factory=list,
        max_length=20,
        alias="requiredSkills",
    )
    needed_people: int | None = Field(default=3, ge=1, le=10, alias="neededPeople")


class EmergencyStaffingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommended_people: list[TeamMemberSuggestion] = Field(
        default_factory=list,
        alias="recommendedPeople",
    )
    summary: str
    urgency_reason: str = Field(alias="urgencyReason")


class ChatResponse(BaseModel):
    intent: str | None = None
    people: int | None = None
    date: str | None = None
    time: str | None = None
    duration: str | None = None
    equipment: list[str] = Field(default_factory=list)
    preferred_location: str | None = None
    coworker: str | None = None
    book_for: str | None = None
    follow_up_question: str | None = None
    action: str | None = None
    reservation_id: int | None = None
    reservation_date: str | None = None
    room_name: str | None = None
    desk_name: str | None = None
    confirmation: str | None = None
    resources: list[ChatResourceSummary] = Field(default_factory=list)
    colleagues: list[ColleagueLocationSummary] = Field(default_factory=list)
