from pathlib import Path

from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.floor_plan import FloorPlan
from app.models.resource import Resource, ResourceType
from app.models.user import ExperienceLevel, Specialization, User, UserRole

Base.metadata.create_all(bind=engine)

db = SessionLocal()

DEMO_FLOOR = "1"
DEMO_FLOOR_IMAGE = "02c4e64e12e044f8add5543cfc83607d.jpg"

DEMO_RESOURCES = [
    ("1", ResourceType.desk, "Open Area", 40.49751243781095, 28.751242133156673, 1, "Hot Desk"),
    ("2", ResourceType.desk, "Open Area", 64.87562189054727, 25.571381252070225, 1, "Hot Desk"),
    ("3", ResourceType.desk, "Open Area", 18.109452736318406, 47.30043060616098, 1, "Hot Desk"),
    ("Meeting Room 1", ResourceType.room, "Meeting", 84.74945533769062, 47.88461538461539, 6, "Meeting Room"),
]

DEMO_USERS = [
    {
        "email": "sarah.chen@genpact.com",
        "password": "password123",
        "full_name": "Sarah Chen",
        "role": UserRole.admin,
        "job_title": "Office Manager",
        "team_name": "Platform",
        "department": "Operations",
        "specialization": Specialization.operations,
        "experience_level": ExperienceLevel.senior,
        "skills": ["Facilities", "Vendor Management", "Workplace Planning"],
        "availability": 0.9,
    },
    {
        "email": "alex.morgan@genpact.com",
        "password": "password123",
        "full_name": "Alex Morgan",
        "role": UserRole.team_leader,
        "job_title": "Engineering Team Lead",
        "team_name": "Product",
        "department": "Engineering",
        "specialization": Specialization.backend,
        "experience_level": ExperienceLevel.senior,
        "skills": ["Python", "FastAPI", "System Design", "Leadership", "PostgreSQL"],
        "availability": 0.75,
    },
    {
        "email": "priya.sharma@genpact.com",
        "password": "password123",
        "full_name": "Priya Sharma",
        "role": UserRole.manager,
        "job_title": "Director of Workplace",
        "team_name": "Operations",
        "department": "Operations",
        "specialization": Specialization.product,
        "experience_level": ExperienceLevel.senior,
        "skills": ["Strategy", "Stakeholder Management", "Program Management"],
        "availability": 0.6,
    },
    {
        "email": "jane.smith@genpact.com",
        "password": "password123",
        "full_name": "Jane Smith",
        "role": UserRole.employee,
        "job_title": "Frontend Engineer",
        "team_name": "Product",
        "department": "Engineering",
        "specialization": Specialization.frontend,
        "experience_level": ExperienceLevel.mid,
        "skills": ["React", "TypeScript", "CSS", "Accessibility"],
        "availability": 0.85,
    },
    {
        "email": "marcus.lee@genpact.com",
        "password": "password123",
        "full_name": "Marcus Lee",
        "role": UserRole.employee,
        "job_title": "Senior Backend Engineer",
        "team_name": "Product",
        "department": "Engineering",
        "specialization": Specialization.backend,
        "experience_level": ExperienceLevel.senior,
        "skills": ["Python", "FastAPI", "PostgreSQL", "REST APIs", "Docker"],
        "availability": 0.7,
    },
    {
        "email": "elena.rossi@genpact.com",
        "password": "password123",
        "full_name": "Elena Rossi",
        "role": UserRole.employee,
        "job_title": "ML Engineer",
        "team_name": "Product",
        "department": "Data & AI",
        "specialization": Specialization.ai_ml,
        "experience_level": ExperienceLevel.mid,
        "skills": ["Python", "Machine Learning", "TensorFlow", "NLP", "MLOps"],
        "availability": 0.8,
    },
    {
        "email": "david.kim@genpact.com",
        "password": "password123",
        "full_name": "David Kim",
        "role": UserRole.employee,
        "job_title": "Data Engineer",
        "team_name": "Product",
        "department": "Data & AI",
        "specialization": Specialization.data_engineering,
        "experience_level": ExperienceLevel.senior,
        "skills": ["Python", "Spark", "Airflow", "Data Pipelines", "SQL"],
        "availability": 0.65,
    },
    {
        "email": "sofia.patel@genpact.com",
        "password": "password123",
        "full_name": "Sofia Patel",
        "role": UserRole.employee,
        "job_title": "Data Scientist",
        "team_name": "Product",
        "department": "Data & AI",
        "specialization": Specialization.data_science,
        "experience_level": ExperienceLevel.mid,
        "skills": ["Python", "Statistics", "Machine Learning", "Data Analysis", "Pandas"],
        "availability": 0.9,
    },
    {
        "email": "liam.nguyen@genpact.com",
        "password": "password123",
        "full_name": "Liam Nguyen",
        "role": UserRole.employee,
        "job_title": "Junior Full Stack Developer",
        "team_name": "Product",
        "department": "Engineering",
        "specialization": Specialization.fullstack,
        "experience_level": ExperienceLevel.junior,
        "skills": ["JavaScript", "React", "Node.js", "REST APIs"],
        "availability": 0.95,
    },
    {
        "email": "nina.bauer@genpact.com",
        "password": "password123",
        "full_name": "Nina Bauer",
        "role": UserRole.employee,
        "job_title": "DevOps Engineer",
        "team_name": "Platform",
        "department": "Engineering",
        "specialization": Specialization.devops,
        "experience_level": ExperienceLevel.mid,
        "skills": ["Docker", "Kubernetes", "CI/CD", "AWS", "Terraform"],
        "availability": 0.72,
    },
    {
        "email": "omar.hassan@genpact.com",
        "password": "password123",
        "full_name": "Omar Hassan",
        "role": UserRole.employee,
        "job_title": "QA Engineer",
        "team_name": "Product",
        "department": "Engineering",
        "specialization": Specialization.qa,
        "experience_level": ExperienceLevel.mid,
        "skills": ["Test Automation", "Selenium", "API Testing", "Quality Assurance"],
        "availability": 0.88,
    },
    {
        "email": "rachel.fox@genpact.com",
        "password": "password123",
        "full_name": "Rachel Fox",
        "role": UserRole.employee,
        "job_title": "UX Designer",
        "team_name": "Design",
        "department": "Design",
        "specialization": Specialization.design,
        "experience_level": ExperienceLevel.senior,
        "skills": ["UX Design", "UI Design", "Figma", "User Research", "Prototyping"],
        "availability": 0.78,
    },
]


