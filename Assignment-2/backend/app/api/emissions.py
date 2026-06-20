from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from ..database import get_db
from ..models import EmissionFactor, EmissionRecord, AuditLog
from pydantic import BaseModel
from typing import Optional
import csv
from io import StringIO
from fastapi.responses import Response

router = APIRouter()

POSITION_HIERARCHY = {
    "CEO": 5,
    "VP": 4,
    "Manager": 3,
    "Supervisor": 2,
    "Employee": 1
}

class EmissionCreate(BaseModel):
    scope: int
    material: str
    quantity: float
    activity_date: str
    section: Optional[str] = None
    user_id: str
    position: str
    category: Optional[str] = None
    transportation_mode: Optional[str] = None
    vendor: Optional[str] = None

class EmissionOverride(BaseModel):
    new_quantity: float
    reason: str
    user_id: str
    position: str

@router.post("")
def create_emission(emission: EmissionCreate, db: Session = Depends(get_db)):
    activity_date = datetime.strptime(emission.activity_date, "%Y-%m-%d").date()
    
    factor = db.query(EmissionFactor).filter(
        EmissionFactor.scope == emission.scope,
        EmissionFactor.material == emission.material,
        EmissionFactor.valid_from <= activity_date,
        EmissionFactor.valid_to >= activity_date
    ).first()
    
    if not factor:
        raise HTTPException(status_code=404, detail=f"No emission factor found for {emission.material} on {activity_date}")
    
    calculated = emission.quantity * factor.factor_value
    
    record = EmissionRecord(
        scope=emission.scope,
        activity_date=activity_date,
        section=emission.section or factor.section,
        material=emission.material,
        quantity=emission.quantity,
        unit=factor.unit,
        factor_id=factor.id,  # UUID string
        calculated_emission=calculated,
        created_by=emission.user_id,
        user_position=emission.position,
        category=emission.category,
        transportation_mode=emission.transportation_mode,
        is_excel_data=False  # User-created records are not from Excel
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    audit = AuditLog(
        record_id=record.id,
        action="CREATE",
        old_value={},
        new_value={"emission": record.calculated_emission},
        changed_by=emission.user_id
    )
    db.add(audit)
    db.commit()
    
    return {
        "id": record.id,
        "scope": record.scope,
        "material": record.material,
        "quantity": record.quantity,
        "unit": record.unit,
        "factor_value": factor.factor_value,
        "calculated_emission": record.calculated_emission,
        "activity_date": record.activity_date,
        "is_override": record.is_override,
        "created_by": record.created_by,
        "position": record.user_position,
        "is_excel_data": record.is_excel_data,
        "factor_uuid": factor.id,
        "message": "Emission recorded successfully"
    }

@router.put("/{record_id}/override")
def override_emission(record_id: int, override: EmissionOverride, db: Session = Depends(get_db)):
    record = db.query(EmissionRecord).filter(EmissionRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    current_position_level = POSITION_HIERARCHY.get(override.position, 0)
    record_position_level = POSITION_HIERARCHY.get(record.user_position, 0)
    
    if current_position_level == record_position_level:
        if override.user_id != record.created_by:
            raise HTTPException(status_code=403, detail="Only the original user can override their own records at same position")
    elif current_position_level < record_position_level:
        raise HTTPException(status_code=403, detail="Higher position required to override this record")
    
    old_values = {
        "quantity": record.quantity,
        "calculated_emission": record.calculated_emission
    }
    
    old_quantity = record.quantity
    record.quantity = override.new_quantity
    record.calculated_emission = override.new_quantity * (record.calculated_emission / old_quantity) if old_quantity > 0 else 0
    record.is_override = True
    record.override_reason = override.reason
    
    audit = AuditLog(
        record_id=record_id,
        action="OVERRIDE",
        old_value=old_values,
        new_value={
            "quantity": override.new_quantity,
            "calculated_emission": record.calculated_emission
        },
        changed_by=override.user_id
    )
    db.add(audit)
    db.commit()
    
    return {
        "id": record.id,
        "new_quantity": record.quantity,
        "new_emission": record.calculated_emission,
        "reason": record.override_reason,
        "changed_by": override.user_id,
        "position": override.position,
        "message": "Emission overridden successfully"
    }

@router.get("")
def get_emissions(scope: Optional[int] = None, material: Optional[str] = None, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    query = db.query(EmissionRecord)
    if scope is not None:
        query = query.filter(EmissionRecord.scope == scope)
    if material:
        query = query.filter(EmissionRecord.material.ilike(f"%{material}%"))
    
    records = query.all()
    factor_ids = {r.factor_id for r in records}
    factors = {f.id: f for f in db.query(EmissionFactor).filter(EmissionFactor.id.in_(factor_ids)).all()}
    
    result = []
    for r in records:
        factor = factors.get(r.factor_id)
        result.append({
            "id": r.id,
            "scope": r.scope,
            "activity_date": r.activity_date,
            "section": r.section,
            "material": r.material,
            "quantity": r.quantity,
            "unit": r.unit,
            "factor_id": r.factor_id,
            "calculated_emission": r.calculated_emission,
            "is_override": r.is_override,
            "override_reason": r.override_reason,
            "created_by": r.created_by,
            "user_position": r.user_position,
            "is_excel_data": r.is_excel_data,
            "created_at": r.created_at,
            "category": r.category,
            "transportation_mode": r.transportation_mode,
            "factor_uuid": factor.id if factor else None,
            "factor_value": factor.factor_value if factor else None
        })
    return result

@router.get("/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(EmissionRecord).filter(EmissionRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    factor = db.query(EmissionFactor).filter(EmissionFactor.id == record.factor_id).first()
    
    return {
        "id": record.id,
        "scope": record.scope,
        "activity_date": record.activity_date,
        "section": record.section,
        "material": record.material,
        "quantity": record.quantity,
        "unit": record.unit,
        "factor_id": record.factor_id,
        "factor_uuid": factor.id if factor else None,
        "factor_value": factor.factor_value if factor else None,
        "factor_valid_from": factor.valid_from if factor else None,
        "factor_valid_to": factor.valid_to if factor else None,
        "calculated_emission": record.calculated_emission,
        "is_override": record.is_override,
        "override_reason": record.override_reason,
        "created_by": record.created_by,
        "user_position": record.user_position,
        "is_excel_data": record.is_excel_data,
        "created_at": record.created_at,
        "category": record.category,
        "transportation_mode": record.transportation_mode
    }

@router.get("/export/csv")
def export_emissions_csv(
    scope: Optional[int] = None,
    material: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(EmissionRecord)
    
    if scope is not None:
        query = query.filter(EmissionRecord.scope == scope)
    if material:
        query = query.filter(EmissionRecord.material.ilike(f"%{material}%"))
    
    records = query.all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Scope", "Material", "Quantity", "Unit", "Emissions (tCO2e)", "Date", "Created By", "Position", "Source"])
    
    for r in records:
        writer.writerow([
            r.id, r.scope, r.material, r.quantity, r.unit,
            r.calculated_emission, r.activity_date,
            r.created_by or "", r.user_position or "",
            "Excel" if r.is_excel_data else "User"
        ])
    
    filename = f"emissions_{scope or 'all'}_{material or 'all'}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )