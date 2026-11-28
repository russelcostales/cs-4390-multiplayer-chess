"""WebSocket glue. One Client per connection; all game logic stays in server.py."""

import asyncio
import json
import logging
import uuid

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from server import Matchmaker

logger = logging.getLogger(__name__)

HOST = "localhost"
PORT = 8765
STATS_INTERVAL_SECONDS = 1.0


async def _write_loop(websocket, outbox: asyncio.Queue) -> None:
    while True:
        message = await outbox.get()
        await websocket.send(message)


async def _stats_loop(matchmaker: Matchmaker) -> None:
    # the network panel only updates when this shows up
    while True:
        await asyncio.sleep(STATS_INTERVAL_SECONDS)
        matchmaker.send_net_stats()


async def handle(websocket, matchmaker: Matchmaker) -> None:
    loop = asyncio.get_running_loop()
    client = matchmaker.connect(uuid.uuid4().hex)
    outbox: asyncio.Queue = asyncio.Queue()
    client.on_send = lambda message: outbox.put_nowait(json.dumps(message))
    # simulated delay: the event loop drops the packet into the outbox after `delay` seconds
    client.on_send_later = lambda message, delay: loop.call_later(
        delay, outbox.put_nowait, json.dumps(message)
    )
    writer = asyncio.create_task(_write_loop(websocket, outbox))
    try:
        async for raw in websocket:
            matchmaker.handle_message(client, raw)
    except ConnectionClosed:
        pass
    finally:
        matchmaker.disconnect(client)
        writer.cancel()


async def main() -> None:
    matchmaker = Matchmaker()

    async def handler(websocket) -> None:
        await handle(websocket, matchmaker)

    async with serve(handler, HOST, PORT):
        stats_task = asyncio.create_task(_stats_loop(matchmaker))
        logger.info("listening on ws://%s:%s", HOST, PORT)
        try:
            await asyncio.Future()
        finally:
            stats_task.cancel()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())