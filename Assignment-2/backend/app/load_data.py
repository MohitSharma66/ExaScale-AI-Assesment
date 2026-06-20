import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime, date
from .models import EmissionFactor, EmissionRecord, BusinessMetric
import os
import uuid
import random

POSITIONS = ["CEO", "VP", "Manager", "Supervisor", "Employee"]

def get_quarter_dates(quarter_str):
    year = 2024
    quarter_map = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)}
    # normalize "2024Q1" → "Q1"
    if len(str(quarter_str)) > 2:
        quarter_str = str(quarter_str)[-2:]
    if quarter_str in quarter_map:
        start_month, end_month = quarter_map[quarter_str]
        return date(year, start_month, 1), date(year, end_month, 30)
    return date(year, 1, 1), date(year, 12, 31)

def generate_factor_uuid(scope, material, quarter):
    key = f"{scope}_{material}_{quarter}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))

def load_excel_data(db: Session, excel_path: str = "/app/GHG_Sheet.xlsx"):
    print(f"📂 Reading Excel file: {excel_path}")
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found at: {excel_path}")
        return
    try:
        df_scope1 = pd.read_excel(excel_path, sheet_name="Scope 1")
        df_scope2 = pd.read_excel(excel_path, sheet_name="Scope 2")
        df_scope3 = pd.read_excel(excel_path, sheet_name="Scope 3")
        print(f"✅ Loaded Scope 1: {len(df_scope1)} rows")
        print(f"✅ Loaded Scope 2: {len(df_scope2)} rows")
        print(f"✅ Loaded Scope 3: {len(df_scope3)} rows")
        
        load_scope1_from_df(db, df_scope1)
        load_scope2_from_df(db, df_scope2)
        load_scope3_from_df(db, df_scope3)
        load_default_business_metrics(db)
        load_2023_data(db)
        
        print("✅ All data loaded successfully!")
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")

