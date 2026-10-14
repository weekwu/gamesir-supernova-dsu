# GameSir Supernova DSU — 超新星无线体感桥

A small Windows DSU motion bridge for a GameSir Supernova using its 2.4 GHz receiver in forced Switch mode. Created after Steam could read gyro while BetterJoy 7.1 repeatedly reset the USB connection. [English notes](docs/README.en.md).

**已在一只超新星上验证原型能通过 2.4GHz 在 Cemu《旷野之息》中进行真实体感瞄准。** 本仓库公开版改用标准 Python HID 依赖；协议、数值和控制项有自动测试，但这次重构后的依赖路径尚未完成同样的游戏验收。请按下面的步骤复测并报告结果。它是社区适配工具，不是 GameSir、Nintendo 或 Cemu 的官方项目。

## 解决什么问题

在本次测试环境中，Steam 能显示陀螺仪，BetterJoy 7.1 则不断输出：

```text
Pro controller connected.
Using USB.
Resetting USB connection.
Removed dropped controller. Can be reconnected.
```

原始 HID 采样显示接收器持续发送包含六轴的 `0x30` 报告。BetterJoy 的 USB 初始化只读一次报告，若不是 `0x81` 就重置；实测 `0x81` 回复会出现在多个 `0x30` 后。这个时序可以解释本次循环，不能据此认定所有超新星固件或所有第三方手柄都会如此。

桥接路径：

```text
超新星 → 2.4GHz 接收器（强制 Switch 模式）
      → 开启 IMU / 完整报告 → 读取六轴、按键、摇杆
      → 本机 DSU 127.0.0.1:26761 → Cemu Wii U GamePad
```

这是六轴数据输入，不是体感转鼠标或摇杆。没有安装虚拟 Xbox 驱动、隐藏设备、USB 重置、固件写入或对外网络连接。完整分析和验证边界见 [复现记录](docs/REPRODUCTION.md)。

## 安装与运行（Windows）

需要 Python 3.10 或更新版本（包含 Tkinter）；当前开发与测试使用 Python 3.14。安装 Python 时保留 Windows `py` 启动器。

1. 下载本仓库代码并解压，或克隆仓库。
2. 双击 `setup.cmd`。它只在项目目录建立 `.venv` 并安装 `hidapi==0.15.0`，不需要 BetterJoy DLL。
3. 连接接收器，保持已经确认的强制 Switch 模式。测试时 Windows 设备标识为 `057E:2009`，产品名为 `Pro Controller`。该标识也被其他控制器使用，不能单凭名字证明兼容。
4. 完全关闭 BetterJoy，双击 `launch.cmd`。看到“体感数据正常”后再开 Cemu。可以创建 `launch.cmd` 的桌面快捷方式。
5. 保持体感桥窗口打开。不要同时运行两个桥接器。

若未安装 `py` 启动器，也可手动运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe bridge_gui.pyw
```

命令行方式：

```powershell
.\.venv\Scripts\python.exe supernova_dsu.py --initialize
```

`--initialize` 只发送临时的 IMU 开启和 `0x30` 报告模式指令。未启用时只读取设备当前报告。命令行不依赖 GUI，也不自动安装依赖。

## Cemu 配置

1. 关闭 Cemu，备份自己的控制器配置。
2. 将 `profiles/GameSir_24G_DSU.xml` 复制到 Cemu 的 `controllerProfiles` 目录。便携模式通常位于 `portable/controllerProfiles`。不要直接覆盖已有 `controller0.xml`。
3. 先运行桥接器，再打开 Cemu，进入 `Options → Input settings → Controller 1`，选择该 Profile 并点击 Load。
4. 模拟控制器选 **Wii U GamePad**；输入为 **Controller 1 [DSUController]**；Settings 中勾选 **Use motion**。
5. 手动添加时，DSU 地址使用 **127.0.0.1**，端口 **26761**（不是 BetterJoy 默认的 26760）。
6. 《旷野之息》游戏选项开启体感操作，持弓瞄准时转动手柄，或进入体感神庙测试。

Circle/Cross/Triangle/Square 是 DSU 协议中的名称，在本配置中对应 Nintendo 物理位置 A/B/X/Y。Axis/Rotation 圆点显示的是左右摇杆，不是陀螺仪。**体感桥中途重启后，Cemu 2.6 可能需要重启才能恢复订阅。**

## 灵敏度与可选控制

默认模式是“本机 Cemu 标准换算”：复现已测试 Cemu 2.6 内置 SDL 2.30.3 在测得零偏为 0 时的 `936/13371` 角速度换算。它不是对所有 Cemu/SDL 版本的自动检测，也不保证不同硬件的实际手感相同。

“之前的校准换算”采用参考较新 SDL 的 `936/15335`；15335 是本次设备报告的三个轴灵敏度系数。两者的来源和限制见 [数值说明](docs/NUMERICS.md)。

| 控制项 | 默认 | 范围 / 效果 |
|---|---|---|
| 灵敏度倍率 | 1.00× | 0.50×–2.00×，线性缩放角速度 |
| 平滑 | 0 ms | 0–100 ms，指数滤波时间常数；增加后更平稳，也更滞后 |
| 体感死区 | 0 °/s | 0–2 °/s，每轴连续减去阈值；增加后更容易忽略细微动作 |

运行中调整会在约 0.2 秒内重新读取设置，无需重启服务。默认关闭额外平滑和死区。设置保存在本项目的 `settings.json`；它不应提交到仓库。

## 已验证、尚未验证

- 原型：Steam 开启及退出时读到六轴；30 秒 DSU 采样收到 3750 包，CRC 有效、时间戳递增；Cemu 游戏瞄准可动，修正坐标后用户确认方向正常。
- 公开版：协议编码、轴方向、滤波默认旁路、参数实时生效、模拟服务器传输有自动测试。新的 `hidapi` 包可导入，但测试公开版时设备已不在目标模式，因此尚未复测游戏。
- 尚未做原装 Pro 实物对照、完整角度标定、长期稳定性测试、多设备测试、其他固件或 Cemu 版本全面测试。
- **没有震动输出、触摸板或虚拟 Xbox 手柄。** 电量和 DSU MAC 是固定的协议占位值，不代表真实电量或物理 MAC。
- HID 选择器按 `057E:2009` 和 usage 匹配，要求恰好一个设备；它无法证明设备一定是超新星或一定是 2.4GHz 连接。其他同标识手柄请勿同时接入。
- 切换蓝牙/PC 模式玩其他游戏前关闭体感桥。当前版本不会自动修改其他游戏或 Steam 的布局。

## 贡献与报告

欢迎提交 issue。请提供型号、手柄/接收器固件版本（如能查到）、连接方式、Python/Cemu 版本、Steam/BetterJoy 是否运行，以及按键、三个体感方向和漂移的结果。勿上传存档、ROM、密钥、真实设备序列号或账户凭据。

```powershell
python -m unittest discover -s tests -v
```

许可证：本项目代码 [MIT](LICENSE)。依赖及公式来源见 [第三方说明](THIRD_PARTY_NOTICES.md)。
