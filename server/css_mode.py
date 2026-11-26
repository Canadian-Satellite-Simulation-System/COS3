import socket

CSS_HOST = "127.0.0.1"
CSS_CONTROL_PORT = 5001
CSS_TIMEOUT = 3


def send_mode_command(command):
    if command not in ("SIM", "HIL", "STATUS"):
        raise ValueError("Invalid CSS mode command.")

    with socket.create_connection(
        (CSS_HOST, CSS_CONTROL_PORT),
        timeout=CSS_TIMEOUT
    ) as sock:
        sock.sendall(f"{command}\n".encode())

        with sock.makefile("rb") as response:
            reply = response.readline(128).decode().strip()

    if reply not in ("OK SIM", "OK HIL"):
        raise RuntimeError(f"Unexpected CSS response: {reply}")

    mode = reply.split()[1]

    if command != "STATUS" and mode != command:
        raise RuntimeError("CSS mode switch was not confirmed.")

    return {"mode": mode}


def get_mode():
    return send_mode_command("STATUS")


def set_mode(mode):
    if mode not in ("SIM", "HIL"):
        raise ValueError("Mode must be SIM or HIL.")

    return send_mode_command(mode)