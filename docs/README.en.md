# GameSir Supernova DSU motion bridge

Windows community prototype for a Supernova connected through its 2.4 GHz receiver in forced Switch mode. It forwards actual gyro/accelerometer, buttons and sticks to Cemu's DSU input on `127.0.0.1:26761`. It does not emulate gyro as a mouse or stick.

## Setup

Python 3.10+ with Tkinter is required. Python 3.14 was used during development.

1. Run `setup.cmd` to create a project-local virtual environment and install the pinned `hidapi` dependency.
2. Connect the receiver in the already verified forced Switch mode. Keep BetterJoy closed.
3. Run `launch.cmd`, then start Cemu after motion reports arrive.
4. Copy `profiles/GameSir_24G_DSU.xml` to Cemu's controller profile directory. Back up existing profiles; load the new profile through Input settings instead of overwriting `controller0.xml`.
5. Select Wii U GamePad, DSUController, localhost port 26761, and enable Use motion. Enable motion controls in the game.

Steam can remain open in the original tested setup. If the bridge restarts, Cemu 2.6 may require a restart to resubscribe.

## Evidence and limits

On one controller, Steam read gyro while BetterJoy 7.1 repeatedly printed `Resetting USB connection`. Raw sampling showed `0x30` motion packets preceding a later `0x81` USB reply. BetterJoy's single-read handshake check explains the observed reset loop; it is not proof of universal incompatibility.

The original local implementation using an existing HID DLL was confirmed in Breath of the Wild, including corrected aim directions. This repository instead uses the standard Python `hidapi` package. Its dependency path was refactored, and has **not yet received equivalent hardware/game validation**. Automated tests cover packet formats, axes, controls and live settings. Please report your results.

The default numeric conversion reproduces the tested Cemu 2.6 / SDL 2.30.3 zero-offset gyro scale. The alternate mode uses the sensitivity coefficient reported by the original device. Neither establishes physical equivalence to a genuine Switch Pro Controller. See [numeric details](NUMERICS.md).

Only one matching `057E:2009` HID gamepad is accepted. That ID is shared by other controllers; device identity and transport are not authenticated. Close the bridge before changing mode or using other controllers. Rumble, touchpad and virtual Xbox output are not implemented; battery and MAC fields are synthetic placeholders.

The service binds only to loopback. No firmware writes, device hiding, virtual drivers or USB reset commands. Temporary IMU/report-mode commands are optional with `--initialize`.

MIT-licensed project code; third-party software retains its own licenses. This is not an official GameSir, Nintendo or Cemu product.
