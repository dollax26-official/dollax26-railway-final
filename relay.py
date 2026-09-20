"""
Dollax Panel — the actual proxy.

Port of the Worker's relay(): it terminates the WebSocket, decodes the request
(VLESS or Trojan), opens a plain TCP connection to the target, and pipes bytes
both ways. Byte counters are reported back through a callback so the panel can
enforce quotas and show usage.

Served natively: VLESS-over-WS, Trojan-over-WS.
Not served here: VMess / Shadowsocks (they are not WebSocket protocols — the
panel still generates their configs and an Xray bridge bundle).
"""
import asyncio
import logging

import protocol

log = logging.getLogger("dollax.relay")

CHUNK = 65536
IDLE_TIMEOUT = float(600)
REPORT_EVERY = 128 * 1024      # flush usage to the DB at least this often


class RelayResult:
    def __init__(self):
        self.sent = 0          # client -> target
        self.recv = 0          # target -> client
        self.error = ""
        self._reported = 0

    @property
    def total(self):
        return self.sent + self.recv

    def pending(self):
        return self.total - self._reported

    def take(self):
        self._reported = self.total
        return self.total


async def _pump_ws_to_tcp(ws, writer, result: RelayResult, first_payload: bytes, on_bytes):
    try:
        if first_payload:
            writer.write(first_payload)
            await writer.drain()
            result.sent += len(first_payload)
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data:
                writer.write(data)
                await writer.drain()
                result.sent += len(data)
                if on_bytes and result.pending() >= REPORT_EVERY:
                    on_bytes(result.take(), False)
    except Exception as exc:  # noqa: BLE001 - any socket/WS error ends the pump
        result.error = result.error or f"upstream: {exc.__class__.__name__}"
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _pump_tcp_to_ws(reader, ws, result: RelayResult, on_bytes):
    try:
        while True:
            data = await asyncio.wait_for(reader.read(CHUNK), timeout=IDLE_TIMEOUT)
            if not data:
                break
            await ws.send_bytes(data)
            result.recv += len(data)
            if on_bytes and result.pending() >= REPORT_EVERY:
                on_bytes(result.take(), False)
    except asyncio.TimeoutError:
        result.error = result.error or "idle timeout"
    except Exception as exc:  # noqa: BLE001
        result.error = result.error or f"client: {exc.__class__.__name__}"
    finally:
        try:
            await ws.close()
        except Exception:
            pass


async def handle(ws, inbound: dict, client: dict, on_bytes=None, already_accepted=False):
    """Terminate one client connection. Returns a RelayResult."""
    result = RelayResult()
    protocol_name = protocol.clean_protocol(inbound.get("protocol"))

    if not already_accepted:
        await ws.accept()
    try:
        first = await ws.receive()
    except Exception:
        await ws.close(code=1002)
        return result

    data = first.get("bytes") if isinstance(first, dict) else None
    if not data:
        await ws.close(code=1002)
        return result

    if protocol_name == "vless":
        parsed = protocol.parse_vless_header(data)
        if not parsed or parsed["uuid"] != client["uuid"]:
            await ws.close(code=1008)
            return result
        if parsed["command"] != 1:
            await ws.close(code=1003)   # UDP is not supported by this relay
            return result
        header = b"\x00\x00\x00"        # VLESS success response (no addons)
    elif protocol_name == "trojan":
        parsed = protocol.parse_trojan_header(data, protocol.client_secret(inbound, client["uuid"]))
        if not parsed:
            await ws.close(code=1008)
            return result
        if parsed["command"] != 1:
            await ws.close(code=1003)
            return result
        header = None
    else:
        await ws.close(code=1003)       # vmess / shadowsocks: not served natively
        return result

    host, port = parsed["host"], parsed["port"]
    if not host or not port:
        await ws.close(code=1002)
        return result

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=15)
    except Exception as exc:  # noqa: BLE001
        log.warning("connect %s:%s failed: %s", host, port, exc)
        await ws.close(code=1011)
        return result

    try:
        if header:
            await ws.send_bytes(header)
        payload = bytes(data[parsed["offset"]:])
        await asyncio.gather(
            _pump_ws_to_tcp(ws, writer, result, payload, on_bytes),
            _pump_tcp_to_ws(reader, ws, result, on_bytes),
        )
    except BaseException:  # cancellation must still report the bytes we moved
        raise
    finally:
        try:
            writer.close()
        except Exception:
            pass
        if on_bytes and result.pending() > 0:
            try:
                on_bytes(result.take(), True)
            except Exception:
                pass
    return result
