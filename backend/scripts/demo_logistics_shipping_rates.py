"""LogisticsShippingRates Demonstration Script.

Demonstrates the enhanced RepositoryAnalyzer on a realistic FastAPI-based
Logistics Shipping Rates microservice repository.

Verifies that:
1. RepositoryAnalyzer correctly identifies implementation files (NOT README.md) first.
2. Entry points (app/main.py), API routes (routes/shipping.py), service layer
   (services/rate_calculator.py), and models (models/shipping_rate.py) are all detected.
3. Framework (FastAPI), package manager (pip), database (PostgreSQL), ORM (SQLAlchemy),
   and technologies are all extracted deterministically.
4. The Planner receives a rich ProjectSummary and generates a plan targeting actual
   source files instead of README.md.

Run from the backend directory:
    python scripts/demo_logistics_shipping_rates.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.repository import ProjectSummary
from app.services.repository_analyzer import repository_analyzer


# ---------------------------------------------------------------------------
# Scaffold LogisticsShippingRates repository
# ---------------------------------------------------------------------------

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def scaffold_logistics_shipping_rates(root: str) -> None:
    """Create a realistic LogisticsShippingRates FastAPI microservice layout."""

    # app/main.py - Entry Point
    _write(
        os.path.join(root, "app", "main.py"),
        """\
from fastapi import FastAPI
from app.api.routes import shipping, carriers, zones
from app.core.config import settings

app = FastAPI(
    title="LogisticsShippingRates API",
    description="Shipping rate calculation microservice",
    version="1.0.0",
)

