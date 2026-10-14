# 单台设备复现记录

日期：2026-10-14。系统为 Windows；Python 3.14，Cemu 2.6 内置 SDL 2.30.3，BetterJoy 7.1。手柄为 GameSir 超新星 / Supernova，2.4GHz 接收器强制 Switch 模式。手柄和接收器固件版本未记录，不作推测。

## 观察

1. Windows HID 标识 `057E:2009`，产品名 `Pro Controller`。序列号为协议常见占位形式；公开记录不含设备独有标识。
2. Steam 可显示陀螺仪。直接 HID 采样四秒收到 501 个 `0x30/64` 报告，其中包括加速度和陀螺仪值。
3. Steam 正常退出后仍收到同类报告。这里没有做冷启动，所以不能证明接收器在任何启动状态下都不需要初始化。
4. 在隔离的 BetterJoy 副本中复现重置循环。关闭 Steam 后仍复现；GameSir Connect 未完全退出，因此不能宣称已排除全部软件交互。
5. 通信日志中，`0x81` 回复会排在多个 `0x30` 报告后。BetterJoy 的 Attach USB 路径只读一次，首个结果不是 `0x81` 就发送重置并退出当前连接。本次证据支持握手回复与连续报告混排导致循环，但没有提交 BetterJoy 补丁来做完整因果验证。
6. 独立 SDL 2.30.3 测试未列出目标控制器；退出后设备仍存在，但原始报告停止。发送临时的 IMU 开启和完整报告模式指令后恢复报告。SDL 的具体失败分支尚未完整定位。
7. 自写的直接 HID → DSU 原型在 Cemu 2.6 成功连接。用户三轴转动期间，30 秒收到 3750 个有效数据包，CRC 全部有效，运动时间戳严格递增。
8. 用户在《旷野之息》中确认准星随手柄运动。最初上下反向，按 Cemu SDL / BetterJoy Pro 的坐标约定修正后，用户再次确认能够正确控制体感。

## 两个误区

- Cemu 设置里的 Rotation 圆点是右摇杆显示，不能用它判断 gyro 是否存在。
- 保存的 profile 与当前 controller0 的 Use motion 状态可能不同，重新加载旧 profile 可以重新关闭体感。请核查实际载入的配置。

## 实现路径

接收器报告中的最后一组 IMU 样本用于 DSU 包。每份报告约 8 ms，实际报告率约 125 Hz；不将该间隔等同于完整的输入到显示延迟。DSU 标准包长 100 字节，携带 CRC32、递增计数、单调微秒时间戳、加速度（g）和角速度（度/秒）。

初始化只使用 Switch 标准子命令 `0x40:01` 和 `0x03:30`。没有采用 BetterJoy 的 USB 单次握手检查、重置、虚拟输出或 HidGuardian 隐藏流程。

## 验证边界

原型使用本机已存在的 BetterJoy HID DLL。本公开版已改成 Python `hidapi` 依赖；重构时目标设备已不在该模式，故新的依赖路径尚未完成游戏复测。请把原型硬件结果与公开版软件测试分开理解。

仍待验证：其他设备/固件、冷启动、断开重连、精确角度、静置漂移、延迟、长期稳定性、其他模拟器和原装 Switch Pro 对照。公开项目不附带 ROM、存档、游戏密钥、本机日志或原控制器备份。

依据：[BetterJoy 初始化](https://github.com/Davidobot/BetterJoy/blob/master/BetterJoyForCemu/Joycon.cs)、[SDL 2.30.3 驱动](https://github.com/libsdl-org/SDL/blob/release-2.30.3/src/joystick/hidapi/SDL_hidapi_switch.c)、[Cemu DSU 处理](https://github.com/cemu-project/Cemu/blob/v2.6/src/input/api/DSU/DSUControllerProvider.cpp)。
