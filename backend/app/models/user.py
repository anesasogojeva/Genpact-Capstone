import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserRole(str, enum.Enum):
    employee = "employee"
    team_leader = "team_leader"
    manager = "manager"
    admin = "admin"


class ExperienceLevel(str, enum.Enum):
    junior = "junior"
    mid = "mid"
    senior = "senior"


class Specialization(str, enum.Enum):
    frontend = "frontend"
    backend = "backend"
    fullstack = "fullstack"
    ai_ml = "ai_ml"
    data_engineering = "data_engineering"
    data_science = "data_science"
    devops = "devops"
    qa = "qa"
    design = "design"
    product = "product"
    operations = "operations"
    general = "general"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.employee)
    full_name: Mapped[str] = mapped_column(String(255))
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    specialization: Mapped[Specialization | None] = mapped_column(
        Enum(Specialization), nullable=True
    )
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        Enum(ExperienceLevel), nullable=True
    )
    skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    availability: Mapped[float | None] = mapped_column(Float, nullable=True)
    profile_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_leader_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(default=False)

    reservations = relationship("Reservation", back_populates="user")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    teammates = relationship(
        "User",
        back_populates="team_leader",
        cascade="all",
        foreign_keys="User.team_leader_id",
    )
    team_leader = relationship(
        "User",
        back_populates="teammates",
        remote_side="User.id",
        foreign_keys=[team_leader_id],
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"
