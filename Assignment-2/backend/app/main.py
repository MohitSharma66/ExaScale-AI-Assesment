from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, get_db
from .models import Base
from .load_data import load_all_data

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GHG Emissions Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    from sqlalchemy.orm import Session
    from .models import EmissionFactor
    db = next(get_db())
    try:
        count = db.query(EmissionFactor).count()
        if count == 0:
            print("📊 Database is empty. Loading sample data...")
            load_all_data(db)
        else:
            print(f"✅ Database already has {count} emission factors")
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "GHG Emissions Platform API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

from .api.emissions import router as emissions_router
from .api.analytics import router as analytics_router
from .api.metrics import router as metrics_router

app.include_router(emissions_router, prefix="/api/emissions", tags=["Emissions"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["Metrics"])