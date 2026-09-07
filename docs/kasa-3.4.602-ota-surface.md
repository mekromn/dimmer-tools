# Kasa 3.4.602 firmware-update surface

This note records static findings from the user-supplied Kasa 3.4.602 APK without committing the APK itself.

## APK identity

| Field | Value |
|---|---|
| Version | 3.4.602 |
| versionCode | 1392 |
| Original package | `com.tplink.kasa_android` |
| Research package | `com.mekromn.dimmertools` |
| minSdk | 24 |
| targetSdk | 35 |
| Application class | `com.tplink.iot.core.TapoAppContext` |

The build metadata embedded in the APK names a 2026-07-24 Kasa Play Store distribution build.

## Firmware classes and models

The DEX string tables contain, among others:

```text
Lcom/tplink/cloud/api/FirmwareApi;
Lcom/tplink/cloud/api/FirmwareV2Api;
Lcom/tplink/cloud/bean/firmware/params/FirmwareInfoParams;
Lcom/tplink/cloud/bean/firmware/params/NonCloudFirmwareInfoParams;
Lcom/tplink/cloud/bean/firmware/result/FirmwareInfoResult;
Lcom/tplink/cloud/bean/firmware/result/FirmwareListResult;
Lcom/tplink/hellotp/features/device/firmwareupdate/FirmwareUpdateActivity;
Lcom/tplink/hellotp/features/device/firmwareupdate/FirmwareUpdateFragment;
```

Useful model/property strings include:

```text
fw_url
fw_ver
fw_version
hw_id
oem_id
getFirmwareLatestInfo
getFirmwareDownloadState
getFirmwareUpgradeState
```

## FirmwareV2Api routes recovered from DEX annotations

Kasa 3.4.602 contains signed Retrofit-style firmware calls for:

```text
{url}/api/v2/common/getIntlFwList
{url}/api/v2/common/getIntlFwVersions
{url}/v2/firmware/getLatestFwListForNonCloudDevices
```

The methods carry a `signature-required:true` header marker. That makes the first probe target very clear: log the selected base URL, request body and raw response before changing any update behavior.

## Firmware query/request fields

`FirmwareInfoParams` contains:

```text
devFwCurrentVer
deviceId
fwId
hwId
locale
oemId
```

The normal firmware result exposes:

```text
fwLocation
fwReleaseDate
fwReleaseLog
fwTitle
fwType
fwUrl
fwVer
getFwReleaseLogUrl
```

The non-cloud firmware result is even more useful for research and exposes:

```text
b2bReleaseLog
channel
cloudPush
fwAddition
fwLocation
fwMd5
fwReleaseDate
fwReleaseLog
fwReleaseLogUrl
fwSecureUrl
fwTitle
fwType
fwVer
hwId
oemId
status
```

## Legacy TPRA operations present in the APK

```text
get_cloud_firmware_info
start_firmware_upgrade
get_firmware_upgrade_status
```

The APK also contains corresponding legacy endpoint strings under `tpra.tp-link.com`. These strings prove those code paths exist; they do **not** by themselves prove which route KP405 uses at runtime in 2026. The probe build should instrument both `FirmwareApi` and `FirmwareV2Api` and record the actual request path selected for the KP405.

## Working hypothesis for "up to date"

The stock UI showing "up to date" while a newer release exists publicly is consistent with **server-side progressive rollout / eligibility**. It is not evidence that 1.0.6 is the final KP405 firmware, nor that Kasa 3.4.602 has no firmware code.

The first runtime capture should therefore log the entire latest-firmware response before we attempt to alter any behavior.
