# Fixing Meross bulb temperature control

This patch restores Kelvin temperature control and correct colour-mode feedback in the Meross Cloud IoT integration. Users can set a white temperature through Home Assistant and see the reported temperature, rather than an incorrect RGB state or a failed action.

**Hardware testing was only and strictly on MSL120D bulbs. The full command sequence was tested on one physical MSL120D. Compatibility with other models has not been established.**

## The fix

Home Assistant supplies colour temperature in Kelvin. The integration was treating that value as mireds and using properties removed from Home Assistant. It also selected the reported colour mode from the bulb's capabilities instead of its active setting.

The changes in `LightEntityWrapper`:

- Convert Kelvin to the device's 1–100 temperature scale and convert feedback back to Kelvin.
- Expose `color_temp_kelvin` and explicit Kelvin limits.
- Track RGB and temperature modes from device updates, preserving the mode when brightness changes.
- Send colour and brightness in one command, before turning an off bulb on.

The existing 2000–6535 K mapping is retained. It is not a measured specification of the bulb's emitted light. Diffuser temperature handling is outside this repair.

## Incorporating the patch

The branch is based on **v1.3.12**. The bulb file matches the version used for the live tests.

Maintainers can fetch the branch and review the code and tests without taking the fork's README changes:

```bash
git fetch https://github.com/AtomicRobotMan0101/meross-homeassistant.git fix/msl120d-kelvin-controls
git diff v1.3.12 FETCH_HEAD -- custom_components/meross_cloud/light.py tests/test_msl120d_light.py
```

After reviewing the diff, apply those changes to a working branch:

```bash
git diff v1.3.12 FETCH_HEAD -- custom_components/meross_cloud/light.py tests/test_msl120d_light.py | git apply --3way
python3 -m unittest discover -s tests -v
```

Resolve any differences against the target branch, particularly if it already contains Kelvin or colour-mode fixes. The dashboard presets used during testing are not required by this patch.

## Test evidence

Test environment: Home Assistant Core **2026.11.1**, HA OS **18.4**, Meross Cloud IoT **1.3.12**, and `meross_iot` **0.4.10.4**.

Five temperature commands were checked after explicit device-update requests:

| Requested | Reported |
|---|---|
| 2000 K | 2000 K |
| 2200 K | 2201 K |
| 2700 K | 2700 K |
| 4000 K | 3982 K |
| 6535 K | 6535 K |

RGB `[255, 60, 0]` also read back correctly, and changing brightness retained RGB mode. A dashboard preset successfully requested 2000 K at 10% brightness. Later brightness feedback was approximately 9%, so percentage precision should not be assumed.

These are software/device read-backs, not measurements of emitted light. Three automated tests use simulated devices to check conversion, boundaries, combined commands, and mode tracking; they do not run the full Home Assistant runtime. [Detailed results](MSL120D-test-results.json) are included.

Before extending support claims, test other bulb models and firmware, external colour changes, and reconnect behaviour. Existing reports [#594](https://github.com/albertogeniola/meross-homeassistant/issues/594) and [#574](https://github.com/albertogeniola/meross-homeassistant/issues/574) describe related failures; proposed fixes should be reviewed alongside this work. Source credibility: **9/10** and **8/10**, respectively, as user-reported evidence.

## Credit

Developed through combined human/AI debugging of the Home Assistant API, integration, Meross library, and live MSL120D behaviour. Human experience and testing direction were combined with AI-assisted code analysis, implementation, and test execution.