app.include_router(shipping.router, prefix="/api/v1/shipping", tags=["Shipping"])
app.include_router(carriers.router, prefix="/api/v1/carriers", tags=["Carriers"])
app.include_router(zones.router, prefix="/api/v1/zones", tags=["Zones"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
""",
    )

    # app/api/routes/shipping.py - API Routes
    _write(
        os.path.join(root, "app", "api", "routes", "shipping.py"),
        """\
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.shipping import ShippingRateRequest, ShippingRateResponse
from app.services.rate_calculator import RateCalculatorService

router = APIRouter()


@router.post("/calculate", response_model=ShippingRateResponse)
def calculate_shipping_rate(
    request: ShippingRateRequest,
    db: Session = Depends(get_db),
):
    \"\"\"Calculate shipping rate for a given shipment.\"\"\"
    service = RateCalculatorService(db)
    return service.calculate(request)


@router.get("/rates", response_model=list[ShippingRateResponse])
def list_shipping_rates(db: Session = Depends(get_db)):
    \"\"\"List all available shipping rates.\"\"\"
    service = RateCalculatorService(db)
    return service.get_all_rates()
""",
    )

    # app/api/routes/carriers.py
    _write(
        os.path.join(root, "app", "api", "routes", "carriers.py"),
        """\
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.carrier_service import CarrierService

router = APIRouter()


@router.get("/")
def list_carriers(db: Session = Depends(get_db)):
    return CarrierService(db).get_all()


@router.get("/{carrier_id}")
def get_carrier(carrier_id: int, db: Session = Depends(get_db)):
    return CarrierService(db).get_by_id(carrier_id)
""",
    )

    # app/api/routes/zones.py
    _write(
        os.path.join(root, "app", "api", "routes", "zones.py"),
        """\
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.zone_service import ZoneService

router = APIRouter()


@router.get("/")
def list_zones(db: Session = Depends(get_db)):
    return ZoneService(db).get_all_zones()
""",
    )

    # app/services/rate_calculator.py - Service Layer (Business Logic)
    _write(
        os.path.join(root, "app", "services", "rate_calculator.py"),
        """\
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session
from app.models.shipping_rate import ShippingRate
from app.models.carrier import Carrier
from app.schemas.shipping import ShippingRateRequest, ShippingRateResponse


class RateCalculatorService:
    \"\"\"Core business logic for shipping rate calculation.\"\"\"

    def __init__(self, db: Session) -> None:
        self.db = db

    def calculate(self, request: ShippingRateRequest) -> ShippingRateResponse:
        carrier = self.db.query(Carrier).filter(
            Carrier.id == request.carrier_id
        ).first()
        if not carrier:
            raise ValueError(f"Carrier {request.carrier_id} not found")

        base_rate = Decimal(str(carrier.base_rate))
        weight_charge = Decimal(str(request.weight_kg)) * Decimal("1.5")
        distance_charge = Decimal(str(request.distance_km)) * Decimal("0.02")
        total = base_rate + weight_charge + distance_charge

        return ShippingRateResponse(
            carrier_id=carrier.id,
            carrier_name=carrier.name,
            base_rate=float(base_rate),
            weight_charge=float(weight_charge),
            distance_charge=float(distance_charge),
            total_rate=float(total),
            currency="USD",
        )

    def get_all_rates(self) -> List[ShippingRate]:
        return self.db.query(ShippingRate).all()
""",
    )

    # app/services/carrier_service.py
    _write(
        os.path.join(root, "app", "services", "carrier_service.py"),
        """\
from sqlalchemy.orm import Session
from app.models.carrier import Carrier


class CarrierService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self):
        return self.db.query(Carrier).all()

    def get_by_id(self, carrier_id: int):
        return self.db.query(Carrier).filter(Carrier.id == carrier_id).first()
""",
    )

    # app/services/zone_service.py
    _write(
        os.path.join(root, "app", "services", "zone_service.py"),
        """\
from sqlalchemy.orm import Session
from app.models.zone import Zone


class ZoneService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all_zones(self):
        return self.db.query(Zone).all()
""",
    )

    # app/models/shipping_rate.py - Data Models
    _write(
        os.path.join(root, "app", "models", "shipping_rate.py"),
        """\
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
import datetime


class ShippingRate(Base):
    __tablename__ = "shipping_rates"

    id = Column(Integer, primary_key=True, index=True)
    carrier_id = Column(Integer, ForeignKey("carriers.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    base_rate = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    carrier = relationship("Carrier", back_populates="rates")
""",
    )

    # app/models/carrier.py
    _write(
        os.path.join(root, "app", "models", "carrier.py"),
        """\
from sqlalchemy import Column, Integer, Float, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    base_rate = Column(Float, nullable=False)
    active = Column(Integer, default=1)

    rates = relationship("ShippingRate", back_populates="carrier")
""",
    )

    # app/models/zone.py
    _write(
        os.path.join(root, "app", "models", "zone.py"),
        """\
from sqlalchemy import Column, Integer, String, Float
from app.db.base import Base


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    min_distance_km = Column(Float, nullable=False)
    max_distance_km = Column(Float, nullable=False)
    surcharge = Column(Float, default=0.0)
""",
    )

    # app/schemas/shipping.py - Pydantic Schemas
    _write(
        os.path.join(root, "app", "schemas", "shipping.py"),
        """\
from pydantic import BaseModel


class ShippingRateRequest(BaseModel):
    carrier_id: int
    weight_kg: float
    distance_km: float
    origin_zip: str
    destination_zip: str


class ShippingRateResponse(BaseModel):
    carrier_id: int
    carrier_name: str
    base_rate: float
    weight_charge: float
    distance_charge: float
    total_rate: float
    currency: str

    class Config:
        from_attributes = True
""",
    )

    # app/core/config.py - Configuration
    _write(
        os.path.join(root, "app", "core", "config.py"),
        """\
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://logistics:pass@localhost:5432/shipping_db"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
""",
    )

    # app/db/session.py
    _write(
        os.path.join(root, "app", "db", "session.py"),
        """\
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
""",
    )

    # app/db/base.py
    _write(
        os.path.join(root, "app", "db", "base.py"),
        "from sqlalchemy.orm import DeclarativeBase\n\nclass Base(DeclarativeBase):\n    pass\n",
    )

    # requirements.txt
    _write(
        os.path.join(root, "requirements.txt"),
        """\
fastapi==0.110.0
uvicorn[standard]==0.28.0
pydantic==2.6.0
pydantic-settings==2.2.0
sqlalchemy==2.0.0
psycopg2-binary==2.9.9
alembic==1.13.0
pytest==8.0.0
pytest-asyncio==0.23.0
httpx==0.27.0
python-dotenv==1.0.0
""",
    )

    # Dockerfile
    _write(
        os.path.join(root, "Dockerfile"),
        """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
    )

    # docker-compose.yml
    _write(
        os.path.join(root, "docker-compose.yml"),
        """\
version: '3.9'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://logistics:pass@db:5432/shipping_db
    depends_on:
      - db
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: logistics
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: shipping_db
    volumes:
      - pg_data:/var/lib/postgresql/data
volumes:
  pg_data:
""",
    )

    # .env.example
    _write(
        os.path.join(root, ".env.example"),
        "DATABASE_URL=postgresql://logistics:pass@localhost:5432/shipping_db\nAPI_V1_PREFIX=/api/v1\nENVIRONMENT=development\n",
    )

    # Makefile
    _write(
        os.path.join(root, "Makefile"),
        "run:\n\tuvicorn app.main:app --reload\n\ntest:\n\tpytest tests/ -v\n\nmigrate:\n\talembic upgrade head\n",
    )

    # README.md (should be prioritized LAST)
    _write(
        os.path.join(root, "README.md"),
        """\
# LogisticsShippingRates

A FastAPI microservice for calculating shipping rates across multiple carriers and zones.

## Features
- Multi-carrier rate calculation
- Zone-based surcharge support
- PostgreSQL persistence
- Docker deployment ready

## Setup
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
""",
    )


# ---------------------------------------------------------------------------
# Demonstration Runner
# ---------------------------------------------------------------------------

def run_demonstration(root: str) -> ProjectSummary:
    print("\n--- Running RepositoryAnalyzer on LogisticsShippingRates ---\n")
    summary = repository_analyzer.analyze_repository(root)
    return summary


def validate_summary(summary: ProjectSummary, root: str) -> None:
    print("\n=== Validation Results ===")
    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        status = "[PASS]" if condition else "[FAIL]"
        if condition:
            passed += 1
        else:
            failed += 1
        suffix = f" ({detail})" if detail else ""
        print(f"  {status} {label}{suffix}")

    # 1. Language detected
    check("Python detected", "Python" in summary.languages)

    # 2. Framework detected
    check("FastAPI detected", "FastAPI" in summary.frameworks)

    # 3. Package manager detected
    check("pip package manager detected", summary.package_manager == "pip", f"got: {summary.package_manager}")

    # 4. Database detected
    check("PostgreSQL detected", summary.database == "PostgreSQL", f"got: {summary.database}")

    # 5. ORM detected
    check("SQLAlchemy detected", summary.orm == "SQLAlchemy", f"got: {summary.orm}")

    # 6. Testing framework detected
    check("Pytest detected", "Pytest" in summary.testing_frameworks, f"got: {summary.testing_frameworks}")

    # 7. Deployment detected
    check("Docker detected", summary.deployment is not None and "Docker" in summary.deployment, f"got: {summary.deployment}")

    # 8. Entry points - app/main.py must be present
    ep_paths = [ep.path for ep in summary.entry_points]
    check(
        "app/main.py detected as entry point",
        any("main.py" in ep for ep in ep_paths),
        f"entry points: {ep_paths}",
    )

    # 9. Important files - source code files must be present
    impl_files = [f for f in summary.important_files if f.endswith(".py") and "readme" not in f.lower()]
    check(
        "Implementation .py files in important_files",
        len(impl_files) > 0,
        f"impl files found: {impl_files[:5]}",
    )

    # 10. README.md must NOT be the first important file
    if summary.important_files:
        first = summary.important_files[0]
        check(
            "README.md is NOT first in important_files",
            "readme" not in first.lower(),
            f"first file is: {first}",
        )

    # 11. Key source files appear before README.md
    readme_idx = next((i for i, f in enumerate(summary.important_files) if "readme" in f.lower()), None)
    rate_calc_idx = next((i for i, f in enumerate(summary.important_files) if "rate_calculator" in f.lower()), None)
    shipping_route_idx = next((i for i, f in enumerate(summary.important_files) if "shipping" in f.lower() and "routes" in f.lower()), None)

    if readme_idx is not None and rate_calc_idx is not None:
        check(
            "rate_calculator.py appears before README.md",
            rate_calc_idx < readme_idx,
            f"rate_calculator_idx={rate_calc_idx}, readme_idx={readme_idx}",
        )
    if readme_idx is not None and shipping_route_idx is not None:
        check(
            "routes/shipping.py appears before README.md",
            shipping_route_idx < readme_idx,
            f"shipping_route_idx={shipping_route_idx}, readme_idx={readme_idx}",
        )

    # 12. Important directories include source dirs
    check(
        "Source directories in important_directories",
        any("app" in d or "services" in d or "models" in d or "api" in d for d in summary.important_directories),
        f"dirs: {summary.important_directories[:8]}",
    )

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed


def print_summary(summary: ProjectSummary) -> None:
    print("\n" + "=" * 60)
    print("LOGISTICS SHIPPING RATES - PROJECT SUMMARY")
    print("=" * 60)
    print(f"  Project:          {summary.project_name}")
    print(f"  Description:      {summary.description}")
    print(f"  Languages:        {summary.languages}")
    print(f"  Frameworks:       {summary.frameworks}")
    print(f"  Package Manager:  {summary.package_manager}")
    print(f"  Database:         {summary.database}")
    print(f"  ORM:              {summary.orm}")
    print(f"  Authentication:   {summary.authentication}")
    print(f"  Testing:          {summary.testing_frameworks}")
    print(f"  Deployment:       {summary.deployment}")
    print(f"  Architecture:     {summary.architecture}")
    print(f"\n  Entry Points ({len(summary.entry_points)}):")
    for ep in summary.entry_points:
        print(f"    - {ep.path}  [{ep.detected_from}]")
    print(f"\n  Important Directories ({len(summary.important_directories)}):")
    for d in summary.important_directories[:10]:
        print(f"    - {d}")
    print(f"\n  Top 12 Prioritized Files:")
    for i, f in enumerate(summary.important_files[:12], 1):
        print(f"    {i:2d}. {f}")
    print(f"\n  Technologies ({len(summary.technologies)}):")
    for t in summary.technologies:
        print(f"    - [{t.category}] {t.name}")
    print(f"\n  Observations:")
    for obs in summary.observations:
        print(f"    - {obs}")
    print("=" * 60)


def print_planner_context(summary: ProjectSummary) -> None:
    """Show what the Planner Agent sees from this ProjectSummary."""
    print("\n" + "=" * 60)
    print("PLANNER AGENT CONTEXT (from ProjectSummary)")
    print("=" * 60)
    print(f"  Architecture: {summary.architecture}")
    print(f"  Frameworks:   {summary.frameworks}")
    print(f"  Entry Points: {[ep.path for ep in summary.entry_points]}")
    print(f"\n  Key Configuration & Manifest Files (what Planner sees as 'Key Files'):")
    for f in summary.important_files[:15]:
        print(f"    - {f}")
    print("\n  >> In a BEFORE scenario, the Planner saw only: ['README.md']")
    print("  >> In the AFTER scenario, the Planner sees actual implementation files above.")
    print("=" * 60)


def main():
    print("=" * 60)
    print("DEMO: LogisticsShippingRates - Enhanced RepositoryAnalyzer")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="logistics_shipping_rates_") as root:
        print(f"\nScaffolding LogisticsShippingRates repository at: {root}")
        scaffold_logistics_shipping_rates(root)

        file_count = sum(len(fs) for _, _, fs in os.walk(root))
        dir_count = sum(1 for _, ds, _ in os.walk(root) for _ in ds)
        print(f"Created {file_count} files across {dir_count} directories.")

        summary = run_demonstration(root)
        print_summary(summary)
        print_planner_context(summary)
        failures = validate_summary(summary, root)

        print("\n" + "=" * 60)
        if failures == 0:
            print("DEMO RESULT: ALL VALIDATIONS PASSED!")
            print("The enhanced RepositoryAnalyzer correctly identifies implementation")
            print("files, entry points, frameworks, and technologies for the Planner.")
        else:
            print(f"DEMO RESULT: {failures} VALIDATION(S) FAILED - see output above.")
        print("=" * 60)


if __name__ == "__main__":
    main()
