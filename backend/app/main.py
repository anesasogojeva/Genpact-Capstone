import logging
import os
from pathlib import Path

from sqlalchemy import inspect, text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.auth import hash_password
from app.config import settings
from app.database import Base, engine
from app.models import AuditLog, Favorite, FloorPlan, Reservation, Resource, User
from app.models.user import UserRole
from app.routers import ai, analytics, audit, auth, floor_plans, reservations, resources, users

logger = logging.getLogger(__name__)

try:
    os.makedirs(settings.upload_dir, exist_ok=True)
except OSError as exc:
    logger.warning("Upload directory unavailable: %s", exc)

app = FastAPI(title="DeskDibs API", version="1.0.0")
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(floor_plans.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(users.router, prefix="/api")


def _column_names(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(conn, table_name: str, column_name: str, column_definition: str):
    if column_name not in _column_names(conn, table_name):
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"))


def _ensure_database_schema():
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TYPE resourcetype ADD VALUE IF NOT EXISTS 'amenity'"))

    Base.metadata.create_all(bind=engine)

    dialect = engine.dialect.name
    is_sqlite = dialect == "sqlite"
    with engine.begin() as conn:
        if not is_sqlite:
            conn.execute(text("ALTER TABLE reservations DROP CONSTRAINT IF EXISTS uq_resource_date"))

        _add_column_if_missing(conn, "users", "team_name", "VARCHAR(150)")
        _add_column_if_missing(conn, "users", "team_leader_id", "INTEGER")
        _add_column_if_missing(conn, "users", "password_reset_token_hash", "VARCHAR(255)")
        _add_column_if_missing(
            conn,
            "users",
            "password_reset_expires_at",
            "DATETIME" if is_sqlite else "TIMESTAMP WITH TIME ZONE",
        )
        _add_column_if_missing(
            conn,
            "users",
            "must_change_password",
            "BOOLEAN DEFAULT 0" if is_sqlite else "BOOLEAN DEFAULT false",
        )
        _add_column_if_missing(conn, "users", "profile_image_path", "VARCHAR(255)")
        _add_column_if_missing(conn, "users", "department", "VARCHAR(120)")
        _add_column_if_missing(conn, "users", "specialization", "VARCHAR(50)")
        _add_column_if_missing(conn, "users", "experience_level", "VARCHAR(20)")
        _add_column_if_missing(
            conn,
            "users",
            "skills",
            "TEXT" if is_sqlite else "JSONB",
        )
        _add_column_if_missing(conn, "users", "availability", "REAL")

        _add_column_if_missing(conn, "reservations", "start_time", "TIME")
        _add_column_if_missing(conn, "reservations", "end_time", "TIME")

        _add_column_if_missing(
            conn,
            "resources",
            "building",
            "VARCHAR(120) DEFAULT 'HQ - Prishtina'",
        )
        conn.execute(text("UPDATE resources SET building = 'HQ - Prishtina' WHERE building IS NULL"))
        _add_column_if_missing(
            conn,
            "resources",
            "restricted_to_team_leaders",
            "BOOLEAN DEFAULT 0" if is_sqlite else "BOOLEAN DEFAULT false",
        )

        _add_column_if_missing(conn, "floor_plans", "name", "VARCHAR(150)")
        conn.execute(text("UPDATE floor_plans SET name = 'Floor ' || floor WHERE name IS NULL"))

        if is_sqlite and "image_path" in _column_names(conn, "floor_plans"):
            plans = conn.execute(text("SELECT id, image_path FROM floor_plans")).fetchall()
            uploads_dir = Path(settings.upload_dir).resolve()
            for plan_id, image_path in plans:
                if not image_path or image_path.startswith(("http://", "https://")):
                    continue
                path = Path(image_path)
                resolved = (uploads_dir / path.name).resolve() if not path.is_absolute() else path
                if not resolved.exists():
                    local_copy = (uploads_dir / path.name).resolve()
                    if local_copy.exists():
                        resolved = local_copy
                if resolved.exists() and str(resolved) != image_path:
                    conn.execute(
                        text("UPDATE floor_plans SET image_path = :path WHERE id = :id"),
                        {"path": str(resolved), "id": plan_id},
                    )


def _ensure_initial_admin():
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return

    from app.database import SessionLocal

    email = settings.initial_admin_email.strip().lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            if user.role != UserRole.admin:
                user.role = UserRole.admin
                db.commit()
            return

        db.add(
            User(
                email=email,
                hashed_password=hash_password(settings.initial_admin_password),
                full_name=settings.initial_admin_name,
                role=UserRole.admin,
                job_title="Office Manager",
            )
        )
        db.commit()


@app.on_event("startup")
def startup():
    if not settings.database_configured:
        raise RuntimeError("DATABASE_URL must be set to the Supabase Postgres connection string")
    if settings.using_sqlite:
        raise RuntimeError("SQLite is disabled for this deployment; set DATABASE_URL to Supabase Postgres")

    try:
        _ensure_database_schema()
    except Exception as exc:
        logger.exception("Database initialization failed: %s", exc)
        return

    _ensure_initial_admin()


@app.get("/")
def root():
    return {
        "name": "DeskDibs API",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    database_status = "not_configured"
    if settings.database_configured:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_status = "ok"
    return {
        "status": "ok",
        "database_configured": settings.database_configured,
        "database": database_status,
        "dialect": engine.dialect.name,
    }