def load_2023_data(db: Session):
    """Load 2023 historical data"""
    from .models import EmissionRecord
    if db.query(EmissionRecord).filter(
        EmissionRecord.activity_date < date(2024, 1, 1)
    ).count() > 0:
        print("⏭️ 2023 records already exist, skipping")
        return

    excel_path = None
    for p in ["/app/app/GHG_Sheet_2023.xlsx", "/app/GHG_Sheet_2023.xlsx", "GHG_Sheet_2023.xlsx"]:
        if os.path.exists(p):
            excel_path = p
            break
    if not excel_path:
        print("⚠️ GHG_Sheet_2023.xlsx not found, skipping 2023 data")
        return

    print(f"📂 Reading 2023 Excel file: {excel_path}")
    try:
        df_s1 = pd.read_excel(excel_path, sheet_name="Scope 1")
        df_s2 = pd.read_excel(excel_path, sheet_name="Scope 2")
        df_s3 = pd.read_excel(excel_path, sheet_name="Scope 3")
    except Exception as e:
        print(f"❌ Error reading 2023 Excel: {e}")
        return

    def get_2023_quarter_dates(quarter_str):
        year = 2023
        q = str(quarter_str)[-2:] if len(str(quarter_str)) > 2 else str(quarter_str)
        qmap = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12)}
        if q in qmap:
            sm, em = qmap[q]
            return date(year, sm, 1), date(year, em, 30)
        return date(year, 1, 1), date(year, 12, 31)

    count = 0
    # Scope 1
    for _, row in df_s1.iterrows():
        try:
            quarter = row.get("Year/Timeline", "Q1")
            vf, vt = get_2023_quarter_dates(quarter)
            material = str(row.get("Material", ""))
            factor_value = float(row.get("Emission Factor", 0) or 0)
            quantity = float(row.get("Q1 Quantity", 0) or 0)
            if not material or factor_value == 0 or quantity == 0:
                continue
            factor_id = generate_factor_uuid(1, material, str(quarter) + "_2023")
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id, scope=1, section=str(row.get("Section", "")),
                    material=material, unit=str(row.get("Unit of Material", "tonnes")),
                    factor_value=factor_value, source="IPCC 2006 Guidelines",
                    valid_from=vf, valid_to=vt, location="Central Steel Plant"
                )
                db.add(factor)
                db.flush()
            db.add(EmissionRecord(
                scope=1, activity_date=vf, section=str(row.get("Section", "")),
                material=material, quantity=quantity, unit=str(row.get("Unit of Material", "tonnes")),
                factor_id=factor_id, calculated_emission=quantity * factor_value,
                created_by="system", user_position=random.choice(POSITIONS), is_excel_data=True
            ))
            count += 1
        except Exception as e:
            print(f"⚠️ 2023 S1 row error: {e}")

    # Scope 2
    for _, row in df_s2.iterrows():
        try:
            quarter = row.get("Quarter", "Q1")
            vf, vt = get_2023_quarter_dates(quarter)
            energy_type = str(row.get("Energy Type", ""))
            factor_value = float(row.get("Emission Factor (tCO₂/unit)", 0) or 0)
            quantity = float(row.get("Energy Consumed", 0) or 0)
            if not energy_type or factor_value == 0 or quantity == 0:
                continue
            factor_id = generate_factor_uuid(2, energy_type, str(quarter) + "_2023")
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id, scope=2, section=str(row.get("Section/Process", "")),
                    material=energy_type, unit=str(row.get("Unit", "kWh")),
                    factor_value=factor_value, source="CEA India 2022 Report",
                    valid_from=vf, valid_to=vt, location="Central Steel Plant",
                    grid_emission_source="CEA India 2022 Report"
                )
                db.add(factor)
                db.flush()
            db.add(EmissionRecord(
                scope=2, activity_date=vf, section=str(row.get("Section/Process", "")),
                material=energy_type, quantity=quantity, unit=str(row.get("Unit", "kWh")),
                factor_id=factor_id, calculated_emission=quantity * factor_value,
                created_by="system", user_position=random.choice(POSITIONS), is_excel_data=True
            ))
            count += 1
        except Exception as e:
            print(f"⚠️ 2023 S2 row error: {e}")

    # Scope 3
    for _, row in df_s3.iterrows():
        try:
            quarter = row.get("Quarter", "2023Q1")
            vf, vt = get_2023_quarter_dates(quarter)
            category = str(row.get("Scope 3 Category", ""))
            factor_value = float(row.get("Emission Factor (tCO2/unit)", 0) or 0)
            quantity = float(row.get("Quantity", 0) or 0)
            if not category or quantity == 0:
                continue
            factor_id = generate_factor_uuid(3, category, str(quarter) + "_2023")
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id, scope=3, section=str(row.get("Activity Description", "")),
                    material=category, unit=str(row.get("Unit of Activity", "unit")),
                    factor_value=factor_value, source="GHG Protocol Scope 3 Eval Tool",
                    valid_from=vf, valid_to=vt, category=category,
                    transportation_mode=str(row.get("Transportation Mode", "")),
                    vendor=str(row.get("Vendor Involved", ""))
                )
                db.add(factor)
                db.flush()
            db.add(EmissionRecord(
                scope=3, activity_date=vf, section=str(row.get("Activity Description", "")),
                material=category, quantity=quantity, unit=str(row.get("Unit of Activity", "unit")),
                factor_id=factor_id, calculated_emission=quantity * factor_value,
                created_by="system", user_position=random.choice(POSITIONS),
                is_excel_data=True, category=category,
                transportation_mode=str(row.get("Transportation Mode", ""))
            ))
            count += 1
        except Exception as e:
            print(f"⚠️ 2023 S3 row error: {e}")

    db.commit()
    print(f"✅ Loaded {count} 2023 emission records")

