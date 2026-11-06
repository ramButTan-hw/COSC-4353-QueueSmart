"""Every table of the application. One module per area, imported here so Base.metadata knows about all of them.

    from app.tables import credentials, profile   # <- add a line when you add a module

Tip: if two rows depend on each other (a parent and its child), either declare a relationship() between the
models or session.flush() the parent before adding the child, because SQLAlchemy only orders inserts for
declared relationships and the database enforces foreign keys.

Example of a table module (app/tables/example.py):

    from sqlalchemy import CheckConstraint, ForeignKey, String
    from sqlalchemy.orm import Mapped, mapped_column
    from app.database import Base

    class Example(Base):
        __tablename__ = "example"
        __table_args__ = (CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),)

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(100), nullable=False)
        owner_id: Mapped[str] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"))
"""

from app.tables import credentials, profile  # noqa: E402,F401
from app.tables import service  # noqa: E402,F401
