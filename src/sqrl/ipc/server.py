"""
JSON-RPC 2.0 server over Unix socket.

Handles communication between Rust daemon and Python Memory Service.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

# JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Default socket path
DEFAULT_SOCKET_PATH = "/tmp/sqrl_agent.sock"


@dataclass
class RPCError:
    """JSON-RPC 2.0 error."""

    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class RPCRequest:
    """JSON-RPC 2.0 request."""

    method: str
    params: dict
    id: Optional[int] = None

    @classmethod
    def from_json(cls, data: str) -> "RPCRequest":
        """Parse JSON-RPC request."""
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Parse error: {e}")

        if obj.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC version")

        method = obj.get("method")
        if not isinstance(method, str):
            raise ValueError("Missing or invalid method")

        params = obj.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("Params must be object")

        return cls(
            method=method,
            params=params,
            id=obj.get("id"),
        )


def make_response(result: Any, request_id: Optional[int]) -> str:
    """Create JSON-RPC 2.0 response."""
    return json.dumps({
        "jsonrpc": "2.0",
        "result": result,
        "id": request_id,
    })


def make_error(error: RPCError, request_id: Optional[int]) -> str:
    """Create JSON-RPC 2.0 error response."""
    return json.dumps({
        "jsonrpc": "2.0",
        "error": error.to_dict(),
        "id": request_id,
    })


MethodHandler = Callable[[dict], Any]


class IPCServer:
    """
    JSON-RPC 2.0 server over Unix socket.

    Usage:
        server = IPCServer()
        server.register("ingest_chunk", ingest_handler)
        server.register("embed_text", embed_handler)
        await server.start()
    """

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path
        self.handlers: dict[str, MethodHandler] = {}
        self._server: Optional[asyncio.Server] = None

    def register(self, method: str, handler: MethodHandler) -> None:
        """Register a method handler."""
        self.handlers[method] = handler

    async def _handle_request(self, data: str) -> str:
        """Process a single JSON-RPC request."""
        request_id = None

        try:
            request = RPCRequest.from_json(data)
            request_id = request.id

            # Find handler
            handler = self.handlers.get(request.method)
            if handler is None:
                return make_error(
                    RPCError(METHOD_NOT_FOUND, f"Method not found: {request.method}"),
                    request_id,
                )

            # Call handler
            try:
                # Support async handlers
                result = handler(request.params)
                if asyncio.iscoroutine(result):
                    result = await result
                return make_response(result, request_id)
            except Exception as e:
                # Check for custom error codes
                if hasattr(e, "code"):
                    return make_error(
                        RPCError(e.code, str(e)),
                        request_id,
                    )
                return make_error(
                    RPCError(INTERNAL_ERROR, f"Internal error: {e}"),
                    request_id,
                )

        except ValueError as e:
            return make_error(
                RPCError(PARSE_ERROR if "Parse error" in str(e) else INVALID_REQUEST, str(e)),
                request_id,
            )

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single client connection."""
        try:
            while True:
                # Read line-delimited JSON
                data = await reader.readline()
                if not data:
                    break

                request_str = data.decode("utf-8").strip()
                if not request_str:
                    continue

                response_str = await self._handle_request(request_str)

                # Write response with newline delimiter
                writer.write((response_str + "\n").encode("utf-8"))
                await writer.drain()

        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> None:
        """Start the server."""
        # Remove existing socket file
        socket_path = Path(self.socket_path)
        if socket_path.exists():
            socket_path.unlink()

        # Create parent directory if needed
        socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(socket_path),
        )

        # Set permissions (owner read/write only)
        os.chmod(self.socket_path, 0o600)

    async def serve_forever(self) -> None:
        """Serve until cancelled."""
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Clean up socket file
        socket_path = Path(self.socket_path)
        if socket_path.exists():
            socket_path.unlink()


async def start_server(
    handlers: dict[str, MethodHandler],
    socket_path: str = DEFAULT_SOCKET_PATH,
) -> IPCServer:
    """
    Start an IPC server with the given handlers.

    Args:
        handlers: Dict mapping method names to handler functions
        socket_path: Unix socket path

    Returns:
        Running IPCServer instance
    """
    server = IPCServer(socket_path)
    for method, handler in handlers.items():
        server.register(method, handler)
    await server.start()
    return server
