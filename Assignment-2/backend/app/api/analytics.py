from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
from ..database import get_db
from ..models import EmissionRecord, BusinessMetric, EmissionFactor
from typing import Optional

router = APIRouter()

@router.get("/yoy")
def get_yoy_emissions(year: int = 2024, db: Session = Depends(get_db)):
    """Year-over-Year emissions comparison by scope"""
    
    result = {}
    
    for target_year in [year, year - 1]:
        emissions = db.query(
            EmissionRecord.scope,
            func.sum(EmissionRecord.calculated_emission).label('total')
        ).filter(
            extract('year', EmissionRecord.activity_date) == target_year
        ).group_by(EmissionRecord.scope).all()
        
        scope_data = {f"scope_{e.scope}": e.total for e in emissions}
        result[str(target_year)] = scope_data
    
    return result

@router.get("/intensity")
def get_emission_intensity(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    metric_name: str = "Steel Production",
    db: Session = Depends(get_db)
):
    """Calculate emission intensity (emissions per unit of production)"""
    
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    total_emissions = db.query(
        func.sum(EmissionRecord.calculated_emission)
    ).filter(
        EmissionRecord.activity_date.between(start, end),
        EmissionRecord.scope.in_([1, 2])
    ).scalar() or 0
    
    metric = db.query(
        func.sum(BusinessMetric.value)
    ).filter(
        BusinessMetric.metric_name == metric_name,
        BusinessMetric.metric_date.between(start, end)
    ).scalar() or 1
    
    intensity = total_emissions / metric if metric > 0 else 0
    
    return {
        "total_emissions": total_emissions,
        "production": metric,
        "intensity": intensity,
        "unit": "kgCO2e/tonne",
        "period": f"{start_date} to {end_date}"
    }

@router.get("/hotspots")
def get_emission_hotspots(
    scope: int = 1,
    year: int = 2024,
    quarter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Breakdown of emissions by material/source"""
    
    query = db.query(
        EmissionRecord.material,
        func.sum(EmissionRecord.calculated_emission).label('total_emission')
    ).filter(
        extract('year', EmissionRecord.activity_date) == year,
        EmissionRecord.scope == scope
    )
    
    if quarter:
        quarter_map = {
            "Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)
        }
        if quarter in quarter_map:
            start_month, end_month = quarter_map[quarter]
            query = query.filter(
                extract('month', EmissionRecord.activity_date).between(start_month, end_month)
            )
    
    results = query.group_by(EmissionRecord.material).order_by(
        func.sum(EmissionRecord.calculated_emission).desc()
    ).all()
    
    return [
        {
            "material": r.material,
            "emission": r.total_emission,
            "percentage": 0
        }
        for r in results
    ]

@router.get("/monthly-trend")
def get_monthly_trend(
    year: int = 2024,
    scope: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        extract('month', EmissionRecord.activity_date).label('month'),
        func.sum(EmissionRecord.calculated_emission).label('total')
    ).filter(
        extract('year', EmissionRecord.activity_date) == year
    )
    
    if scope is not None:
        query = query.filter(EmissionRecord.scope == scope)
    
    results = query.group_by('month').order_by('month').all()
    
    # Fill missing months with 0
    month_data = {r.month: r.total for r in results}
    all_months = []
    for m in range(1, 13):
        all_months.append({
            "month": m,
            "emission": month_data.get(m, 0)
        })
    
    return all_months