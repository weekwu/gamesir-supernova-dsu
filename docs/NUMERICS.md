# 数值来源与控制项

这里区分数学换算的一致性和不同硬件的真实运动一致性。没有原装 Switch Pro 对照测试，也没有完成已知角度的物理标定。

## 默认模式：Cemu 2.6 / SDL 2.30.3

该版本的 Switch 驱动使用 `936 / (13371 - gyro_zero_offset)`，随后转换为弧度/秒。原测试设备从工厂校准区读到的三个 gyro 零偏均为 0。因此本桥接默认系数是 `936/13371 ≈ 0.07000224` 度/秒/计数。

这对齐的是已测试版本、已测零偏条件下的公式。代码没有自动检测 Cemu 版本，也没有读取另一只控制器的用户校准区。不能用于声称任何手柄与原装控制器在同一物理动作下完全相同。

## 备用模式：原型校准公式

较新 SDL 驱动使用 `936 / (reported_sensitivity - gyro_zero_offset)`。原测试设备报告的三个 sensitivity 均为 15335，零偏为 0；备用模式采用 `936/15335 ≈ 0.06103684`。这是本次记录的设备值，不是所有 GameSir 或原装 Pro 的常量。

默认与备用的幅度比为 `15335/13371 ≈ 1.1469`，即对相同原始值约提高 14.7%。反过来，备用幅度约是默认的 87.2%。这些是系数比较，不是测得的真实瞄准幅度差异。

## 坐标与后续处理

原始 Switch IMU 为 `(ax,ay,az,gx,gy,gz)`。本桥接的 DSU 加速度为 `(ay,-az,ax)/4096`，gyro 为 `(-gy,-gz,gx)*scale`。Cemu DSU 随后将 gyro 转弧度/秒，并将 acceleration 的 y/z 符号调整后送入 MotionHandler；SDL 输入也进入同一套 MotionHandler。

这对齐轴方向和主要量纲，但不是逐位浮点输出一致：SDL 的重力单位常数、DSU 的度到弧度常数、采样数量、报告时序和积分时间仍存在细节差异。本桥接每个报告取最后一组 IMU，不重建三组原生 SDL sensor events。因此应把“标准换算”理解为可追溯的公式基线，不能扩张成完整仿真等效性。

## 可选手感调整

- gain：0.5～2.0，默认 1.0。
- deadzone：0～2 度/秒，默认 0。每轴采用 `sign(x)*max(0,abs(x)-threshold)`，避免过阈值时突然跳变；仍会减少小幅动作。
- smoothing：指数滤波时间常数 0～100 ms，默认 0。`alpha = 1-exp(-dt/tau)`；更强平滑会增加滞后。零值时不增加滤波。
- 设置约每 0.2 秒重新读取，变更时重置额外滤波状态，避免旧状态拖尾。

默认关闭额外滤波和死区，保留原始微动。滤波不是用来掩盖初始化或坐标错误。命令行 `--gyro-scale` / `--gyro-bias` 用于明确的数值试验；不得将随意调整的值报告成完成了硬件校准。

来源：[SDL 2.30.3](https://github.com/libsdl-org/SDL/blob/release-2.30.3/src/joystick/hidapi/SDL_hidapi_switch.c)、[较新 SDL2 驱动](https://github.com/libsdl-org/SDL/blob/SDL2/src/joystick/hidapi/SDL_hidapi_switch.c)、[Cemu SDL](https://github.com/cemu-project/Cemu/blob/v2.6/src/input/api/SDL/SDLControllerProvider.cpp)、[Cemu DSU](https://github.com/cemu-project/Cemu/blob/v2.6/src/input/api/DSU/DSUControllerProvider.cpp)。
