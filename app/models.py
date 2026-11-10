"""Task table and the three supported statuses."""

from enum import StrEnum

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="valid_title_length"),
        CheckConstraint("length(description) <= 5000", name="valid_description_length"),
        CheckConstraint("instr(title, char(0)) = 0", name="title_without_nul"),
        CheckConstraint("instr(description, char(0)) = 0", name="description_without_nul"),
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="valid_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=TaskStatus.TODO.value, server_default=TaskStatus.TODO.value
    )
