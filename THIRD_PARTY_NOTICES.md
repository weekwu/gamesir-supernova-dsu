# Third-party references and dependency

Project code is licensed under MIT. No BetterJoy executable, HID DLL, Cemu executable, ROM or game asset is bundled.

- [cython-hidapi](https://github.com/trezor/cython-hidapi) / the Python `hidapi` package is installed separately from PyPI. Its BSD wrapper and HIDAPI's own licensing notices remain applicable; see the upstream repository's license files.
- [HIDAPI](https://github.com/libusb/hidapi) provides the underlying device access. Refer to its upstream licensing options and notices.
- [SDL](https://github.com/libsdl-org/SDL) is the reference for Switch sensor unit conversion and axis conventions. SDL uses the zlib license; it is not bundled here.
- [BetterJoy](https://github.com/Davidobot/BetterJoy), MIT, was used to inspect the observed USB reset path and confirm the Pro-controller axis convention. Its code/binaries are not distributed by this repository.
- [Cemu](https://github.com/cemu-project/Cemu), MPL-2.0, is the reference for the consuming DSU format and motion input path. No Cemu source or binary is bundled.
- [Cemuhook/DSU protocol documentation](https://v1993.github.io/cemuhook-protocol/) documents the wire format.

GameSir, Nintendo and Cemu names identify compatibility targets. No affiliation or endorsement is implied.