def _floor_plan_image_path() -> str:
    uploads_dir = Path(settings.upload_dir).resolve()
    image_path = uploads_dir / DEMO_FLOOR_IMAGE
    if not image_path.exists():
        raise FileNotFoundError(
            f"Missing demo floor plan image at {image_path}. "
            "Make sure backend/uploads is checked out from the repo."
        )
    return str(image_path)


for profile in DEMO_USERS:
    user = db.query(User).filter(User.email == profile["email"]).first()
    payload = {
        "hashed_password": hash_password(profile["password"]),
        "full_name": profile["full_name"],
        "role": profile["role"],
        "job_title": profile["job_title"],
        "team_name": profile["team_name"],
        "department": profile["department"],
        "specialization": profile["specialization"],
        "experience_level": profile["experience_level"],
        "skills": profile["skills"],
        "availability": profile["availability"],
        "team_leader_id": None,
    }

    if user:
        for key, value in payload.items():
            setattr(user, key, value)
    else:
        db.add(User(email=profile["email"], **payload))

team_leader = db.query(User).filter(User.email == "alex.morgan@genpact.com").first()
for teammate_email in (
    "jane.smith@genpact.com",
    "marcus.lee@genpact.com",
    "elena.rossi@genpact.com",
    "david.kim@genpact.com",
    "sofia.patel@genpact.com",
    "liam.nguyen@genpact.com",
    "omar.hassan@genpact.com",
):
    teammate = db.query(User).filter(User.email == teammate_email).first()
    if teammate and team_leader:
        teammate.team_leader_id = team_leader.id
        teammate.team_name = team_leader.team_name

image_path = _floor_plan_image_path()
floor_plan = db.query(FloorPlan).filter(FloorPlan.floor == DEMO_FLOOR).first()
if floor_plan:
    floor_plan.name = f"Floor {DEMO_FLOOR}"
    floor_plan.building = "HQ - Prishtina"
    floor_plan.image_path = image_path
else:
    db.add(
        FloorPlan(
            name=f"Floor {DEMO_FLOOR}",
            building="HQ - Prishtina",
            floor=DEMO_FLOOR,
            image_path=image_path,
        )
    )

for name, resource_type, zone, x, y, capacity, desk_type in DEMO_RESOURCES:
    resource = db.query(Resource).filter(Resource.name == name, Resource.floor == DEMO_FLOOR).first()
    if resource:
        resource.type = resource_type
        resource.zone = zone
        resource.floor_plan_x = x
        resource.floor_plan_y = y
        resource.capacity = capacity
        resource.desk_type = desk_type
        resource.building = "HQ - Prishtina"
        resource.is_active = True
    else:
        db.add(
            Resource(
                name=name,
                type=resource_type,
                building="HQ - Prishtina",
                floor=DEMO_FLOOR,
                zone=zone,
                floor_plan_x=x,
                floor_plan_y=y,
                capacity=capacity,
                desk_type=desk_type,
                is_active=True,
            )
        )

db.commit()
db.close()

print("Seed complete (users with profiles, floor plan, and demo resources)")
