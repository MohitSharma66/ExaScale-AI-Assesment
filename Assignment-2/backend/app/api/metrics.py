from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import BusinessMetric
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class MetricCreate(BaseModel):
    metric_date: str
    metric_name: str
    value: float
    unit: str

@router.post("/")
def create_metric(metric: MetricCreate, db: Session = Depends(get_db)):
    metric_date = datetime.strptime(metric.metric_date, "%Y-%m-%d").date()
    
    new_metric = BusinessMetric(
        metric_date=metric_date,
        metric_name=metric.metric_name,
        value=metric.value,
        unit=metric.unit
    )
    db.add(new_metric)
    db.commit()
    db.refresh(new_metric)
    
    return {
        "id": new_metric.id,
        "metric_date": new_metric.metric_date,
        "metric_name": new_metric.metric_name,
        "value": new_metric.value,
        "unit": new_metric.unit,
        "message": "Metric saved successfully"
    }

@router.get("/")
def get_metrics(
    metric_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(BusinessMetric)
    if metric_name:
        query = query.filter(BusinessMetric.metric_name == metric_name)
    return query.all()

@router.get("/names")
def get_metric_names(db: Session = Depends(get_db)):
    results = db.query(BusinessMetric.metric_name, BusinessMetric.unit).distinct().all()
    return [{"name": r[0], "unit": r[1]} for r in results]