"""
Minimal agent example (Python)

Usage:
  python agent.py --backend http://localhost:8000 --machine-id <id> --token <token> --allow C:/data --allow D:/docs

The agent opens a WebSocket to `/api/v1/machines/ws/{machine_id}` using the
`X-Machine-Token` header and
responds to simple commands: `list` and `read`.
"""
import argparse
import asyncio
import base64
import json
import os

try:
    from websockets.exceptions import ConnectionClosed
except Exception:  # pragma: no cover - compatibility fallback
    ConnectionClosed = Exception

import websockets


def _normalize(path):
    return os.path.abspath(os.path.expanduser(path))


def _is_allowed(target_path, allowed_paths):
    target = _normalize(target_path)
    for base in allowed_paths:
        try:
            if os.path.commonpath([target, _normalize(base)]) == _normalize(base):
                return True
        except ValueError:
            continue
    return False


def _resolve_requested_path(requested_path, allowed_paths):
    if not allowed_paths:
        raise RuntimeError("machine-policy-not-registered")
    base_path = _normalize(allowed_paths[0])
    if not requested_path or requested_path in (".", "./", ".\\"):
        return base_path
    if os.path.isabs(requested_path):
        return _normalize(requested_path)
    return _normalize(os.path.join(base_path, requested_path))


def _connect_kwargs(token):
    headers = [("X-Machine-Token", token)]
    try:
        return {"additional_headers": headers}
    except TypeError:
        return {"extra_headers": headers}


async def handle_connection(uri, machine_id, token, allowed_paths):
    ws_uri = f"{uri.rstrip('/')}/api/v1/machines/ws/{machine_id}"
    try:
        ws_cm = websockets.connect(ws_uri, **_connect_kwargs(token))
    except TypeError:
        ws_cm = websockets.connect(ws_uri, extra_headers={"X-Machine-Token": token})

    async with ws_cm as ws:
        print("Conectado ao servidor como", machine_id)
        await ws.send(json.dumps({"type": "hello", "allowed_paths": allowed_paths, "request_id": "hello"}))
        ack_raw = await ws.recv()
        ack = json.loads(ack_raw)
        if not ack.get("ok"):
            raise RuntimeError(ack.get("error", "registration-failed"))

        try:
            async for msg in ws:
                try:
                    payload = json.loads(msg)
                except Exception:
                    continue

                cmd = payload.get("cmd")
                if cmd == "list":
                    path = _resolve_requested_path(payload.get("path"), allowed_paths)
                    try:
                        if not _is_allowed(path, allowed_paths):
                            raise PermissionError("path not allowed")
                        items = os.listdir(path)
                        await ws.send(json.dumps({"ok": True, "items": items, "path": path, "request_id": payload.get("request_id")}))
                    except Exception as e:
                        await ws.send(json.dumps({"ok": False, "error": str(e), "request_id": payload.get("request_id")}))

                elif cmd == "read":
                    path = _resolve_requested_path(payload.get("path"), allowed_paths)
                    max_bytes = int(payload.get("max_bytes", 65536))
                    try:
                        if not _is_allowed(path, allowed_paths):
                            raise PermissionError("path not allowed")
                        with open(path, "rb") as fh:
                            data = fh.read(max_bytes)
                        b64 = base64.b64encode(data).decode("ascii")
                        await ws.send(json.dumps({"ok": True, "data_b64": b64, "path": path, "request_id": payload.get("request_id")}))
                    except Exception as e:
                        await ws.send(json.dumps({"ok": False, "error": str(e), "request_id": payload.get("request_id")}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "unknown-cmd", "request_id": payload.get("request_id")}))
        except ConnectionClosed:
            print("Conexão fechada")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--allow", action="append", dest="allowed", default=[])
    args = parser.parse_args()

    allowed_paths = [path for path in args.allowed if path and path.strip()] or [os.getcwd()]

    asyncio.run(
        handle_connection(
            args.backend.replace('http://', 'ws://').replace('https://', 'wss://'),
            args.machine_id,
            args.token,
            allowed_paths,
        )
    )


if __name__ == "__main__":
    main()
