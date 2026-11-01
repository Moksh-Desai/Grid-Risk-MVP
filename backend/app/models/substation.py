from sqlalchemy import Column, Float, String

from app.database import Base


class Substation(Base):
    """A point of interconnection (POI) where projects request to connect."""

    __tablename__ = "substations"

    substation_id = Column(String, primary_key=True)
    substation_name = Column(String)
    iso_region = Column(String, index=True)
    state = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    voltage_kv = Column(Float, nullable=True)
    existing_capacity_mw = Column(Float, nullable=True)
    data_source = Column(String, default="synthetic")
