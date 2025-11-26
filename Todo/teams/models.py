from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class TeamRole(str, Enum):
    OWNER = "owner"
    CO_OWNER = "co_owner"
    MEMBER = "member"

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class TeamInvite(BaseModel):
    user_id: str

class TeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    created_at: str

class TeamMemberResponse(BaseModel):
    user_id: str
    username: str
    role: TeamRole
    joined_at: str

class TeamTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TeamTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class TeamTaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    team_id: str
    created_by: str
    created_at: str
    completions: List[str]  # user_ids who completed the task
    is_completed: bool

class TeamTaskCompletion(BaseModel):
    completed: bool