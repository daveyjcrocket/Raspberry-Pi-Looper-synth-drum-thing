#!/usr/bin/env python3
"""Web remote for LiveLoopSynth: serves the page in remote/web/ and bridges it to Pd.

    browser  <-- WebSocket /ws (JSON) -->  this server  <-- TCP 127.0.0.1:9311 (FUDI) -->  Pd [remote]

Only the Python standard library is used, so it runs on a stock Raspberry Pi OS.
Pd may start before or after this server; the connection is retried every second.
Only the names in names.json (made by tools/gen_remote.py) are passed on to Pd,
and only as a bang or a number.

    python3 remote/server.py [--port 8080] [--host 0.0.0.0]
"""
import argparse, asyncio, base64, hashlib, json, math, mimetypes, os, socket, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, 'web')
NAMES = json.load(open(os.path.join(HERE, 'names.json')))
IN, OUT = set(NAMES['in']), set(NAMES['out'])
FAST = {'loop-pos', 'l-in-sig', 'r-in-sig', 'l-out-db'}   # sent to the browsers at most every FAST_MS
FAST_MS = 40
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


# ---------------- Pd's FUDI text format ----------------

def fudi_split(buf):
    """Complete messages in buf (split on unescaped ';') and the unfinished rest."""
    msgs, cur, esc = [], [], False
    start = 0
    for i, ch in enumerate(buf):
        if esc:
            esc = False
        elif ch == '\\':
            esc = True
        elif ch == ';':
            msgs.append(buf[start:i]); start = i + 1
    return msgs, buf[start:]


def fudi_atoms(msg):
    """Atoms of one message: floats, or strings with escapes removed."""
    atoms, cur, esc, escaped = [], [], False, False
    for ch in msg + ' ':
        if esc:
            cur.append(ch); esc = False
        elif ch == '\\':
            esc = escaped = True
        elif ch in ' \t\n\r':
            if cur:
                word = ''.join(cur)
                if not escaped:
                    try:
                        word = float(word)
                    except ValueError:
                        pass
                atoms.append(word)
            cur, escaped = [], False
        else:
            cur.append(ch)
    return atoms


def fudi_num(v):
    return str(int(v)) if float(v).is_integer() else repr(float(v))


# ---------------- state shared by Pd and the browsers ----------------

class Hub:
    def __init__(self):
        self.state = {}          # (name, kind) -> value, replayed to every new browser
        self.fast = {}           # pending high-rate updates
        self.clients = set()
        self.pd = None           # StreamWriter to Pd, or None

    def from_pd(self, atoms):
        if len(atoms) < 2 or atoms[0] not in OUT:
            return
        name, args = atoms[0], atoms[1:]
        kind = 'value'
        if args[0] in ('label', 'color'):
            kind, args = args[0], args[1:]
        elif args[0] == 'set':
            args = args[1:]
        if not args:
            return
        if kind == 'label':
            value = ' '.join(fudi_num(a) if isinstance(a, float) else a for a in args)
        elif kind == 'color':
            value = args
        else:
            value = args[0]
        self.state[(name, kind)] = value
        upd = {'n': name, 'k': kind, 'v': value}
        if name in FAST:
            self.fast[(name, kind)] = upd
        else:
            self.broadcast([upd])

    def from_browser(self, msg):
        name, v = msg.get('n'), msg.get('v')
        if name not in IN or self.pd is None:
            return
        if v == 'bang':
            text = f'{name} bang;\n'
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            text = f'{name} {fudi_num(v)};\n'
        else:
            return
        self.pd.write(text.encode())

    def broadcast(self, updates):
        data = json.dumps({'u': updates}, separators=(',', ':'))
        for c in list(self.clients):
            c.send(data)

    def snapshot(self):
        ups = [{'n': n, 'k': k, 'v': v} for (n, k), v in self.state.items()]
        return json.dumps({'pd': self.pd is not None, 'u': ups}, separators=(',', ':'))

    async def flush_fast(self):
        while True:
            await asyncio.sleep(FAST_MS / 1000)
            if self.fast:
                ups, self.fast = list(self.fast.values()), {}
                self.broadcast(ups)

    async def pd_link(self, port):
        announced = False
        while True:
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', port)
            except OSError:
                if not announced:
                    print(f'Waiting for Pd on 127.0.0.1:{port} ...', flush=True); announced = True
                await asyncio.sleep(1)
                continue
            print('Connected to Pd.', flush=True); announced = False
            self.pd = writer
            writer.write(b'remote-dump bang;\n')
            self.broadcast_status()
            buf = ''
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    msgs, buf = fudi_split(buf + data.decode('utf-8', 'replace'))
                    for m in msgs:
                        self.from_pd(fudi_atoms(m))
            except (ConnectionError, OSError):
                pass
            self.pd = None
            writer.close()
            print('Lost the connection to Pd.', flush=True)
            self.broadcast_status()
            await asyncio.sleep(1)

    def broadcast_status(self):
        data = json.dumps({'pd': self.pd is not None})
        for c in list(self.clients):
            c.send(data)


# ---------------- WebSocket (RFC 6455, text frames only) ----------------

