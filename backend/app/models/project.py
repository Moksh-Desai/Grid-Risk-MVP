from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import Date

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(
        String,
        primary_key=True
    )

    iso_region = Column(String)

    substation_id = Column(String)

    technology_type = Column(String)

    proposed_capacity_mw = Column(Float)

    queue_date = Column(Date)

    status = Column(String)

    study_phase = Column(String)

    upgrade_cost_estimate = Column(Float)

    time_in_queue_days = Column(Integer)
