"""
Minimal WebSocket echo using the built-in client.
"""

from gakido.websocket import WebSocket


def main() -> None:
    host = "echo.websocket.events"
    ws = WebSocket.connect(host, 443, "/", headers=[], tls=True, timeout=10.0)
    ws.send_text("hello websocket")
    opcode, payload = ws.recv()
    print("opcode:", opcode, "payload:", payload.decode(errors="ignore"))
    ws.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("WebSocket error:", exc)
