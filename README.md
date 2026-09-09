# Dimmer Tools — KP405 / Kasa firmware research

Open tooling for researching and eventually replacing the firmware on the **TP-Link Kasa KP405** outdoor plug-in dimmer without committing TP-Link proprietary APK or firmware binaries to this public repository.

## Non-negotiable design goal: works with no Internet

The open firmware must remain fully controllable when the WAN/Internet is unavailable. Cloud services may be optional conveniences, but they must never be required for basic operation.

Hard requirements:

- physical button always works locally;
- on/off and dimming work over the local LAN with no Internet connection;
- direct local Web UI hosted by the KP405;
- local REST/WebSocket API;
- local MQTT support and Home Assistant discovery;
- schedules, timers, scenes, minimum/maximum brightness, and power-on behavior are stored and executed on-device;
- no login, vendor account, cloud token, or remote server is required for control;
- if the configured Wi-Fi network is unavailable, the device can expose a recovery/control AP after a configurable delay;
- loss of DNS, NTP, WAN, or cloud connectivity must not stall the control loop or make the device unresponsive;
- cached/local timekeeping keeps schedules running through temporary Internet outages, with RTC/time resynchronization when a trusted local or Internet time source returns;
- cloud integrations, if enabled at all, run as an additive layer over local control rather than sitting in the command path;
- firmware update checks are never required for normal operation and updates are user-controlled;
- no telemetry or vendor analytics are necessary for functionality.

A simple architectural rule follows from this: **mains control and dimming must be local-first; networking is an optional control transport, not a dependency.**

## Current target

- Device family: KP405
- Observed case revision: V1.8 / V1-family hardware
- Observed stock firmware: 1.0.6
- Android research base: Kasa 3.4.602 (versionCode 1392)
- Stock Android application id: `com.tplink.kasa_android`
- **Mod application id: `com.mekromn.dimmertools`**

The mod package is intentionally different so the research build can coexist with the normal Kasa app. `com.mekromn.dimmertools` is also the same character length as the stock id, which leaves open a minimal binary-patching fallback if we need one later.

## What we found in Kasa 3.4.602

Static inspection confirms the APK still contains the complete firmware-update client surface rather than a dead/removed menu. Relevant symbols include:

- `com.tplink.cloud.api.FirmwareApi`
- `com.tplink.cloud.api.FirmwareV2Api`
- `FirmwareInfoParams`, `FirmwareInfoResult`, `FirmwareListResult`
- `get_cloud_firmware_info`
- `start_firmware_upgrade`
- `get_firmware_upgrade_status`
- `fw_url`, `fw_ver`, `hw_id`, `oem_id`
- legacy TPRA endpoint strings for cloud firmware info / upgrade status / upgrade start

That strongly suggests the "up to date" result is controlled by server/device eligibility rather than this Kasa build simply lacking update logic.

## First-phase goal

Build a side-by-side **Kasa Probe** that defaults to observation, not flashing:

1. capture the exact firmware-info request and response for a KP405;
2. display hardware/OEM identifiers and rollout eligibility;
3. capture firmware metadata and URL without starting an install;
4. log upgrade-state polling;
5. keep destructive/flash actions behind a separate explicit control;
6. preserve the stock Kasa app untouched.

Once we understand the OTA trust chain, we can determine whether a wireless custom-firmware installer is possible or whether the first open-firmware flash must use the RTL8710CF boot ROM/UART path.

## Tools

### `tools/apk_probe.py`

Dependency-free static APK probe. It reads Android binary XML and DEX string tables directly, so it can report the application id, SDK levels, and firmware/OTA symbols without decompiling or modifying the APK.

```bash
python3 tools/apk_probe.py /path/to/Kasa.apk --limit 100
python3 tools/apk_probe.py /path/to/Kasa.apk --json > kasa-probe.json
```

### `tools/patch_decoded_tree.py`

Patches an apktool-decoded tree from the stock application id to:

```text
com.mekromn.dimmertools
```

It also catches provider authorities and other text references containing the old id.

### `scripts/build_probe.sh`

Rebuild/sign helper for a local copy of the APK. The proprietary base APK and signing keys are intentionally ignored/not committed.

Required locally: Java, apktool, Python 3, Android `zipalign`, and `apksigner`.

```bash
export APKTOOL_JAR=/path/to/apktool_3.0.3.jar
scripts/build_probe.sh /path/to/Kasa.apk
```

## Safety / development rule

Until the OTA format and verification path are understood, the research build should be **capture-only by default**. Do not trigger an unknown firmware package, modify a firmware image, or power-cycle a device while it is flashing.

The KP405 is a mains-powered device. Hardware work must use appropriate isolation and should not connect a normal grounded USB-UART adapter to energized mains-referenced circuitry.
