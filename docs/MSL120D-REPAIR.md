# Restoring Meross MSL120D temperature controls in Home Assistant

**Hardware testing was only and strictly performed on Meross MSL120D bulbs. The complete command test sequence was run on one physical MSL120D bulb. No other Meross bulb model, light strip, dimmer, or diffuser was tested.**

## What was wrong

Setting a specific white temperature was unreliable through Home Assistant. Inspection found that the installed Meross Cloud IoT integration mixed two temperature units: Home Assistant now sends Kelvin, but the integration still treated that number as mireds, the older reciprocal scale. It also referenced temperature properties removed from current Home Assistant.

A second fault affected feedback: the integration reported RGB mode whenever a bulb supported RGB, even when it was operating in white-temperature mode. Temperature feedback used an obsolete property. This made the controls and displayed state misleading.

The test environment used Home Assistant Core 2026.11.1, HA OS 18.4, Meross Cloud IoT 1.3.12, and meross_iot 0.4.10.4. A VM clone was available for recovery, and the integration and dashboard were backed up before changes.

## How it was fixed

The bulb wrapper was changed to:

- Accept Kelvin and convert it to the device's temperature command scale.
- Keep temperature commands within 1–100. An initial attempt using 0 at the warm endpoint was rejected by the tested bulb; the corrected endpoint succeeded.
- Convert reported temperature back to Kelvin using the current Home Assistant property.
- Read active colour mode from device updates instead of assuming RGB.
- Send colour/temperature and brightness together, retaining colour mode when only brightness changes.

The existing advertised range, **2000–6535 K**, was retained. This is a software mapping, **not a verified physical temperature range or a calibration of the bulb's emitted light**.

A separate dashboard view added brightness and temperature sliders, colour favourites, fixed Kelvin buttons, a Bedtime preset, and an Amber preset. These controls use standard Home Assistant features; they are separate from the integration repair.

## How it was tested

Three focused automated tests checked conversion, boundaries, RGB/brightness handling, and mode tracking using simulated devices. These tests do not replace full Home Assistant integration tests or hardware testing.

On the live MSL120D, five temperature commands at 10% requested brightness were followed by explicit device-update requests and state checks:

| Requested | Reported by Home Assistant |
|---|---|
| 2000 K | 2000 K |
| 2200 K | 2201 K |
| 2700 K | 2700 K |
| 4000 K | 3982 K |
| 6535 K | 6535 K |

Two further checks confirmed that RGB `[255, 60, 0]` read back correctly and that changing brightness to 20% retained RGB mode. The dashboard Bedtime button was also tested.

These are command/read-back results, not independent measurements of emitted colour or light intensity. A requested 10% brightness initially reported about 10%, then later about 9%. The device uses discrete values; exact percentages should not be assumed.

The tested bulb's previous temperature and brightness were restored, and it was left off. The deployed file was downloaded again and matched against the local repaired file.

## Relevance to other Meross users

Other users of this same custom integration may benefit where the same unit-conversion and feedback faults occur. Benefits for other models remain **unverified**. Different firmware, temperature ranges, command behaviour, and device types require separate testing. Diffuser temperature handling was not repaired or validated in this work.

This is a tested MSL120D repair candidate, not an official release or a claim of compatibility with every Meross device. Integration updates can overwrite a local repair. The work belongs in the separately maintained Meross custom integration; related existing reports and patches should be considered before proposing an upstream change.

## Human and AI collaboration

**This was a combined human/AI effort because debugging required tracing several interacting layers: the Home Assistant API, custom integration, Meross library, and live device behaviour.** The human supplied the symptoms, equipment and environment, recovery provision, and approval for live testing. The AI assistant inspected the code, developed the repair, executed the automated and live checks, and documented the evidence and limitations. AI involvement does not establish correctness; the stated tests and reviewable code provide the evidence.

## References

- [Home Assistant Kelvin API migration](https://contributors.home-assistant.io/blog/2026/02/23/remove-deprecate-light-features/) — credibility **10/10** for API requirements.
- [Meross integration issue #594](https://github.com/albertogeniola/meross-homeassistant/issues/594) — **9/10** for a matching reported failure.
- [Meross integration issue #574](https://github.com/albertogeniola/meross-homeassistant/issues/574) — **8/10** for a related report on a different, untested device.
- [Existing integration pull requests](https://github.com/albertogeniola/meross-homeassistant/pulls), including #587 and #591 — **9/10** for tracker status at review; their code has not been validated by this work.
