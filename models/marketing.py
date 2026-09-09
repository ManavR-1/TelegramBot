from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from database import Base


class MarketingVisit(Base):
    __tablename__ = "marketing_visits"

    id = Column(Integer, primary_key=True, autoincrement=True)

    telegram_id = Column(Integer, nullable=False, index=True)
    campaign = Column(String(100), nullable=False, index=True)

    first_seen_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    last_seen_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    visit_count = Column(
        Integer,
        default=1,
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<MarketingVisit telegram_id={self.telegram_id} "
            f"campaign={self.campaign} visits={self.visit_count}>"
        )
