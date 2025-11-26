from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user, UserAuth
from teams.services import TeamService, TeamTaskService
from teams.models import (
    TeamCreate, TeamUpdate, TeamInvite, TeamResponse, TeamMemberResponse,
    TeamTaskCreate, TeamTaskUpdate, TeamTaskResponse, TeamTaskCompletion,
    TeamRole
)

router = APIRouter(prefix="/teams", tags=["teams"])


# 🏢 Управление командами
@router.post("/", response_model=TeamResponse)
def create_team(
        team_data: TeamCreate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание новой команды"""
    team_service = TeamService(db)
    team = team_service.create_team(current_user.user_id, team_data)
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "owner_id": team.owner_id,
        "created_at": team.created_at.isoformat()
    }


@router.get("/", response_model=list[TeamResponse])
def get_my_teams(
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение всех команд пользователя"""
    team_service = TeamService(db)
    teams = team_service.get_user_teams(current_user.user_id)
    return [
        {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "created_at": team.created_at.isoformat()
        }
        for team in teams
    ]


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
        team_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение информации о команде"""
    team_service = TeamService(db)
    team = team_service.get_team(team_id, current_user.user_id)
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "owner_id": team.owner_id,
        "created_at": team.created_at.isoformat()
    }


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
        team_id: str,
        team_data: TeamUpdate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Обновление команды"""
    team_service = TeamService(db)
    team = team_service.update_team(team_id, current_user.user_id, team_data)
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "owner_id": team.owner_id,
        "created_at": team.created_at.isoformat()
    }


@router.delete("/{team_id}")
def delete_team(
        team_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Удаление команды"""
    team_service = TeamService(db)
    team_service.delete_team(team_id, current_user.user_id)
    return {"message": "Team deleted successfully"}


# 👥 Управление участниками
@router.post("/{team_id}/invite")
def invite_to_team(
        team_id: str,
        invite_data: TeamInvite,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Приглашение пользователя в команду"""
    team_service = TeamService(db)
    return team_service.invite_user(team_id, current_user.user_id, invite_data)


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
def get_team_members(
        team_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение списка участников команды"""
    team_service = TeamService(db)
    members = team_service.get_team_members(team_id, current_user.user_id)
    return members


@router.patch("/{team_id}/members/{member_id}/role")
def update_member_role(
        team_id: str,
        member_id: str,
        role: TeamRole,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Изменение роли участника команды"""
    team_service = TeamService(db)
    return team_service.update_member_role(team_id, current_user.user_id, member_id, role)


@router.delete("/{team_id}/members/{member_id}")
def remove_member(
        team_id: str,
        member_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Удаление участника из команды"""
    team_service = TeamService(db)
    return team_service.remove_member(team_id, current_user.user_id, member_id)


# 📋 Управление задачами команды
@router.post("/{team_id}/tasks", response_model=TeamTaskResponse)
def create_team_task(
        team_id: str,
        task_data: TeamTaskCreate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание задачи для команды"""
    task_service = TeamTaskService(db)
    task = task_service.create_team_task(team_id, current_user.user_id, task_data)

    # Получаем информацию о completion
    completions = task_service.get_task_completions(team_id, task.id, current_user.user_id)

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "team_id": task.team_id,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "completions": [comp["user_id"] for comp in completions],
        "is_completed": False  # Новая задача не выполнена
    }


@router.get("/{team_id}/tasks", response_model=list[TeamTaskResponse])
def get_team_tasks(
        team_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение всех задач команды"""
    task_service = TeamTaskService(db)
    tasks = task_service.get_team_tasks(team_id, current_user.user_id)

    result = []
    for task in tasks:
        completions = task_service.get_task_completions(team_id, task.id, current_user.user_id)
        team_members_count = len(TeamService(db).get_team_members(team_id, current_user.user_id))

        result.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "team_id": task.team_id,
            "created_by": task.created_by,
            "created_at": task.created_at.isoformat(),
            "completions": [comp["user_id"] for comp in completions],
            "is_completed": len(completions) == team_members_count
        })

    return result


@router.put("/{team_id}/tasks/{task_id}", response_model=TeamTaskResponse)
def update_team_task(
        team_id: str,
        task_id: str,
        task_data: TeamTaskUpdate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Обновление задачи команды"""
    task_service = TeamTaskService(db)
    task = task_service.update_team_task(team_id, task_id, current_user.user_id, task_data)

    completions = task_service.get_task_completions(team_id, task.id, current_user.user_id)
    team_members_count = len(TeamService(db).get_team_members(team_id, current_user.user_id))

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "team_id": task.team_id,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "completions": [comp["user_id"] for comp in completions],
        "is_completed": len(completions) == team_members_count
    }


@router.delete("/{team_id}/tasks/{task_id}")
def delete_team_task(
        team_id: str,
        task_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Удаление задачи команды"""
    task_service = TeamTaskService(db)
    task_service.delete_team_task(team_id, task_id, current_user.user_id)
    return {"message": "Team task deleted successfully"}


@router.patch("/{team_id}/tasks/{task_id}/completion")
def toggle_task_completion(
        team_id: str,
        task_id: str,
        completion_data: TeamTaskCompletion,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Отметка задачи как выполненной/невыполненной"""
    task_service = TeamTaskService(db)
    return task_service.toggle_task_completion(
        team_id, task_id, current_user.user_id, completion_data.completed
    )


@router.get("/{team_id}/tasks/{task_id}/completions")
def get_task_completions(
        team_id: str,
        task_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получение информации о выполнении задачи"""
    task_service = TeamTaskService(db)
    return task_service.get_task_completions(team_id, task_id, current_user.user_id)