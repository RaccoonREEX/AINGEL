"""Accept forwarded HTTPS/client IP only from an explicitly trusted reverse proxy.

The proxy must overwrite X-Real-IP and X-Forwarded-Proto and must be the only
network path to ASGI. This applies equally to HTTP and WebSocket handshakes.
"""
from ipaddress import ip_address


class TrustedProxyASGI:
    def __init__(self, application, networks):
        self.application = application
        self.networks = networks

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.application(scope, receive, send)
        try:
            peer = ip_address(scope["client"][0])
            headers = scope.get("headers", [])
            real_ips = [v for k, v in headers if k.lower() == b"x-real-ip"]
            protocols = [v for k, v in headers if k.lower() == b"x-forwarded-proto"]
            if not any(peer in network for network in self.networks):
                raise ValueError
            if len(real_ips) != 1 or len(protocols) != 1 or protocols[0] != b"https":
                raise ValueError
            client_ip = ip_address(real_ips[0].decode("ascii"))
        except (ValueError, TypeError, IndexError, KeyError, UnicodeDecodeError):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4403})
            else:
                await send({"type": "http.response.start", "status": 403, "headers": []})
                await send({"type": "http.response.body", "body": b"Forbidden"})
            return
        scope = dict(scope)
        scope["client"] = (str(client_ip), scope["client"][1])
        scope["scheme"] = "wss" if scope["type"] == "websocket" else "https"
        return await self.application(scope, receive, send)
