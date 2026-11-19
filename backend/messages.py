"""Parse and validate client messages before a handler sees them."""

import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError


MAX_MESSAGE_BYTES = 4096


class ErrorCode(str, Enum):
    INVALID_MESSAGE = "INVALID_MESSAGE"
    ALREADY_QUEUED = "ALREADY_QUEUED"
    ALREADY_IN_GAME = "ALREADY_IN_GAME"
    NOT_QUEUED = "NOT_QUEUED"
    RATE_LIMITED = "RATE_LIMITED"


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


ClientMessage = (
    FindMatchMessage
    | CancelMatchMessage
    | CreateLobbyMessage
    | ListLobbiesMessage
    | JoinLobbyMessage
    | LeaveLobbyMessage
)

_MODELS: dict[str, type[_ClientMessage]] = {
    "find_match": FindMatchMessage,
    "cancel_match": CancelMatchMessage,
    "create_lobby": CreateLobbyMessage,
    "list_lobbies": ListLobbiesMessage,
    "join_lobby": JoinLobbyMessage,
    "leave_lobby": LeaveLobbyMessage,
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
