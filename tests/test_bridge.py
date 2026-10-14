import contextlib
import io
import json
import math
import pathlib
import socket
import struct
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
import zlib

import supernova_dsu as bridge


def report(right=0, shared=0, left=0, imu=(0,0,4096,10,20,30)):
    raw = bytearray(64)
    raw[0] = 0x30
    raw[3:6] = bytes([right,shared,left])
    # Both 12-bit sticks centered at 2048.
    raw[6:12] = bytes.fromhex('000880000880')
    struct.pack_into('<6h',raw,37,*imu)
    return raw


class ProtocolTests(unittest.TestCase):
    def test_wire_layout_units_and_crc(self):
        payload,motion = bridge.pad_payload(report(),42,123456,1/4096,936/13371,[0,0,0])
        packet = bridge.packet(0x100002,payload)
        self.assertEqual(len(packet),100)
        self.assertEqual(packet[:4],b'DSUS')
        self.assertEqual(struct.unpack_from('<HH',packet,4),(1001,84))
        self.assertEqual(struct.unpack_from('<I',packet,16)[0],0x100002)
        self.assertEqual(struct.unpack_from('<I',packet,32)[0],42)
        self.assertEqual(struct.unpack_from('<Q',packet,68)[0],123456)
        self.assertEqual(struct.unpack_from('<3f',packet,76),(0,-1,0))
        self.assertAlmostEqual(struct.unpack_from('<f',packet,88)[0],-20*936/13371,places=6)
        zero_crc = packet[:8]+b'\0'*4+packet[12:]
        self.assertEqual(struct.unpack_from('<I',packet,8)[0],zlib.crc32(zero_crc))
    def test_rejects_corruption_truncation_and_server_magic(self):
        request = bridge.packet(0x100002,bytes([1,0])+b'\0'*6,magic=b'DSUC')
        self.assertTrue(bridge.valid(request))
        corrupt = bytearray(request);corrupt[-1]^=1
        self.assertFalse(bridge.valid(corrupt))
        self.assertFalse(bridge.valid(request[:-1]))
        self.assertFalse(bridge.valid(bridge.packet(0x100000)))
        self.assertFalse(bridge.valid(b''))
    def test_nintendo_positions_and_dpad(self):
        # Nintendo A (right face button) -> DSU Circle; up -> DSU D-pad Up.
        payload,_ = bridge.pad_payload(report(right=8,left=2),1,1,1/4096,1,[0,0,0])
        self.assertEqual(payload[16],0x10)
        self.assertEqual(payload[17],0x20)
        self.assertEqual(payload[20:24],bytes([128]*4))
        self.assertEqual(payload[27],255)  # analog D-pad Up
        self.assertEqual(payload[30],255)  # analog Circle
    def test_dsu_axes_follow_cemu_convention(self):
        _,motion = bridge.pad_payload(report(imu=(4096,8192,12288,10,20,30)),1,1,1/4096,1,[0,0,0])
        self.assertEqual(motion,(2,-3,1,-20,-30,10))


class ControlsTests(unittest.TestCase):
    def test_default_filter_is_bypass(self):
        self.assertEqual(bridge.MotionFilter().apply([1,-2,.01],.008,bridge.DEFAULT_OPTIONS),[1,-2,.01])
    def test_gain_and_continuous_deadzone(self):
        options={**bridge.DEFAULT_OPTIONS,'gain':1.5,'deadzone_dps':.5}
        result=bridge.MotionFilter().apply([.2,-.5,1],.008,options)
        self.assertEqual(result,[0,0,.75])
    def test_smoothing_time_constant(self):
        options={**bridge.DEFAULT_OPTIONS,'smoothing_ms':20}
        f=bridge.MotionFilter();f.apply([0,0,0],.008,options)
        self.assertAlmostEqual(f.apply([10,0,0],.008,options)[0],10*(1-math.exp(-.4)))
    def test_missing_malformed_and_out_of_range_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'settings.json'
            self.assertEqual(bridge.read_options(path),bridge.DEFAULT_OPTIONS)
            path.write_text('{',encoding='utf8')
            self.assertEqual(bridge.read_options(path),bridge.DEFAULT_OPTIONS)
            path.write_text(json.dumps({'mode':'calibrated','gain':99,'deadzone_dps':-1,'smoothing_ms':'NaN'}),encoding='utf8')
            result=bridge.read_options(path)
            self.assertEqual(result['mode'],'calibrated')
            self.assertEqual(result['gain'],2)
            self.assertEqual(result['deadzone_dps'],0)
            self.assertEqual(result['smoothing_ms'],0)


