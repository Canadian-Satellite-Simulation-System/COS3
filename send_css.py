#!/usr/bin/env python3
"""Simulate an ESP32 by sending six CSS voltages to NOS3 over TCP."""
import argparse
import math
import socket
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--interval', type=float, default=1.0)
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        print(f'Connected to {args.host}:{args.port}; Ctrl+C to stop')
        tick = 0
        while True:
            # All values are in volts. Changing CSS0 makes updates easy to spot.
            values = [round(0.5 + 0.25 * math.sin(tick * 0.5), 3),
                      1.0, 1.5, 2.0, 2.5, 3.0]
            message = ','.join(f'{value:.3f}' for value in values) + '\n'
            connection.sendall(message.encode('ascii'))
            print('Sent:', message.strip(), flush=True)
            tick += 1
            time.sleep(args.interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.')
    except OSError as exc:
        raise SystemExit(f'TCP connection error: {exc}')
