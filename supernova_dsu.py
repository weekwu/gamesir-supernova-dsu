"""Local DSU bridge for the GameSir Supernova in 2.4 GHz Switch mode.

Reads HID reports using the standard Python hidapi package. No virtual drivers,
firmware writes, device resets, HID hiding, or external network connections.
"""
import argparse, json, math, pathlib, socket, struct, time, zlib

MAC = bytes.fromhex('020057e02009')  # Stable synthetic DSU identifier, not device MAC.
SERVER_ID = 0x53555052

DEFAULT_OPTIONS = dict(mode='cemu26', gain=1.0, smoothing_ms=0.0, deadzone_dps=0.0)

def read_options(path):
    options = DEFAULT_OPTIONS.copy()
    if path:
        try:
            raw = json.loads(pathlib.Path(path).read_text(encoding='utf8'))
            if raw.get('mode') in ('cemu26', 'calibrated'): options['mode'] = raw['mode']
            for key, low, high in [('gain', .5, 2.0), ('smoothing_ms', 0, 100), ('deadzone_dps', 0, 2)]:
                value = float(raw.get(key, options[key]))
                if math.isfinite(value): options[key] = max(low, min(high, value))
        except (OSError, ValueError, TypeError, AttributeError): pass
    return options

class MotionFilter:
    def __init__(self): self.previous = None
    def apply(self, gyro, dt, options):
        # Subtract the deadzone continuously rather than jumping at its boundary.
        deadzone = options['deadzone_dps']
        values = [math.copysign(max(0, abs(v)-deadzone), v) * options['gain'] for v in gyro]
        tau = options['smoothing_ms'] / 1000
        if tau and self.previous is not None and 0 < dt < .25:
            alpha = 1-math.exp(-dt/tau)
            values = [p+alpha*(v-p) for p,v in zip(self.previous,values)]
        self.previous = values
        return values

def packet(kind, payload=b'', magic=b'DSUS'):
    b = bytearray(struct.pack('<4sHHIII', magic, 1001, 4+len(payload), 0, SERVER_ID, kind)+payload)
    struct.pack_into('<I', b, 8, zlib.crc32(b))
    return bytes(b)

def valid(b):
    if len(b) < 20 or b[:4] != b'DSUC': return False
    version, size, crc = struct.unpack_from('<HHI', b, 4)
    if version > 1001 or size+16 != len(b): return False
    zeroed = b[:8]+b'\0'*4+b[12:]
    return zlib.crc32(zeroed) == crc

class Hid:
    def __init__(self):
        try:
            import hid
        except ImportError as error:
            raise RuntimeError('Install dependencies: python -m pip install -r requirements.txt') from error
        self.lib = hid
        self.handle = None
        self.seq = 0
    def open(self):
        paths = [d['path'] for d in self.lib.enumerate(0x057e,0x2009)
                 if d.get('usage_page') == 1 and d.get('usage') in (4,5)]
        if len(paths) != 1:
            raise RuntimeError(f'Expected exactly one Switch-mode controller; found {len(paths)}')
        handle = self.lib.device()
        try:
            handle.open_path(paths[0])
        except OSError as error:
            handle.close()
            raise RuntimeError('Cannot open Switch-mode receiver') from error
        self.handle = handle
    def read(self, timeout=10):
        try:
            return bytes(self.handle.read(512, timeout))
        except (OSError,ValueError) as error:
            raise RuntimeError('Receiver disconnected or read failed') from error
    def command(self, command, data=b''):
        # Nintendo standard subcommands. Avoid the USB reset/handshake used by BetterJoy.
        b = bytes([1, self.seq])+bytes.fromhex('0001404000014040')+bytes([command])+data
        self.seq = (self.seq+1) & 15
        b = b.ljust(64, b'\0')
        try:
            written = self.handle.write(b)
        except (OSError,ValueError) as error:
            raise RuntimeError('HID command failed') from error
        if written < 0: raise RuntimeError('HID command failed')
    def close(self):
        if self.handle:
            self.handle.close(); self.handle = None

def info(slot=0, connected=True, active=False):
    return bytes([slot, 2 if connected else 0, 2 if connected else 0, 1 if connected else 0])+MAC+bytes([5 if connected else 0, int(active)])

