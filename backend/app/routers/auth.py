from datetime import datetime, timezone
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models.user import ExperienceLevel, Specialization, User
from app.schemas.auth import (
    PasswordResetEmailRequest,
    PasswordResetRequest,
    Token,
    UserCreate,
    UserCreateResponse,
    UserOut,
    UserSelfUpdate,
)
from app.utils.user_profile import serialize_skills
from app.utils.email_validation import normalize_email, validate_allowed_email
from app.services.audit import record_audit
from app.services.notifications import (
    build_account_created_email,
    build_password_reset_email,
    build_reset_link,
    generate_reset_token,
    generate_temporary_password,
    hash_token,
    reset_token_expiry,
    send_email,
    token_matches,
)

router = APIRouter(prefix="/auth", tags=["auth"])

PROFILE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _parse_optional_enum(value: str | None, enum_cls):
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return enum_cls(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {enum_cls.__name__} value") from exc


def _parse_availability(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Availability must be a number") from exc
    if parsed > 1:
        parsed /= 100
    if parsed < 0 or parsed > 1:
        raise HTTPException(status_code=400, detail="Availability must be between 0 and 100%")
    return round(parsed, 2)


async def _store_profile_image(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in PROFILE_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, or WEBP images are allowed")

    filename = f"{uuid.uuid4().hex}{ext}"
    content = await file.read()
    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, filename)
    with open(filepath, "wb") as handle:
        handle.write(content)
    return f"/uploads/{filename}"


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    email = normalize_email(form_data.username)
    validate_allowed_email(email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    full_name: str | None = Form(None),
    job_title: str | None = Form(None),
    department: str | None = Form(None),
    specialization: str | None = Form(None),
    experience_level: str | None = Form(None),
    skills: str | None = Form(None),
    availability: str | None = Form(None),
    current_password: str | None = Form(None),
    new_password: str | None = Form(None),
    profile_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if new_password:
        if not current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.hashed_password = hash_password(new_password)
        current_user.must_change_password = False

    profile_payload = UserSelfUpdate(
        full_name=full_name,
        job_title=job_title,
        department=department,
        specialization=_parse_optional_enum(specialization, Specialization),
        experience_level=_parse_optional_enum(experience_level, ExperienceLevel),
        skills=serialize_skills(skills) if skills is not None else None,
        availability=_parse_availability(availability),
    )

    if profile_payload.full_name is not None:
        cleaned_name = profile_payload.full_name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail="Full name cannot be empty")
        current_user.full_name = cleaned_name
    if profile_payload.job_title is not None:
        current_user.job_title = profile_payload.job_title
    if profile_payload.department is not None:
        current_user.department = profile_payload.department
    if specialization is not None:
        current_user.specialization = profile_payload.specialization
    if experience_level is not None:
        current_user.experience_level = profile_payload.experience_level
    if skills is not None:
        current_user.skills = profile_payload.skills or []
    if availability is not None:
        current_user.availability = profile_payload.availability

    if profile_image and profile_image.filename:
        current_user.profile_image_path = await _store_profile_image(profile_image)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    token = create_access_token({"sub": str(current_user.id), "role": current_user.role.value})
    return Token(access_token=token, user=UserOut.model_validate(current_user))


@router.post("/register", response_model=UserCreateResponse)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    email = normalize_email(data.email)
    validate_allowed_email(email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    temporary_password = generate_temporary_password()
    reset_token = generate_reset_token()
    user = User(
        email=email,
        hashed_password=hash_password(temporary_password),
        full_name=data.full_name,
        role=data.role,
        job_title=data.job_title,
        team_name=data.team_name,
        team_leader_id=data.team_leader_id,
        department=data.department,
        specialization=data.specialization,
        experience_level=data.experience_level,
        skills=data.skills or [],
        availability=data.availability,
        password_reset_token_hash=hash_token(reset_token),
        password_reset_expires_at=reset_token_expiry(),
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        send_email(
            user.email,
            "Your DeskDibs account is ready",
            build_account_created_email(
                user.full_name,
                user.email,
                temporary_password,
                build_reset_link(reset_token),
            ),
        )
    except Exception as exc:
        print(f"[mail:error] account_created user_id={user.id} email={user.email}: {exc}")

    record_audit(
        db,
        admin_user,
        "create_user",
        "user",
        user.id,
        f"Created {user.email} as {user.role.value}",
    )
    db.commit()

    return UserCreateResponse(
        **UserOut.model_validate(user).model_dump(),
        temporary_password=temporary_password,
    )


@router.post("/forgot-password")
def forgot_password(data: PasswordResetEmailRequest, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    validate_allowed_email(email)
    user = db.query(User).filter(User.email == email).first()

    if user:
        reset_token = generate_reset_token()
        user.password_reset_token_hash = hash_token(reset_token)
        user.password_reset_expires_at = reset_token_expiry()
        db.commit()

        try:
            send_email(
                user.email,
                "Reset your DeskDibs password",
                build_password_reset_email(
                    user.full_name,
                    build_reset_link(reset_token),
                ),
            )
        except Exception as exc:
            print(f"[mail:error] password_reset user_id={user.id} email={user.email}: {exc}")

    return {
        "detail": "If an account exists for that email, a password reset link has been sent.",
    }


@router.post("/reset-password")
def reset_password(data: PasswordResetRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(User)
        .filter(User.password_reset_token_hash.isnot(None))
        .filter(User.password_reset_expires_at.isnot(None))
        .all()
    )
    target_user = next(
        (item for item in candidates if token_matches(data.token, item.password_reset_token_hash)),
        None,
    )
    if not target_user or not target_user.password_reset_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    if target_user.password_reset_expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    target_user.hashed_password = hash_password(data.password)
    target_user.password_reset_token_hash = None
    target_user.password_reset_expires_at = None
    target_user.must_change_password = False
    db.commit()
    return {"detail": "Password updated"}
