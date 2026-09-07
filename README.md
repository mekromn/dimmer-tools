# Dimmer Tools — KP405 / Kasa firmware research

Open tooling for researching and eventually replacing the firmware on the **TP-Link Kasa KP405** outdoor plug-in dimmer without committing TP-Link proprietary APK or firmware binaries to this public repository.

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
