from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RefereeAction(str, Enum):
    free_kick = "free_kick"
    penalty_shot = "penalty_shot"
    yellow_card = "yellow_card"
    red_card = "red_card"


class PlayerFlopDetails(BaseModel):
    player_name: Optional[str] = Field(
        default=None, description="The name of the flopping player, if identifiable."
    )
    player_team_name: Optional[str] = Field(
        default=None,
        description="The team name of the flopping player, if identifiable.",
    )
    injured: bool = Field(
        ..., description="Is the player actually injured or just faking?"
    )
    flop_start_video_time: int = Field(
        ...,
        ge=0,
        description="Flop start time in seconds from the start of the provided video.",
    )
    flop_end_video_time: Optional[int] = Field(
        default=None,
        ge=0,
        description="Flop end time in seconds from the start of the provided video. May be missing if not observed in this segment.",
    )
    flop_start_game_time: str = Field(
        ...,
        pattern=r"^\d{1,2}:\d{2}$",
        description="Flop start time as shown in the game clock (MM:SS format).",
    )
    flop_end_game_time: Optional[str] = Field(
        default=None,
        pattern=r"^\d{1,2}:\d{2}$",
        description="Flop end time as shown in the game clock (MM:SS format). May be missing if not observed in this segment.",
    )


class RefereeDecision(BaseModel):
    action: RefereeAction = Field(..., description="Type of referee decision.")
    offending_team: Optional[str] = Field(
        default=None, description="The team receiving the penalty or foul decision."
    )


class FlopEvent(BaseModel):
    players: Optional[List[PlayerFlopDetails]] = Field(
        default=None,
        description="List of players involved in the flop, including their team, injury status, and individual timestamps.",
    )
    referee_decisions: Optional[List[RefereeDecision]] = Field(
        default=None,
        description="List of referee decisions, including the team that committed the foul or simulation.",
    )


class ImageAnalysisResponse(BaseModel):
    # flop_detected: bool = Field(..., description="Is a flop detected in this segment?")
    flops: List[FlopEvent] = Field(
        ..., description="List of detected flop events in the video."
    )


### previous schema


# class RefereeAction(str, Enum):
#     free_kick = "free_kick"
#     penalty_shot = "penalty_shot"
#     yellow_card = "yellow_card"
#     red_card = "red_card"


# class ImageAnalysisResponse(BaseModel):
#     flop_detected: bool = Field(..., description="Is a flop detected in this segment?")
#     player_name: Optional[str] = Field(
#         default=None, description="The name of the flopping player, if identifiable."
#     )
#     player_team_name: Optional[str] = Field(
#         default=None,
#         description="The team name of the flopping player, if identifiable.",
#     )
#     injured: bool = Field(
#         ..., description="Is the player actually injured or just faking?"
#     )
#     referee_action: Optional[List[RefereeAction]] = Field(
#         default=None, description="Referee's decision regarding the flop."
#     )
#     flop_start_video_time: float = Field(
#         ...,
#         ge=0,
#         description="Flop start time in seconds from the start of the provided video.",
#     )
#     flop_end_video_time: Optional[float] = Field(
#         default=None,
#         ge=0,
#         description="Flop end time in seconds from the start of the provided video. May be missing if not observed in this segment.",
#     )
#     flop_start_game_time: str = Field(
#         ...,
#         pattern=r"^\d{1,2}:\d{2}$",
#         description="Flop start time as shown in the game clock (MM:SS format).",
#     )
#     flop_end_game_time: Optional[str] = Field(
#         default=None,
#         pattern=r"^\d{1,2}:\d{2}$",
#         description="Flop end time as shown in the game clock (MM:SS or HH:MM format). May be missing if not observed in this segment.",
#     )
