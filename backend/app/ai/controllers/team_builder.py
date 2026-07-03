from sqlalchemy.orm import Session

from app.ai.services.team_builder_service import build_project_team
from app.models.user import User
from app.schemas.ai import TeamBuilderRequest, TeamBuilderResponse


def build_team(
    data: TeamBuilderRequest,
    db: Session,
    current_user: User,
) -> TeamBuilderResponse:
    _ = current_user
    return build_project_team(
        db,
        prompt=data.prompt,
        required_skills=data.required_skills,
        team_size=data.team_size,
    )
