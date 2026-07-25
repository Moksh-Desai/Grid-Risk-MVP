from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import String

from app.database import Base


class Substation(Base):
    __tablename__ = "substations"

    substation_id = Column(
        String,
        primary_key=True
    )

    substation_name = Column(String)

    iso_region = Column(String)

    latitude = Column(Float)

    longitude = Column(Float)

    existing_capacity_mw = Column(Float)

    historical_withdrawal_rate = Column(Float)

    historical_avg_wait_days = Column(Float)

    historical_avg_upgrade_cost = Column(Float)
