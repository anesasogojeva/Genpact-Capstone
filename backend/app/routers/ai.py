from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.ai import ChatRequest, ChatResponse
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
