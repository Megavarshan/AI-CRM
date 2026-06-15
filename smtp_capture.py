"""
Local SMTP capture server for verifying the REAL email send path without a
live provider. Listens on localhost:1025 and writes every received message to
D:/CRM/.captured_mail/ as a .eml file. Nothing is actually delivered.

Run:  python smtp_capture.py
Point channel/.env at it: SMTP_HOST=localhost SMTP_PORT=1025 SMTP_USE_TLS=false
"""

import asyncio
import os
import time

from aiosmtpd.controller import Controller

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".captured_mail")
os.makedirs(OUT, exist_ok=True)


class Handler:
    async def handle_DATA(self, server, session, envelope):
        ts = time.strftime("%Y%m%d_%H%M%S")
        fn = os.path.join(OUT, f"{ts}_{envelope.rcpt_tos[0].replace('@', '_at_')}.eml")
        with open(fn, "wb") as f:
            f.write(envelope.content)
        print(f"[CAPTURED] -> {envelope.rcpt_tos} ({len(envelope.content)} bytes) saved {os.path.basename(fn)}")
        return "250 Message accepted for delivery"


if __name__ == "__main__":
    controller = Controller(Handler(), hostname="127.0.0.1", port=1025)
    controller.start()
    print("SMTP capture listening on 127.0.0.1:1025 — Ctrl+C to stop. Saving to", OUT)
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()
