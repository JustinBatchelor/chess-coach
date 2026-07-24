from typing import Literal

from pydantic import BaseModel, Field


class GameCreate(BaseModel):
    color: Literal["white", "black", "random"] = "random"
    difficulty: Literal["beginner", "easy", "medium", "hard", "expert", "maximum"] = "medium"
    time_control: Literal["3+2", "5+0", "10+0", "15+10"] = "10+0"


class MoveCreate(BaseModel):
    uci: str = Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")
    expected_ply: int = Field(ge=0)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=80)

