#!/usr/bin/env python3
"""apptest-network-chaos — fault-injecting reverse proxy. Standard library only
(Python 3.9+); runs on any operating system.

The app (if its base URL can change in tests) is pointed at http://localhost:<port>; the proxy forwards
requests to --upstream (a MOCK or STAGING server, NC-P1) and injects faults into requests matching a rule.
It does not run against a production server (--confirm-nonprod if the name does not look like mock / staging).

    python3 -I nc_proxy.py --upstream https://staging.example.com [--port 8899]
        [--rule '<regex METHOD /path>' '<fault>' ...] [--rate 1.0] [--seed 1] [--log requests.jsonl]
    python3 -I nc_proxy.py --self-test

Fault (per rule; with @N appended, only on the first N matches):
  pass              leave alone (for rule ordering)
  delay:MS          wait MS milliseconds, then forward
  status:CODE       return CODE without reaching the server (e.g. 500, 503, 401, 429)
  drop              close the connection without responding
  reset             reset the connection (RST)
  hang:SEC          send nothing for SEC seconds, then close (timeout test)
  truncate:PERCENT  forward, send only PERCENT of the body, close (partial response)
  garbage           200 + corrupt JSON
  slow:BPS          send the body at BPS bytes per second
Rules are tried in order; the first match applies. Match text: "METHOD /path?query".
"""
from __future__ import annotations

import argparse
import http.client
import http.server
import ipaddress
import json
import random
import re
import socket
import socketserver
import ssl
import struct
import sys
import threading
import time
import urllib.parse

for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length"}
NONPROD = re.compile(r"(?i)(^|[.-])(staging|stage|stg|dev|develop|test|testing|sandbox|mock|qa|uat|local|preview|"
                     r"demo|fake|stub)([.-]|$)")
FAULT = re.compile(r"^(pass|drop|reset|garbage|delay:\d+|status:\d{3}|hang:\d+(\.\d+)?|truncate:\d{1,3}|slow:\d+)"
                   r"(@\d+)?$")


def nonprod_host(host: str) -> bool:
    h = (host or "").split(":")[0].strip("[]").lower()
    if h in ("localhost", "") or h.endswith(".local") or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        return bool(NONPROD.search(h))


class Rule:
    def __init__(self, pattern: str, fault: str):
        if not FAULT.match(fault):
            raise ValueError(f"unknown fault: {fault}")
        self.rx = re.compile(pattern)
        self.text = pattern
        self.fault, _, limit = fault.partition("@")
        self.limit = int(limit) if limit else None
        self.hits = 0
        self.lock = threading.Lock()

    def take(self, target: str) -> bool:
        if not self.rx.search(target):
            return False
        with self.lock:
            if self.limit is not None and self.hits >= self.limit:
                return False
            self.hits += 1
            return True