def pad_payload(b, count, timestamp, acc_scale, gyro_scale, gyro_bias, motion_filter=None, dt=0, options=None):
    right, shared, left = b[3:6]
    # DSU's buttons use the DualShock layout; Nintendo face buttons retain physical positions.
    state1 = ((shared&1)>0) | (((shared&8)>0)<<1) | (((shared&4)>0)<<2) | (((shared&2)>0)<<3)
    state1 |= (((left&2)>0)<<4) | (((left&4)>0)<<5) | (((left&1)>0)<<6) | (((left&8)>0)<<7)
    state2 = ((left&128)>0) | (((right&128)>0)<<1) | (((left&64)>0)<<2) | (((right&64)>0)<<3)
    state2 |= (((right&2)>0)<<4) | (((right&8)>0)<<5) | (((right&4)>0)<<6) | (((right&1)>0)<<7)
    def stick(offset):
        x = b[offset] | ((b[offset+1]&15)<<8)
        y = (b[offset+1]>>4) | (b[offset+2]<<4)
        return round(x*255/4095), round(y*255/4095)
    axes = (*stick(6), *stick(9))
    analog = bytes(255 if yes else 0 for yes in [left&8,left&1,left&4,left&2,right&1,right&4,right&8,right&2,right&64,left&64,right&128,left&128])
    ax, ay, az, gx, gy, gz = struct.unpack_from('<6h', b, 37)
    # Same axis convention as BetterJoy for a Pro controller. Units: g and degrees/sec.
    motion = (ay*acc_scale, -az*acc_scale, ax*acc_scale,
              -(gy-gyro_bias[1])*gyro_scale, -(gz-gyro_bias[2])*gyro_scale, (gx-gyro_bias[0])*gyro_scale)
    if motion_filter is not None:
        motion = (*motion[:3], *motion_filter.apply(motion[3:],dt,options))
    return info(active=True)+struct.pack('<I8B', count, state1, state2, int(bool(shared&16)), int(bool(shared&32)), *axes)+analog+b'\0'*12+struct.pack('<Q6f', timestamp, *motion), motion

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=26761)
    ap.add_argument('--duration', type=float, default=0)
    ap.add_argument('--status')
    ap.add_argument('--initialize', action='store_true', help='Enable six-axis and 0x30 reports using temporary subcommands')
    ap.add_argument('--options-file')
    ap.add_argument('--gyro-scale', type=float, default=None)
    ap.add_argument('--acc-scale', type=float, default=1/4096)
    ap.add_argument('--gyro-bias', type=float, nargs=3, default=[0,0,0])
    args = ap.parse_args()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, 'SIO_UDP_CONNRESET'):
        udp.ioctl(socket.SIO_UDP_CONNRESET, False)
    udp.bind(('127.0.0.1', args.port))
    udp.setblocking(False)
    hid = Hid()
    clients, requests = {}, {}
    count, sent, last_report, last_status, motion = 0, 0, 0, 0, None
    # perf_counter uses Windows' high-resolution clock even on Python 3.10.
    # Older monotonic implementations can repeat timestamps at an 8 ms cadence.
    start = time.perf_counter()
    options = read_options(args.options_file)
    last_options = 0
    motion_filter = MotionFilter()
    try:
        hid.open()
        if args.initialize:
            hid.command(0x40, b'\x01')
            hid.command(0x03, b'\x30')
        print(f'DSU ready on 127.0.0.1:{args.port}; keep BetterJoy closed.', flush=True)
        while not args.duration or time.perf_counter()-start < args.duration:
            now = time.perf_counter()
            if now-last_options >= .2:
                fresh_options = read_options(args.options_file)
                if fresh_options != options: motion_filter = MotionFilter()
                options = fresh_options
                last_options = now
            while True:
                try: b, address = udp.recvfrom(1024)
                except BlockingIOError: break
                except ConnectionResetError: continue
                if not valid(b): continue
                kind = struct.unpack_from('<I', b, 16)[0]
                requests[hex(kind)] = requests.get(hex(kind),0)+1
                if kind == 0x100000:
                    udp.sendto(packet(kind, struct.pack('<H',1001)+b'\0\0'), address)
                elif kind == 0x100001 and len(b) >= 24:
                    n = struct.unpack_from('<I', b, 20)[0]
                    if n > 4 or len(b) < 24+n: continue
                    for slot in b[24:24+n]:
                        if slot < 4: udp.sendto(packet(kind, info(slot, slot==0 and now-last_report<1)),address)
                elif kind == 0x100002 and len(b) == 28:
                    flags, slot = b[20:22]
                    if flags == 0 or ((flags&1) and slot==0) or ((flags&2) and b[22:28]==MAC): clients[address] = now
            try:
                b = hid.read()
            except RuntimeError:
                hid.close()
                clients.clear()
                print('Receiver disconnected. Waiting for the same Switch-mode receiver.', flush=True)
                while True:
                    if args.duration and time.perf_counter()-start >= args.duration: return
                    time.sleep(.5)
                    try:
                        hid.open()
                        if args.initialize:
                            hid.command(0x40, b'\x01'); hid.command(0x03, b'\x30')
                        break
                    except RuntimeError: hid.close()
                continue
            now = time.perf_counter()
            clients = {a:t for a,t in clients.items() if now-t < 5}
            if len(b) >= 49 and b[0] == 0x30:
                count = (count+1)&0xffffffff
                dt = now-last_report if last_report else 0
                last_report = now
                # Cemu 2.6's SDL 2.30.3 uses 936/13371 with the measured zero offsets.
                # The previous mode uses the reported sensitivity coefficient, 15335.
                gyro_scale = args.gyro_scale if args.gyro_scale is not None else 936/(13371 if options['mode']=='cemu26' else 15335)
                payload, motion = pad_payload(b,count,time.perf_counter_ns()//1000,args.acc_scale,gyro_scale,args.gyro_bias,motion_filter,dt,options)
                out = packet(0x100002,payload)
                for a in clients:
                    udp.sendto(out,a); sent += 1
            if now-last_status > 1:
                status = dict(reports=count,packets_sent=sent,clients=len(clients),requests=requests,report_age=round(now-last_report,3) if last_report else None,motion=motion,elapsed=round(now-start,1),options=options)
                if args.status:
                    pathlib.Path(args.status).write_text(json.dumps(status,indent=2),encoding='utf8')
                print(json.dumps(status),flush=True)
                last_status = now
    finally:
        hid.close(); udp.close()

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