def load_scope1_from_df(db: Session, df):
    print("📊 Processing Scope 1 data...")
    factor_count = 0
    record_count = 0
    
    print("📊 Processing Scope 1 data...")
    from .models import EmissionRecord
    if db.query(EmissionRecord).filter(EmissionRecord.scope == 1).count() > 0:
        print("⏭️ Scope 1 records already exist, skipping")
        return
    
    for _, row in df.iterrows():
        try:
            quarter = row.get("Year/Timeline", "Q1")
            if pd.isna(quarter):
                quarter = "Q1"
            valid_from, valid_to = get_quarter_dates(quarter)
            
            material = row.get("Material", "")
            if pd.isna(material):
                continue
            factor_value = row.get("Emission Factor", 0)
            if pd.isna(factor_value) or factor_value == 0:
                continue
            unit = row.get("Unit of Material", "tonnes")
            section = row.get("Section", "General")
            
            factor_id = generate_factor_uuid(1, str(material), quarter)
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id,
                    scope=1,
                    section=str(section),
                    material=str(material),
                    unit=str(unit),
                    factor_value=float(factor_value),
                    source="IPCC 2006 Guidelines",
                    valid_from=valid_from,
                    valid_to=valid_to,
                    location="Central Steel Plant"
                )
                db.add(factor)
                factor_count += 1
                db.flush()
            
            # Create emission record from Q1 Quantity (or other quarters if needed)
            quantity = row.get("Q1 Quantity", 0)
            if not pd.isna(quantity) and quantity > 0:
                record = EmissionRecord(
                    scope=1,
                    activity_date=valid_from,
                    section=str(section),
                    material=str(material),
                    quantity=float(quantity),
                    unit=str(unit),
                    factor_id=factor_id,
                    calculated_emission=float(quantity) * float(factor_value),
                    created_by="system",
                    user_position=random.choice(POSITIONS),
                    is_excel_data=True
                )
                db.add(record)
                record_count += 1
                if record_count % 50 == 0:
                    db.commit()
                    
        except Exception as e:
            print(f"⚠️ Error processing row: {e}")
            continue
    
    db.commit()
    print(f"✅ Loaded {factor_count} Scope 1 factors and {record_count} records with UUIDs and positions")

def load_scope2_from_df(db: Session, df):
    print("📊 Processing Scope 2 data...")
    factor_count = 0
    record_count = 0

    print("📊 Processing Scope 2 data...")
    from .models import EmissionRecord
    if db.query(EmissionRecord).filter(EmissionRecord.scope == 2).count() > 0:
        print("⏭️ Scope 2 records already exist, skipping")
        return
    
    for _, row in df.iterrows():
        try:
            quarter = row.get("Quarter", "Q1")
            if pd.isna(quarter):
                quarter = "Q1"
            valid_from, valid_to = get_quarter_dates(quarter)
            
            energy_type = row.get("Energy Type", "")
            if pd.isna(energy_type):
                continue
            factor_value = row.get("Emission Factor (tCO₂/unit)", 0)
            if pd.isna(factor_value) or factor_value == 0:
                continue
            unit = row.get("Unit", "kWh")
            section = row.get("Section/Process", "General")
            
            factor_id = generate_factor_uuid(2, str(energy_type), quarter)
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id,
                    scope=2,
                    section=str(section),
                    material=str(energy_type),
                    unit=str(unit),
                    factor_value=float(factor_value),
                    source="CEA India 2023 Report",
                    valid_from=valid_from,
                    valid_to=valid_to,
                    location="Central Steel Plant",
                    grid_emission_source="CEA India 2023 Report"
                )
                db.add(factor)
                factor_count += 1
                db.flush()
            
            quantity = row.get("Energy Consumed", 0)
            if not pd.isna(quantity) and quantity > 0:
                record = EmissionRecord(
                    scope=2,
                    activity_date=valid_from,
                    section=str(section),
                    material=str(energy_type),
                    quantity=float(quantity),
                    unit=str(unit),
                    factor_id=factor_id,
                    calculated_emission=float(quantity) * float(factor_value),
                    created_by="system",
                    user_position=random.choice(POSITIONS),
                    is_excel_data=True
                )
                db.add(record)
                record_count += 1
                if record_count % 50 == 0:
                    db.commit()
                    
        except Exception as e:
            print(f"⚠️ Error processing row: {e}")
            continue
    
    db.commit()
    print(f"✅ Loaded {factor_count} Scope 2 factors and {record_count} records")

