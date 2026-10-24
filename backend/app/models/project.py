from sqlalchemy import Boolean, Column, Date, Float, Integer, String

from app.database import Base


class Project(Base):
    """One interconnection request, with the dates it reached each study phase.

    status is "active", "operational" or "withdrawn". max_phase is the furthest
    phase reached (see app.data.regions.PHASES). Phase dates are null when the
    project never reached that phase or the source does not report it.
    """

    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    iso_region = Column(String, index=True)
    state = Column(String)
    substation_id = Column(String, index=True, nullable=True)
    technology_type = Column(String)
    is_hybrid = Column(Boolean, default=False)
    proposed_capacity_mw = Column(Float)

    queue_date = Column(Date)
    sis_date = Column(Date, nullable=True)          # system impact study start
    facilities_date = Column(Date, nullable=True)   # facilities study start
    ia_date = Column(Date, nullable=True)           # interconnection agreement
    construction_date = Column(Date, nullable=True)
    cod_date = Column(Date, nullable=True)          # commercial operation
    withdrawn_date = Column(Date, nullable=True)

    status = Column(String, index=True)
    max_phase = Column(Integer)
    upgrade_cost_per_kw = Column(Float, nullable=True)
    data_source = Column(String, default="synthetic")
