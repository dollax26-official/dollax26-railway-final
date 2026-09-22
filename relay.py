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
        self.sent = 0          # client -> target  = upload
        self.recv = 0          # target -> client  = download
        self.error = ""
        self._reported_sent = 0
        self._reported_recv = 0

    @property
    def total(self):
        return self.sent + self.recv

    def pending(self):
        return (self.sent - self._reported_sent) + (self.recv - self._reported_recv)

    def take(self):
        """Return (upload_total, download_total) and mark them as reported."""
        self._reported_sent, self._reported_recv = self.sent, self.recv
        return self.sent, self.recv


async def _pump_ws_to_tcp(ws, writer, result: RelayResult, first_payload: bytes, on_bytes):
    try:
        if first_payload:
            writer.write(first_payload)
            await writer.drain()
            result.sent += len(first_payload)
        while True:
            msg = await ws.receive()
            if not isinstance(msg, dict) or msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes") or (msg.get("text") or "").encode()
            if data:
                writer.write(data)
                await writer.drain()
                result.sent += len(data)
                if on_bytes and result.pending() >= REPORT_EVERY:
                    on_bytes(*result.take(), False)
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
                on_bytes(*result.take(), False)
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
    # read the first frame, tolerating leading empty/ping frames (some clients send those)
    data = None
    for _ in range(4):
        try:
            msg = await ws.receive()
        except Exception:
            break
        if not isinstance(msg, dict) or msg.get("type") == "websocket.disconnect":
            break
        chunk = msg.get("bytes") or (msg.get("text") or "").encode()
        if chunk:
            data = chunk
            break
    if not data:
        await ws.close(code=1002)
        return result

    if protocol_name == "vless":
        parsed = protocol.parse_vless_header(data)
        if not parsed or parsed["uuid"] != client["uuid"]:
            await ws.close(code=1008)
            return result
        if parsed["command"] not in (1, 3):
            await ws.close(code=1003)
            return result
        # VLESS response header = version(0) + addon length(0) => exactly TWO bytes.
        # It used to be three, which leaked a NUL byte into the payload and corrupted
        # the very first byte the client received (fatal for a TLS handshake).
        header = b"\x00\x00"
    elif protocol_name == "trojan":
        parsed = protocol.parse_trojan_header(data, protocol.client_secret(inbound, client["uuid"]))
        if not parsed:
            await ws.close(code=1008)
            return result
        if parsed["command"] not in (1, 3):
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
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
        try:
            sock = writer.get_extra_info("socket")
            if sock:
                import socket as _socket
                sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        except Exception:
            pass
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
                on_bytes(*result.take(), True)
            except Exception:
                pass
    return result


# ---------------------------------------------------------------- Xray bridge
async def bridge(ws, upstream_url: str, on_bytes=None):
    """Pipe a client WebSocket into a local WebSocket (the bundled Xray-core inbound).

    The panel stays in the path, so quotas, connection/IP limits and traffic accounting keep
    working, while Xray-core does the protocol work (VMess, Shadowsocks, Reality, UDP, ...).
    """
    import websockets

    result = RelayResult()
    try:
        async with websockets.connect(upstream_url, max_size=None, open_timeout=10) as up:
            async def client_to_core():
                while True:
                    msg = await ws.receive()
                    if not isinstance(msg, dict) or msg.get("type") == "websocket.disconnect":
                        break
                    chunk = msg.get("bytes") or (msg.get("text") or "").encode()
                    if not chunk:
                        continue
                    await up.send(chunk)
                    result.sent += len(chunk)
                    if on_bytes and result.pending() >= REPORT_EVERY:
                        on_bytes(*result.take(), False)

            async def core_to_client():
                async for message in up:
                    data = message if isinstance(message, (bytes, bytearray)) else str(message).encode()
                    if not data:
                        continue
                    await ws.send_bytes(bytes(data))
                    result.recv += len(data)
                    if on_bytes and result.pending() >= REPORT_EVERY:
                        on_bytes(*result.take(), False)

            await asyncio.gather(client_to_core(), core_to_client())
    except Exception as exc:  # noqa: BLE001
        result.error = result.error or f"xray bridge: {exc.__class__.__name__}"
    finally:
        if on_bytes and result.pending() > 0:
            try:
                on_bytes(*result.take(), True)
            except Exception:
                pass
        try:
            await ws.close()
        except Exception:
            pass
    return result