class WsClient:
    MAX_QUEUE = 500

    def __init__(self, hub, reader, writer):
        self.hub, self.reader, self.writer = hub, reader, writer
        self.queue = asyncio.Queue()

    def send(self, text):
        if self.queue.qsize() > self.MAX_QUEUE:        # a phone that stopped reading
            self.writer.close(); return
        self.queue.put_nowait(self.frame(1, text.encode()))

    @staticmethod
    def frame(opcode, payload):
        n = len(payload)
        head = bytes([0x80 | opcode])
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + struct.pack('>H', n)
        else:
            head += bytes([127]) + struct.pack('>Q', n)
        return head + payload

    async def writer_task(self):
        try:
            while True:
                self.writer.write(await self.queue.get())
                await self.writer.drain()
        except (ConnectionError, OSError):
            pass

    async def pinger(self):
        while True:
            await asyncio.sleep(20)
            self.queue.put_nowait(self.frame(9, b''))

    async def read_frame(self):
        b1, b2 = await self.reader.readexactly(2)
        opcode, n = b1 & 0x0F, b2 & 0x7F
        if n == 126:
            n = struct.unpack('>H', await self.reader.readexactly(2))[0]
        elif n == 127:
            n = struct.unpack('>Q', await self.reader.readexactly(8))[0]
        if n > 65536:
            raise ConnectionError('frame too large')
        mask = await self.reader.readexactly(4) if b2 & 0x80 else b'\0\0\0\0'
        data = bytearray(await self.reader.readexactly(n))
        for i in range(n):
            data[i] ^= mask[i % 4]
        return b1 & 0x80, opcode, bytes(data)

    async def run(self):
        tasks = [asyncio.ensure_future(self.writer_task()), asyncio.ensure_future(self.pinger())]
        self.hub.clients.add(self)
        self.queue.put_nowait(self.frame(1, self.hub.snapshot().encode()))
        parts = b''
        try:
            while True:
                fin, opcode, data = await self.read_frame()
                if opcode == 8:
                    break
                if opcode == 9:
                    self.queue.put_nowait(self.frame(10, data)); continue
                if opcode in (1, 0):
                    parts += data
                    if len(parts) > 65536:
                        break
                    if fin:
                        try:
                            msg = json.loads(parts.decode())
                        except ValueError:
                            msg = None
                        parts = b''
                        for m in (msg if isinstance(msg, list) else [msg]):
                            if isinstance(m, dict):
                                self.hub.from_browser(m)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            self.hub.clients.discard(self)
            for t in tasks:
                t.cancel()
            self.writer.close()


# ---------------- HTTP ----------------

def http_response(writer, status, body=b'', ctype='text/plain; charset=utf-8', extra=''):
    writer.write((f'HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n'
                  f'Cache-Control: no-cache\r\nConnection: close\r\n{extra}\r\n').encode() + body)


async def handle(hub, reader, writer):
    try:
        head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        writer.close(); return
    lines = head.decode('latin-1').split('\r\n')
    try:
        method, target, _ = lines[0].split(' ', 2)
    except ValueError:
        writer.close(); return
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    path = target.split('?', 1)[0]

    if path == '/ws' and headers.get('upgrade', '').lower() == 'websocket':
        key = headers.get('sec-websocket-key', '')
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                      f'Sec-WebSocket-Accept: {accept}\r\n\r\n').encode())
        await WsClient(hub, reader, writer).run()
        return

    if method not in ('GET', 'HEAD'):
        http_response(writer, '405 Method Not Allowed')
    else:
        rel = 'index.html' if path in ('/', '') else path.lstrip('/')
        full = os.path.realpath(os.path.join(WEB, rel))
        if full.startswith(os.path.realpath(WEB) + os.sep) and os.path.isfile(full):
            body = open(full, 'rb').read()
            ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
            if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json'):
                ctype += '; charset=utf-8'
            http_response(writer, '200 OK', b'' if method == 'HEAD' else body, ctype)
        else:
            http_response(writer, '404 Not Found', b'not found')
    try:
        await writer.drain()
    except ConnectionError:
        pass
    writer.close()


def lan_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))      # no packet is sent; this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=int(os.environ.get('REMOTE_PORT', 8080)))
    ap.add_argument('--host', default=os.environ.get('REMOTE_HOST', '0.0.0.0'),
                    help='address to listen on (127.0.0.1 = this computer only)')
    a = ap.parse_args()
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('application/manifest+json', '.webmanifest')
    hub = Hub()
    server = await asyncio.start_server(lambda r, w: handle(hub, r, w), a.host, a.port)
    print(f'LiveLoopSynth remote on port {a.port}. Open one of these on your phone (same Wi-Fi):', flush=True)
    if a.host in ('0.0.0.0', ''):
        ip = lan_address()
        if ip:
            print(f'  http://{ip}:{a.port}/')
        print(f'  http://{socket.gethostname()}.local:{a.port}/')
    else:
        print(f'  http://{a.host}:{a.port}/')
    sys.stdout.flush()
    await asyncio.gather(server.serve_forever(), hub.pd_link(NAMES['pd_port']), hub.flush_fast())


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