class HidAdapterTests(unittest.TestCase):
    def test_package_adapter_reads_and_only_sends_requested_subcommands(self):
        device=mock.Mock()
        device.read.return_value=list(report())
        device.write.return_value=64
        package=types.SimpleNamespace(enumerate=lambda *_:[{'path':b'fixture','usage_page':1,'usage':4}],device=lambda:device)
        with mock.patch.dict(sys.modules,{'hid':package}):
            hid=bridge.Hid();hid.open()
            self.assertEqual(hid.read(),bytes(report()))
            self.assertFalse(device.write.called)
            hid.command(0x40,b'\x01');hid.command(0x03,b'\x30')
            packets=[call.args[0] for call in device.write.call_args_list]
            self.assertEqual([p[10:12] for p in packets],[b'\x40\x01',b'\x03\x30'])
            self.assertTrue(all(len(p)==64 and p[0]==1 for p in packets))
            hid.close();device.close.assert_called_once()
    def test_ambiguous_matching_devices_are_rejected(self):
        record={'path':b'fixture','usage_page':1,'usage':4}
        package=types.SimpleNamespace(enumerate=lambda *_:[record,record])
        with mock.patch.dict(sys.modules,{'hid':package}):
            with self.assertRaisesRegex(RuntimeError,'found 2'):bridge.Hid().open()


class StreamTests(unittest.TestCase):
    def test_live_settings_on_local_udp_stream(self):
        class FakeHid:
            def open(self):pass
            def close(self):pass
            def read(self):time.sleep(.008);return report(imu=(0,0,4096,0,100,0))
        probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
        errors=[]
        with tempfile.TemporaryDirectory() as directory:
            config=pathlib.Path(directory)/'options.json'
            config.write_text(json.dumps(bridge.DEFAULT_OPTIONS),encoding='utf8')
            argv=['bridge','--duration','2','--port',str(port),'--options-file',str(config)]
            def server():
                try:bridge.main()
                except BaseException as error:errors.append(error)
            with mock.patch.object(bridge,'Hid',FakeHid),mock.patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
                thread=threading.Thread(target=server);thread.start()
                client=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                if hasattr(socket,'SIO_UDP_CONNRESET'):client.ioctl(socket.SIO_UDP_CONNRESET,False)
                client.settimeout(.2)
                early=[];late=[];stamps=[];changed=False;start=time.monotonic()
                try:
                    while time.monotonic()-start<1.5:
                        elapsed=time.monotonic()-start
                        if elapsed>.5 and not changed:
                            config.write_text(json.dumps({**bridge.DEFAULT_OPTIONS,'gain':2}),encoding='utf8');changed=True
                        client.sendto(bridge.packet(0x100002,bytes([1,0])+b'\0'*6,magic=b'DSUC'),('127.0.0.1',port))
                        try:data,_=client.recvfrom(1024)
                        except (socket.timeout,ConnectionResetError):continue
                        stamps.append(struct.unpack_from('<Q',data,68)[0])
                        gyro=struct.unpack_from('<f',data,88)[0]
                        if elapsed<.4:early.append(gyro)
                        if elapsed>1:late.append(gyro)
                finally:
                    client.close();thread.join(timeout=4)
                self.assertFalse(thread.is_alive())
            self.assertFalse(errors,errors)
            self.assertTrue(early and late)
            self.assertTrue(all(abs(v+100*936/13371)<1e-5 for v in early))
            self.assertTrue(all(abs(v+200*936/13371)<1e-5 for v in late))
            self.assertTrue(all(a<b for a,b in zip(stamps,stamps[1:])))


if __name__=='__main__':unittest.main()
