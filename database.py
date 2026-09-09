from sqlalchemy import (
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
)

DATABASE_URL = "sqlite:///database/payments.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def init_db():
    """Create tables and apply required SQLite migrations."""

    from models.payment import Payment
    from models.subscription import Subscription
    from models.marketing import MarketingVisit

    print("🗄️ Initializing database...")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"🗄️ Existing tables: {tables}")

    if "subscriptions" in tables:
        existing_columns = {
            column["name"]
            for column in inspector.get_columns("subscriptions")
        }

        print("🗄️ Subscription columns:")
        print(", ".join(sorted(existing_columns)))

        with engine.begin() as connection:
            if "reminder_3d_sent" not in existing_columns:
                print("🛠️ Adding reminder_3d_sent...")
                connection.execute(
                    text(
                        """
                        ALTER TABLE subscriptions
                        ADD COLUMN reminder_3d_sent
                        BOOLEAN NOT NULL DEFAULT 0
                        """
                    )
                )
                print("✅ reminder_3d_sent added.")
            else:
                print("✅ reminder_3d_sent already exists.")

            if "reminder_1d_sent" not in existing_columns:
                print("🛠️ Adding reminder_1d_sent...")
                connection.execute(
                    text(
                        """
                        ALTER TABLE subscriptions
                        ADD COLUMN reminder_1d_sent
                        BOOLEAN NOT NULL DEFAULT 0
                        """
                    )
                )
                print("✅ reminder_1d_sent added.")
            else:
                print("✅ reminder_1d_sent already exists.")

    # Payment campaign attribution migration.
    inspector = inspect(engine)
    payment_columns = {
        column["name"]
        for column in inspector.get_columns("payments")
    } if "payments" in inspector.get_table_names() else set()

    if "campaign" not in payment_columns:
        print("🛠️ Adding payments.campaign...")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    ALTER TABLE payments
                    ADD COLUMN campaign VARCHAR(100)
                    """
                )
            )
        print("✅ payments.campaign added.")
    else:
        print("✅ payments.campaign already exists.")

    inspector = inspect(engine)

    if "subscriptions" in inspector.get_table_names():
        final_columns = {
            column["name"]
            for column in inspector.get_columns("subscriptions")
        }

        required_columns = {
            "reminder_3d_sent",
            "reminder_1d_sent",
        }

        missing_columns = required_columns - final_columns

        if missing_columns:
            raise RuntimeError(
                "❌ Database migration failed. "
                f"Missing columns: {missing_columns}"
            )

    final_payment_columns = {
        column["name"]
        for column in inspector.get_columns("payments")
    }

    if "campaign" not in final_payment_columns:
        raise RuntimeError(
            "❌ Database migration failed. payments.campaign is missing."
        )

    print("✅ Database initialized and migrations completed.")
