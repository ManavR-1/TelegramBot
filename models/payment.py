from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text

from database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    telegram_id = Column(Integer, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)

    utr = Column(String(255), nullable=False, unique=True, index=True)
    amount = Column(Integer, nullable=False)

    screenshot_file_id = Column(Text, nullable=True)

    # Last campaign/deep-link touch recorded before this payment.
    campaign = Column(String(100), nullable=True, index=True)

    status = Column(String(50), nullable=False, default="pending")

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    reviewed_at = Column(
        DateTime,
        nullable=True,
    )

    rejection_reason = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<Payment "
            f"id={self.id} "
            f"telegram_id={self.telegram_id} "
            f"utr={self.utr} "
            f"status={self.status}>"
        )
