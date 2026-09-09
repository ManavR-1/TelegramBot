from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
)

from database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    payment_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    telegram_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    status = Column(
        String(50),
        nullable=False,
        default="active",
    )

    started_at = Column(
        DateTime,
        nullable=False,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
    )

    invite_link = Column(
        Text,
        nullable=True,
    )

    invite_expires_at = Column(
        DateTime,
        nullable=True,
    )

    # Renewal reminder tracking
    reminder_3d_sent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reminder_1d_sent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self):
        return (
            f"<Subscription "
            f"id={self.id} "
            f"telegram_id={self.telegram_id} "
            f"status={self.status}>"
        )