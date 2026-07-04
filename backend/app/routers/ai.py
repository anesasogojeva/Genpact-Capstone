from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_manager_or_admin
from app.database import get_db
from app.models.user import User
from app.ai.controllers.team_builder import build_team
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    TeamBuilderRequest,
    TeamBuilderResponse,
    EmergencyStaffingRequest,
    EmergencyStaffingResponse,
)
from app.services.ai_chat import generate_chat_reply
from app.services.huggingface import generate_hf_response

router = APIRouter(prefix="/ai", tags=["ai"])

TEST_PROMPT = (
    'Extract intent JSON for: "Book a meeting room for 6 people tomorrow at 15:00 with a projector"'
)


@router.get("/test", response_class=PlainTextResponse)
def test_hf():
    return generate_hf_response(TEST_PROMPT)


@router.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    history = [{"role": item.role, "content": item.content} for item in data.history]
    return generate_chat_reply(db, current_user, data.message.strip(), history)


@router.post("/team-builder", response_model=TeamBuilderResponse, response_model_by_alias=True)
def team_builder(
    data: TeamBuilderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    return build_team(data, db, current_user)


@router.post(
    "/emergency-staffing",
    response_model=EmergencyStaffingResponse,
    response_model_by_alias=True,
)
def emergency_staffing(
    data: EmergencyStaffingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    prompt = (
        f"Emergency staffing needed for project: {data.project_name}. "
        f"Problem: {data.problem}. "
        f"Suggest temporary employees who can help quickly."
    )

    result = build_team(
        TeamBuilderRequest(
            prompt=prompt,
            requiredSkills=data.required_skills,
            teamSize=data.needed_people,
        ),
        db,
        current_user,
    )

    return EmergencyStaffingResponse(
        recommendedPeople=result.team,
        summary=result.summary,
        urgencyReason=f"Project '{data.project_name}' needs urgent help because: {data.problem}",
    )