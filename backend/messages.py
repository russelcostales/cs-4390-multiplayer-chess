"""Parse and validate client messages before a handler sees them."""

import json
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic import BaseModel, ConfigDict, ValidationError


MAX_MESSAGE_BYTES = 4096


class ErrorCode(str, Enum):
    INVALID_MESSAGE = "INVALID_MESSAGE"
    ALREADY_QUEUED = "ALREADY_QUEUED"
    ALREADY_IN_GAME = "ALREADY_IN_GAME"
    NOT_QUEUED = "NOT_QUEUED"
    RATE_LIMITED = "RATE_LIMITED"
    LOBBY_NOT_FOUND = "LOBBY_NOT_FOUND"
    LOBBY_FULL = "LOBBY_FULL"
    WRONG_PASSCODE = "WRONG_PASSCODE"
    ALREADY_IN_LOBBY = "ALREADY_IN_LOBBY"
    INVALID_NAME = "INVALID_NAME"
    NOT_IN_LOBBY = "NOT_IN_LOBBY"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    GAME_OVER = "GAME_OVER"
    NOT_IN_GAME = "NOT_IN_GAME"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    ILLEGAL_MOVE = "ILLEGAL_MOVE"
    PROMOTION_REQUIRED = "PROMOTION_REQUIRED"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_DRAW_OFFER = "INVALID_DRAW_OFFER"


class MessageRejected(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


def error_payload(code: ErrorCode, message: str) -> dict[str, str]:
    return {"type": "error", "code": code.value, "message": message}


class _ClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindMatchMessage(_ClientMessage):
    type: Literal["find_match"]


class CancelMatchMessage(_ClientMessage):
    type: Literal["cancel_match"]

class CreateLobbyMessage(_ClientMessage):
    type: Literal["create_lobby"]
    name: str
    passcode: str | None = None


class ListLobbiesMessage(_ClientMessage):
    type: Literal["list_lobbies"]


class JoinLobbyMessage(_ClientMessage):
    type: Literal["join_lobby"]
    lobbyId: str
    passcode: str | None = None


class LeaveLobbyMessage(_ClientMessage):
    type: Literal["leave_lobby"]


class MoveMessage(_ClientMessage):
    type: Literal["move"]
    move: str

class OfferDrawMessage(_ClientMessage):
    type: Literal["offer_draw"]

class RespondDrawMessage(_ClientMessage):
    type: Literal["respond_draw"]
    accept: bool

class ResignMessage(_ClientMessage):
    type: Literal["resign"]

class CursorMessage(_ClientMessage):
    type: Literal["cursor"]
    # 0-1 instead of pixels so it doesn't care how big each player's board is
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)

class NetSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # same limits as LOSS_PERCENT_MAX and DELAY_MS_MAX in frontend/src/types/network.ts
    lossPercent: float = Field(ge=0, le=50)
    delayMs: float = Field(ge=0, le=500)
    deltaCompression: bool
    huffmanCoding: bool


class NetConfigMessage(_ClientMessage):
    type: Literal["net_config"]
    config: NetSettings


class NetResetStatsMessage(_ClientMessage):
    type: Literal["net_reset_stats"]

ClientMessage = (
    FindMatchMessage
    | CancelMatchMessage
    | CreateLobbyMessage
    | ListLobbiesMessage
    | JoinLobbyMessage
    | LeaveLobbyMessage
    | MoveMessage
    | OfferDrawMessage
    | RespondDrawMessage
    | ResignMessage
    | CursorMessage
    | NetConfigMessage
    | NetResetStatsMessage
)

_MODELS: dict[str, type[_ClientMessage]] = {
    "find_match": FindMatchMessage,
    "cancel_match": CancelMatchMessage,
    "create_lobby": CreateLobbyMessage,
    "list_lobbies": ListLobbiesMessage,
    "join_lobby": JoinLobbyMessage,
    "leave_lobby": LeaveLobbyMessage,
    "move": MoveMessage,
    "offer_draw": OfferDrawMessage,
    "respond_draw": RespondDrawMessage,
    "resign": ResignMessage,
    "cursor": CursorMessage,
    "net_config": NetConfigMessage,
    "net_reset_stats": NetResetStatsMessage,
}


def parse_client_message(raw: object, *, max_bytes: int = MAX_MESSAGE_BYTES) -> ClientMessage:
    data = _load_json(_decode(raw, max_bytes))
    if not isinstance(data, dict):
        raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message")

    message_type = data.get("type")
    if not isinstance(message_type, str):
        raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message")

    model = _MODELS.get(message_type)
    if model is None:
        raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Unknown message type")

    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message") from exc
    if isinstance(
        parsed,
        (
            FindMatchMessage,
            CancelMatchMessage,
            CreateLobbyMessage,
            ListLobbiesMessage,
            JoinLobbyMessage,
            LeaveLobbyMessage,
            MoveMessage,
            OfferDrawMessage,
            RespondDrawMessage,
            ResignMessage,
            CursorMessage,
            NetConfigMessage,
            NetResetStatsMessage,
        ),
    ):
        return parsed
    raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Unknown message type")


def _decode(raw: object, max_bytes: int) -> str:
    if isinstance(raw, str):
        # A longer character count cannot fit in max_bytes of UTF-8.
        if len(raw) > max_bytes:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Message exceeds maximum size")
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message") from exc
        if len(encoded) > max_bytes:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Message exceeds maximum size")
        return raw

    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > max_bytes:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Message exceeds maximum size")
        try:
            return bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message") from exc

    raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Invalid message")


def _load_json(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Malformed JSON") from exc
