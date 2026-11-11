"""Public request and response contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import TaskStatus

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]*$"),
]
Description = Annotated[str, StringConstraints(max_length=5000, pattern=r"^[^\x00]*$")]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description = ""
    status: TaskStatus = TaskStatus.TODO


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Missing fields have an unvalidated default and are discarded by exclude_unset.
    # The non-nullable types still reject an explicitly supplied JSON null.
    title: Title = Field(default=None)
    description: Description = Field(default=None)
    status: TaskStatus = Field(default=None)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TaskStatus
