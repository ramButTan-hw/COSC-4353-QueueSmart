"""Strict event models with aliases matching the existing browser API."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

Identifier = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)]
UserId = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=254)]
PositiveInteger = Annotated[int, Field(strict=True, ge=1, le=9007199254740991)]


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always", validate_by_name=True)
    participation_id: Identifier = Field(alias="participationId")


class JoinedEvent(Event):
    type: Literal["joined"]
    user_id: UserId = Field(alias="userId")
    service_id: PositiveInteger = Field(alias="serviceId")
    service_name: Identifier = Field(alias="serviceName")
    position: PositiveInteger
    queue_open: StrictBool = Field(alias="queueOpen")


class PositionEvent(Event):
    type: Literal["position"]
    position: PositiveInteger
    queue_open: StrictBool = Field(alias="queueOpen")


class CompletedEvent(Event):
    type: Literal["served", "left", "removed"]


QueueEvent = Annotated[JoinedEvent | PositionEvent | CompletedEvent, Field(discriminator="type")]


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always", validate_by_name=True)
    events: Annotated[list[QueueEvent], Field(min_length=1, max_length=1000)]
