# Raspberry Pi CAN Monitor

A collection of vehicle CAN monitoring, decoding, and logging applications developed for NTU Racing. It turns incoming CAN traffic into browser dashboards and recorded data so vehicle signals can be inspected during development and testing.

## What it is used for

- Read vehicle traffic through CAN interfaces.
- Decode message payloads into engineering signals.
- Display live dashboards for vehicle, battery/AMS, torque-related, GPS, and IMU information.
- Record traffic and inspect previously captured data.
- Explore both custom decoding logic and DBC-based decoding.
- Develop Xsens-related interpretation and dashboard integration.

## How the pieces fit together

The Python applications combine `python-can` acquisition with FastAPI, WebSockets, and HTML/JavaScript dashboards. Dedicated logging scripts preserve recordings, while decoder modules translate the payloads used by different experiments.

| Path | Role |
| --- | --- |
| [GUIvehical-v6_dev.py](GUIvehical-v6_dev.py) | A development version of the live dashboard server |
| [CanDecoder.py](CanDecoder.py), [CanDecoderDBC.py](CanDecoderDBC.py) | Custom and DBC-based decoding approaches |
| [canlogging-v6.py](canlogging-v6.py) | One of the CAN logging iterations |
| [templates](templates), [static](static) | Dashboard pages, styling, and browser logic |
| [XSENS_INTEGRATION.md](XSENS_INTEGRATION.md) | Xsens integration notes |
| [test_can_interfaces.py](test_can_interfaces.py), [test_xsens_decode.py](test_xsens_decode.py) | Interface and decoding checks |

## Project context

This repository is also a development record: the `v2`–`v6` files and alternative dashboards preserve successive approaches. Their configuration and signal coverage differ, so a higher filename version should not be treated as proof of compatibility with every vehicle configuration.

[RPI_Desktop](https://github.com/Ktliu-Tyler/RPI_Desktop) references this repository as a deployment submodule. [nturacing_remote_monitor](https://github.com/Ktliu-Tyler/nturacing_remote_monitor) explores a split vehicle/client and remote-server design, while [CANdecoder](https://github.com/Ktliu-Tyler/CANdecoder) focuses on offline CSV analysis.
