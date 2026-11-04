"""
One-shot migration: converts the TEXT columns of
incident_analyses to JSONB (PostgreSQL).

Run from the backend folder:
    python scripts/migrate_jsonb.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.database import engine  # noqa: E402

COLUMNS = ["indicators", "recommended_actions"]


def main():
    with engine.connect() as connection:
        sql = text("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'incident_analyses'
              AND column_name = :name
        """)

        for column in COLUMNS:
            result = connection.execute(
                sql, {"name": column}
            ).scalar_one_or_none()

            if result is None:
                print(f"column {column}: not found (skipped)")
                continue

            if result == "jsonb":
                print(f"column {column}: already jsonb (skipped)")
                continue

            connection.execute(text(
                f"""
                ALTER TABLE incident_analyses
                ALTER COLUMN {column}
                TYPE jsonb
                USING ({column}::jsonb)
                """
            ))
            print(f"column {column}: text -> jsonb")

        connection.commit()

    print("migration complete")


if __name__ == "__main__":
    main()