class Chaos:
    def __init__(self, upstream: str, rules, rate: float, seed: int, log_path=None, timeout: float = 30.0,
                 quiet: bool = False):
        u = urllib.parse.urlsplit(upstream)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ValueError("--upstream must look like http(s)://server")
        self.scheme, self.netloc, self.base = u.scheme, u.netloc, u.path.rstrip("/")
        self.rules, self.rate = rules, rate
        self.rnd = random.Random(seed)
        self.rnd_lock = threading.Lock()
        self.log_path = log_path
        self.log_lock = threading.Lock()
        self.timeout = timeout
        self.quiet = quiet

    def pick(self, target: str):
        for r in self.rules:
            if r.take(target):
                with self.rnd_lock:
                    hit = self.rnd.random() < self.rate
                return r.fault if hit else "pass"
        return "pass"

    def log(self, rec):
        line = json.dumps(rec, ensure_ascii=False)
        if not self.quiet:
            print(line, flush=True)
        if self.log_path:
            with self.log_lock, open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def forward(self, method, path, headers, body):
        conn_cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        kw = {"context": ssl.create_default_context()} if self.scheme == "https" else {}
        conn = conn_cls(self.netloc, timeout=self.timeout, **kw)
        try:
            hdrs = {k: v for k, v in headers.items() if k.lower() not in HOP}
            hdrs["Host"] = self.netloc
            conn.request(method, self.base + path, body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, resp.reason, [(k, v) for k, v in resp.getheaders() if k.lower() not in HOP], data
        finally:
            conn.close()


def make_handler(chaos: Chaos):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "apptest-chaos"

        def log_message(self, *a):  # we have our own log
            pass

        def _body(self):
            if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                out = bytearray()
                while True:
                    size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                    if size == 0:
                        self.rfile.readline()
                        return bytes(out)
                    out += self.rfile.read(size)
                    self.rfile.readline()
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else None

        def _send(self, status, reason, headers, data, keep=True):
            self.send_response(status, reason)
            for k, v in headers:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            if not keep:
                self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _handle(self):
            t0 = time.time()
            target = f"{self.command} {self.path}"
            fault = chaos.pick(target)
            body = self._body()
            kind, _, arg = fault.partition(":")
            rec = {"time": time.strftime("%H:%M:%S"), "request": target, "fault": fault}
            try:
                if kind == "delay":
                    time.sleep(int(arg) / 1000)
                if kind == "status":
                    payload = json.dumps({"error": "injected", "status": int(arg)}).encode()
                    self._send(int(arg), None, [("Content-Type", "application/json")], payload)
                    rec["status"] = int(arg)
                elif kind == "drop":
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                elif kind == "reset":
                    self.close_connection = True
                    self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                    self.connection.close()
                elif kind == "hang":
                    time.sleep(float(arg))
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                elif kind == "garbage":
                    self._send(200, None, [("Content-Type", "application/json")], b'{"data": [1, 2,, "\xff')
                    rec["status"] = 200
                else:
                    status, reason, headers, data = chaos.forward(self.command, self.path, dict(self.headers), body)
                    rec["status"] = status
                    if kind == "truncate":
                        cut = data[: len(data) * int(arg) // 100]
                        self.send_response(status, reason)
                        for k, v in headers:
                            self.send_header(k, v)
                        self.send_header("Content-Length", str(len(data)))  # promises full length, sends half the body
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.wfile.write(cut)
                        self.wfile.flush()
                        self.close_connection = True
                    elif kind == "slow":
                        bps = max(1, int(arg))
                        self.send_response(status, reason)
                        for k, v in headers:
                            self.send_header(k, v)
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        step = max(1, bps // 10)
                        for i in range(0, len(data), step):
                            self.wfile.write(data[i:i + step])
                            self.wfile.flush()
                            time.sleep(step / bps)
                    else:
                        self._send(status, reason, headers, data)
            except (OSError, http.client.HTTPException) as e:
                rec["proxy_error"] = f"{type(e).__name__}: {e}"
                try:
                    self._send(502, "Bad Gateway", [("Content-Type", "text/plain")], b"upstream error", keep=False)
                except OSError:
                    pass
                self.close_connection = True
            rec["ms"] = int((time.time() - t0) * 1000)
            chaos.log(rec)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _handle

    return H


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(chaos: Chaos, host: str, port: int):
    srv = Server((host, port), make_handler(chaos))
    return srv


def self_test() -> int:
    """Local mock server + proxy; verifies that each fault type really happens."""
    class Up(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            data = json.dumps({"ok": True, "path": self.path, "pad": "x" * 2000}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            got = self.rfile.read(n)
            data = json.dumps({"echo": got.decode()}).encode()
            self.send_response(201)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    up = Server(("127.0.0.1", 0), Up)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    rules = [Rule("^GET /status", "status:503"), Rule("^GET /delay", "delay:400"), Rule("^GET /drop", "drop"),
             Rule("^GET /reset", "reset"), Rule("^GET /hang", "hang:1.5"), Rule("^GET /trunc", "truncate:50"),
             Rule("^GET /garbage", "garbage"), Rule("^GET /once", "status:500@1"), Rule("^GET /slow", "slow:8000")]
    import tempfile
    import os
    logf = os.path.join(tempfile.mkdtemp(prefix="nc-selftest-"), "log.jsonl")
    chaos = Chaos(f"http://127.0.0.1:{up.server_address[1]}", rules, 1.0, 1, logf, timeout=5, quiet=True)
    px = serve(chaos, "127.0.0.1", 0)
    threading.Thread(target=px.serve_forever, daemon=True).start()
    port = px.server_address[1]
    fails = []

    def get(path, timeout=5.0, method="GET", body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        t0 = time.time()
        try:
            c.request(method, path, body=body)
            r = c.getresponse()
            return r.status, r.read(), time.time() - t0
        finally:
            c.close()

    try:
        st, body, _ = get("/ok")
        if st != 200 or json.loads(body)["path"] != "/ok":
            fails.append(f"pass: {st}")
        st, body, _ = get("/echo", method="POST", body=b"hello")
        if st != 201 or json.loads(body)["echo"] != "hello":
            fails.append(f"POST body: {st} {body[:60]}")
        st, _, _ = get("/status")
        if st != 503:
            fails.append(f"status: {st}")
        _, _, dt = get("/delay")
        if dt < 0.38:
            fails.append(f"delay: {dt:.2f} s")
        for path, name in (("/drop", "drop"), ("/reset", "reset")):
            try:
                get(path)
                fails.append(f"{name}: got a response")
            except (http.client.HTTPException, OSError):
                pass
        try:
            get("/hang", timeout=0.8)
            fails.append("hang: got a response")
        except (socket.timeout, TimeoutError, OSError):
            pass
        try:
            st, body, _ = get("/trunc")
            fails.append(f"truncate: read in full ({len(body)} bytes)")
        except http.client.IncompleteRead as e:
            if not (0 < len(e.partial) < e.expected + len(e.partial)):
                fails.append("truncate: unexpected length")
        st, body, _ = get("/garbage")
        try:
            json.loads(body)
            fails.append("garbage: valid JSON")
        except ValueError:
            pass
        st1, _, _ = get("/once")
        st2, _, _ = get("/once")
        if (st1, st2) != (500, 200):
            fails.append(f"@1 limit: {st1}, {st2}")
        st, body, dt = get("/slow")
        if st != 200 or dt < 0.2:
            fails.append(f"slow: {st} {dt:.2f} s")
        # The log line is written AFTER the response (hang closes after 1.5 s): wait for it to finish.
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with open(logf, encoding="utf-8") as fh:
                    if sum(1 for _ in fh) >= 12:
                        break
            except OSError:
                pass
            time.sleep(0.05)
    finally:
        px.shutdown()
        up.shutdown()
        px.server_close()
        up.server_close()
    if not nonprod_host("staging.api.example.com") or nonprod_host("api.example.com") \
            or not nonprod_host("localhost:8080") or not nonprod_host("10.0.0.5"):
        fails.append("production / mock server distinction")
    with open(logf, encoding="utf-8") as fh:
        logged = sum(1 for _ in fh)
    if logged < 12:
        fails.append(f"log incomplete ({logged} lines)")
    import shutil
    shutil.rmtree(os.path.dirname(logf), ignore_errors=True)
    if fails:
        print("SELF-TEST FAILED:\n- " + "\n- ".join(fails))
        return 1
    print("Self-test passed: pass, POST body, status, delay, drop, reset, hang, truncate, garbage, @N limit, slow, "
          "production distinction, log.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fault-injecting reverse proxy (in front of a mock / staging server).")
    ap.add_argument("--upstream", help="https://staging.example.com (NOT PRODUCTION)")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--bind", default="127.0.0.1", help="default is this Mac only (the simulator can reach it)")
    ap.add_argument("--rule", nargs=2, action="append", default=[], metavar=("PATTERN", "FAULT"))
    ap.add_argument("--rate", type=float, default=1.0, help="fault probability on matching requests (0–1)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--log", help="request log (JSON lines)")
    ap.add_argument("--timeout", type=float, default=30.0, help="timeout when forwarding to the server (s)")
    ap.add_argument("--confirm-nonprod", action="store_true",
                    help="I confirm this is NOT PRODUCTION even if the server name does not look like mock / staging")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.upstream:
        ap.error("--upstream required (or --self-test)")
    host = urllib.parse.urlsplit(a.upstream).netloc
    if not nonprod_host(host) and not a.confirm_nonprod:
        print(f"'{host}' does not look like a mock / staging server. Faults are injected only into a mock or staging "
              f"server (NC-P1). If it is not production, run again with --confirm-nonprod.", file=sys.stderr)
        return 2
    try:
        rules = [Rule(p, f) for p, f in a.rule]
        chaos = Chaos(a.upstream, rules, a.rate, a.seed, a.log, a.timeout)
    except (ValueError, re.error) as e:
        print(f"Invalid setting: {e}", file=sys.stderr)
        return 2
    srv = serve(chaos, a.bind, a.port)
    print(f"Proxy: http://localhost:{srv.server_address[1]} → {a.upstream} · {len(rules)} rules · rate {a.rate} · "
          f"seed {a.seed}. Set the app's base URL to http://localhost:{srv.server_address[1]} "
          f"(iOS 17+: NOT 127.0.0.1, use localhost — ATS blocks IP addresses). To stop: Ctrl+C / by PID.",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
