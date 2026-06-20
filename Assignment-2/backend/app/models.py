from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    scope = Column(Integer, nullable=False)
    section = Column(String(255))
    material = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False)
    factor_value = Column(Float, nullable=False)
    source = Column(String(255))
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Scope 2 specific
    renewable_share = Column(Float, nullable=True)
    grid_emission_source = Column(String(255), nullable=True)
    load_factor = Column(Float, nullable=True)
    power_factor = Column(Float, nullable=True)
    location = Column(String(255), nullable=True)
    
    # Scope 3 specific
    category = Column(String(255), nullable=True)
    transportation_mode = Column(String(100), nullable=True)
    vendor = Column(String(255), nullable=True)
    lifecycle_stage = Column(String(100), nullable=True)
    measurement_method = Column(String(255), nullable=True)

class EmissionRecord(Base):
    __tablename__ = "emission_records"
    
    id = Column(Integer, primary_key=True, index=True)
    scope = Column(Integer, nullable=False)
    activity_date = Column(Date, nullable=False)
    section = Column(String(255))
    material = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    factor_id = Column(String(36), nullable=False)  # UUID of EmissionFactor
    calculated_emission = Column(Float, nullable=False)
    is_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    user_position = Column(String(50), nullable=True)
    is_excel_data = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Scope 3 specific
    category = Column(String(255), nullable=True)
    transportation_mode = Column(String(100), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    changed_by = Column(String(100))
    changed_at = Column(DateTime, server_default=func.now())

class BusinessMetric(Base):
    __tablename__ = "business_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_date = Column(Date, nullable=False)
    metric_name = Column(String(255), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())