def load_scope3_from_df(db: Session, df):
    print("📊 Processing Scope 3 data...")
    factor_count = 0
    record_count = 0

    print("📊 Processing Scope 3 data...")
    from .models import EmissionRecord
    if db.query(EmissionRecord).filter(EmissionRecord.scope == 3).count() > 0:
        print("⏭️ Scope 3 records already exist, skipping")
        return
    
    for _, row in df.iterrows():
        try:
            quarter = row.get("Quarter", "Q1")
            if pd.isna(quarter):
                quarter = "Q1"
            valid_from, valid_to = get_quarter_dates(quarter)
            
            category = row.get("Scope 3 Category", "")
            if pd.isna(category):
                continue
            factor_value = row.get("Emission Factor (tCO2/unit)", 0)
            if pd.isna(factor_value) or factor_value == 0:
                continue
            unit = row.get("Unit of Activity", "unit")
            
            factor_id = generate_factor_uuid(3, str(category), quarter)
            factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
            if not factor:
                factor = EmissionFactor(
                    id=factor_id,
                    scope=3,
                    section=str(row.get("Activity Description", "")),
                    material=str(category),
                    unit=str(unit),
                    factor_value=float(factor_value),
                    source="GHG Protocol Scope 3 Eval Tool",
                    valid_from=valid_from,
                    valid_to=valid_to,
                    category=str(category),
                    transportation_mode=str(row.get("Transportation Mode", "")),
                    vendor=str(row.get("Vendor Involved", "")),
                    lifecycle_stage=str(row.get("Lifecycle Stage", "")),
                    measurement_method=str(row.get("Measurement Method", ""))
                )
                db.add(factor)
                factor_count += 1
                db.flush()
            
            quantity = row.get("Quantity", 0)
            if not pd.isna(quantity) and quantity > 0:
                record = EmissionRecord(
                    scope=3,
                    activity_date=valid_from,
                    section=str(row.get("Activity Description", "")),
                    material=str(category),
                    quantity=float(quantity),
                    unit=str(unit),
                    factor_id=factor_id,
                    calculated_emission=float(quantity) * float(factor_value),
                    created_by="system",
                    user_position=random.choice(POSITIONS),
                    is_excel_data=True,
                    category=str(category),
                    transportation_mode=str(row.get("Transportation Mode", ""))
                )
                db.add(record)
                record_count += 1
                if record_count % 50 == 0:
                    db.commit()
                    
        except Exception as e:
            print(f"⚠️ Error processing row: {e}")
            continue
    
    db.commit()
    print(f"✅ Loaded {factor_count} Scope 3 factors and {record_count} records")

def load_default_business_metrics(db: Session):
    existing = db.query(BusinessMetric).first()
    if existing:
        return
    
    metrics = [
        ("2024-01-01", "Steel Production", 45000, "tonnes"),
        ("2024-02-01", "Steel Production", 48000, "tonnes"),
        ("2024-03-01", "Steel Production", 52000, "tonnes"),
        ("2024-04-01", "Steel Production", 50000, "tonnes"),
        ("2024-05-01", "Steel Production", 53000, "tonnes"),
        ("2024-06-01", "Steel Production", 49000, "tonnes"),
        ("2024-07-01", "Steel Production", 55000, "tonnes"),
        ("2024-08-01", "Steel Production", 51000, "tonnes"),
        ("2024-09-01", "Steel Production", 56000, "tonnes"),
        ("2024-10-01", "Steel Production", 54000, "tonnes"),
        ("2024-11-01", "Steel Production", 52000, "tonnes"),
        ("2024-12-01", "Steel Production", 58000, "tonnes"),
        ("2024-01-01", "Employees", 500, "count"),
        ("2024-02-01", "Employees", 510, "count"),
        ("2024-03-01", "Employees", 520, "count"),
        ("2024-04-01", "Employees", 530, "count"),
        ("2024-05-01", "Employees", 540, "count"),
        ("2024-06-01", "Employees", 550, "count"),
    ]
    
    for date_str, name, value, unit in metrics:
        metric = BusinessMetric(
            metric_date=datetime.strptime(date_str, "%Y-%m-%d").date(),
            metric_name=name,
            value=value,
            unit=unit
        )
        db.add(metric)
    
    db.commit()
    print(f"✅ Loaded {len(metrics)} default business metrics")

def load_all_data(db: Session):
    excel_path = "/app/GHG_Sheet.xlsx"
    if os.path.exists("/app/app/GHG_Sheet.xlsx"):
        excel_path = "/app/app/GHG_Sheet.xlsx"
    elif os.path.exists("/app/GHG_Sheet.xlsx"):
        excel_path = "/app/GHG_Sheet.xlsx"
    else:
        excel_path = "GHG_Sheet.xlsx"
    
    load_excel_data(db, excel_path)

if __name__ == "__main__":
    from database import SessionLocal
    db = SessionLocal()
    try:
        load_all_data(db)
    finally:
        db.close()