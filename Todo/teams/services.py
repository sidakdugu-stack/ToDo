from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from database import Team, TeamMember, TeamTask, TeamTaskCompletion, User
from teams.models import TeamRole, TeamCreate, TeamUpdate, TeamInvite, TeamTaskCreate
from database import transaction


class TeamService:
    def __init__(self, db: Session):
        self.db = db

    def create_team(self, user_id: str, team_data: TeamCreate) -> Team:
        """Создание новой команды в транзакции"""
        with transaction(self.db) as db_transaction:
            # Проверяем, нет ли команды с таким именем
            existing_team = db_transaction.query(Team).filter(Team.name == team_data.name).first()
            if existing_team:
                raise HTTPException(400, "Team with this name already exists")

            # Создаем команду
            team = Team(
                name=team_data.name,
                description=team_data.description,
                owner_id=user_id
            )
            db_transaction.add(team)
            db_transaction.flush()  # Получаем ID команды

            # Добавляем создателя как владельца
            team_member = TeamMember(
                team_id=team.id,
                user_id=user_id,
                role=TeamRole.OWNER
            )
            db_transaction.add(team_member)

            return team

    def get_user_teams(self, user_id: str) -> List[Team]:
        """Получение всех команд пользователя"""
        return self.db.query(Team).join(TeamMember).filter(
            TeamMember.user_id == user_id
        ).all()

    def get_team(self, team_id: str, user_id: str) -> Team:
        """Получение команды с проверкой доступа"""
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(404, "Team not found")

        # Проверяем, является ли пользователь участником команды
        membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        ).first()
        if not membership:
            raise HTTPException(403, "Access denied")

        return team

    def update_team(self, team_id: str, user_id: str, team_data: TeamUpdate) -> Team:
        """Обновление команды"""
        team = self.get_team(team_id, user_id)

        # Проверяем права (только владелец и соруководители могут редактировать)
        membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        ).first()

        if membership.role not in [TeamRole.OWNER, TeamRole.CO_OWNER]:
            raise HTTPException(403, "Only owners and co-owners can edit team")

        with transaction(self.db) as db_transaction:
            if team_data.name:
                # Проверяем уникальность имени
                existing = db_transaction.query(Team).filter(
                    Team.name == team_data.name,
                    Team.id != team_id
                ).first()
                if existing:
                    raise HTTPException(400, "Team with this name already exists")
                team.name = team_data.name

            if team_data.description is not None:
                team.description = team_data.description

            return team

    def delete_team(self, team_id: str, user_id: str):
        """Удаление команды"""
        team = self.get_team(team_id, user_id)

        # Проверяем, что пользователь - владелец
        membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        ).first()

        if membership.role != TeamRole.OWNER:
            raise HTTPException(403, "Only team owner can delete the team")

        with transaction(self.db) as db_transaction:
            db_transaction.delete(team)

    def invite_user(self, team_id: str, inviter_id: str, invite_data: TeamInvite) -> Dict[str, Any]:
        """Приглашение пользователя в команду"""
        team = self.get_team(team_id, inviter_id)

        # Проверяем права на приглашение
        membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == inviter_id
        ).first()

        if membership.role not in [TeamRole.OWNER, TeamRole.CO_OWNER]:
            raise HTTPException(403, "Only owners and co-owners can invite users")

        with transaction(self.db) as db_transaction:
            # Проверяем существование пользователя
            user = db_transaction.query(User).filter(User.id == invite_data.user_id).first()
            if not user:
                raise HTTPException(404, "User not found")

            # Проверяем, не является ли пользователь уже участником
            existing_member = db_transaction.query(TeamMember).filter(
                TeamMember.team_id == team_id,
                TeamMember.user_id == invite_data.user_id
            ).first()
            if existing_member:
                raise HTTPException(400, "User is already a team member")

            # Добавляем пользователя в команду
            team_member = TeamMember(
                team_id=team_id,
                user_id=invite_data.user_id,
                role=TeamRole.MEMBER
            )
            db_transaction.add(team_member)

            return {
                "message": f"User {user.username} added to team",
                "team_id": team_id,
                "user_id": invite_data.user_id,
                "username": user.username
            }

    def update_member_role(self, team_id: str, owner_id: str, member_id: str, new_role: TeamRole) -> Dict[str, Any]:
        """Изменение роли участника команды"""
        team = self.get_team(team_id, owner_id)

        # Проверяем, что изменяющий - владелец
        owner_membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == owner_id
        ).first()

        if owner_membership.role != TeamRole.OWNER:
            raise HTTPException(403, "Only team owner can change roles")

        with transaction(self.db) as db_transaction:
            # Находим участника для изменения
            member_membership = db_transaction.query(TeamMember).filter(
                TeamMember.team_id == team_id,
                TeamMember.user_id == member_id
            ).first()

            if not member_membership:
                raise HTTPException(404, "Team member not found")

            member_membership.role = new_role

            user = db_transaction.query(User).filter(User.id == member_id).first()
            return {
                "message": f"Role updated for {user.username}",
                "user_id": member_id,
                "username": user.username,
                "new_role": new_role
            }

    def get_team_members(self, team_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка участников команды"""
        team = self.get_team(team_id, user_id)

        members = self.db.query(TeamMember, User).join(
            User, TeamMember.user_id == User.id
        ).filter(TeamMember.team_id == team_id).all()

        return [
            {
                "user_id": member.TeamMember.user_id,
                "username": member.User.username,
                "role": member.TeamMember.role,
                "joined_at": member.TeamMember.joined_at.isoformat()
            }
            for member in members
        ]

    def remove_member(self, team_id: str, remover_id: str, member_id: str):
        """Удаление участника из команды"""
        team = self.get_team(team_id, remover_id)

        # Проверяем права
        remover_membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == remover_id
        ).first()

        member_membership = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == member_id
        ).first()

        if not member_membership:
            raise HTTPException(404, "Team member not found")

        # Владелец может удалить кого угодно, кроме себя
        # Соруководители могут удалять только обычных участников
        if remover_id == member_id:
            raise HTTPException(400, "Cannot remove yourself from team")

        if remover_membership.role == TeamRole.OWNER:
            # Владелец не может удалить себя
            if member_membership.role == TeamRole.OWNER:
                raise HTTPException(400, "Owner cannot remove themselves")
        elif remover_membership.role == TeamRole.CO_OWNER:
            # Соруководитель может удалять только обычных участников
            if member_membership.role in [TeamRole.OWNER, TeamRole.CO_OWNER]:
                raise HTTPException(403, "Co-owners can only remove regular members")
        else:
            # Обычные участники не могут удалять никого
            raise HTTPException(403, "Regular members cannot remove other members")

        with transaction(self.db) as db_transaction:
            db_transaction.delete(member_membership)

        return {"message": "Member removed from team"}

    def get_team_members_count(self, team_id: str) -> int:
        """Получить количество участников команды"""
        return self.db.query(TeamMember).filter(TeamMember.team_id == team_id).count()


class TeamTaskService:
    def __init__(self, db: Session):
        self.db = db
        self.team_service = TeamService(db)

    def create_team_task(self, team_id: str, user_id: str, task_data: TeamTaskCreate) -> TeamTask:
        """Создание задачи для команды в транзакции"""
        # Проверяем доступ к команде
        self.team_service.get_team(team_id, user_id)

        with transaction(self.db) as db_transaction:
            # Создаем задачу
            task = TeamTask(
                title=task_data.title,
                description=task_data.description,
                team_id=team_id,
                created_by=user_id
            )
            db_transaction.add(task)
            return task

    def get_team_tasks(self, team_id: str, user_id: str) -> List[TeamTask]:
        """Получение всех задач команды"""
        self.team_service.get_team(team_id, user_id)

        tasks = self.db.query(TeamTask).filter(TeamTask.team_id == team_id).all()
        return tasks

    def update_team_task(self, team_id: str, task_id: str, user_id: str, task_data: TeamTaskCreate) -> TeamTask:
        """Обновление задачи команды"""
        self.team_service.get_team(team_id, user_id)

        task = self.db.query(TeamTask).filter(
            TeamTask.id == task_id,
            TeamTask.team_id == team_id
        ).first()

        if not task:
            raise HTTPException(404, "Team task not found")

        with transaction(self.db) as db_transaction:
            # Обновляем задачу
            if task_data.title:
                task.title = task_data.title
            if task_data.description is not None:
                task.description = task_data.description

            return task

    def delete_team_task(self, team_id: str, task_id: str, user_id: str):
        """Удаление задачи команды"""
        self.team_service.get_team(team_id, user_id)

        task = self.db.query(TeamTask).filter(
            TeamTask.id == task_id,
            TeamTask.team_id == team_id
        ).first()

        if not task:
            raise HTTPException(404, "Team task not found")

        with transaction(self.db) as db_transaction:
            db_transaction.delete(task)

    def toggle_task_completion(self, team_id: str, task_id: str, user_id: str, completed: bool) -> Dict[str, Any]:
        """Отметка задачи как выполненной/невыполненной"""
        self.team_service.get_team(team_id, user_id)

        with transaction(self.db) as db_transaction:
            task = db_transaction.query(TeamTask).filter(
                TeamTask.id == task_id,
                TeamTask.team_id == team_id
            ).first()

            if not task:
                raise HTTPException(404, "Team task not found")

            if completed:
                # Добавляем completion
                existing_completion = db_transaction.query(TeamTaskCompletion).filter(
                    TeamTaskCompletion.task_id == task_id,
                    TeamTaskCompletion.user_id == user_id
                ).first()

                if not existing_completion:
                    completion = TeamTaskCompletion(
                        task_id=task_id,
                        user_id=user_id
                    )
                    db_transaction.add(completion)
            else:
                # Удаляем completion
                completion = db_transaction.query(TeamTaskCompletion).filter(
                    TeamTaskCompletion.task_id == task_id,
                    TeamTaskCompletion.user_id == user_id
                ).first()

                if completion:
                    db_transaction.delete(completion)

            # Получаем обновленную информацию о задаче
            completions = db_transaction.query(TeamTaskCompletion).filter(
                TeamTaskCompletion.task_id == task_id
            ).all()

            team_members_count = self.team_service.get_team_members_count(team_id)

            is_fully_completed = len(completions) == team_members_count

            return {
                "task_id": task_id,
                "user_id": user_id,
                "completed": completed,
                "completions_count": len(completions),
                "team_members_count": team_members_count,
                "is_fully_completed": is_fully_completed
            }

    def get_task_completions(self, team_id: str, task_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Получение информации о выполнении задачи"""
        self.team_service.get_team(team_id, user_id)

        completions = self.db.query(TeamTaskCompletion, User).join(
            User, TeamTaskCompletion.user_id == User.id
        ).filter(TeamTaskCompletion.task_id == task_id).all()

        return [
            {
                "user_id": completion.TeamTaskCompletion.user_id,
                "username": completion.User.username,
                "completed_at": completion.TeamTaskCompletion.completed_at.isoformat()
            }
            for completion in completions
        ]