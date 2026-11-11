"""Task CRUD and status filtering."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Task, TaskStatus
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def task_or_404(task_id: int, session: Session) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", status_code=201, response_model=TaskRead)
def create_task(payload: TaskCreate, session: DatabaseSession) -> Task:
    task = Task(**payload.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(session: DatabaseSession, status: TaskStatus | None = None) -> list[Task]:
    statement = select(Task).order_by(Task.id)
    if status is not None:
        statement = statement.where(Task.status == status.value)
    return list(session.scalars(statement))


@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: int, session: DatabaseSession) -> Task:
    return task_or_404(task_id, session)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, session: DatabaseSession) -> Task:
    task = task_or_404(task_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: int, session: DatabaseSession) -> Response:
    task = task_or_404(task_id, session)
    session.delete(task)
    session.commit()
    return Response(status_code=204)
