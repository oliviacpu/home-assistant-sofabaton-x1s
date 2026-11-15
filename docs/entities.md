# Entity reference

Each configured hub provides entities for controlling Sofabaton from Home Assistant, using remote and hub activity in automations, and managing the integration. Home Assistant generates default entity IDs from the hub name; the tables use `<hub>` as a placeholder. Entity IDs can be renamed in Home Assistant.

## ◇ Control the hub from Home Assistant

Use these entities in dashboards or custom UIs, automations, and scripts.

| Platform | Default entity                                   | Purpose                                                                                                                     |
| -------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Remote   | `remote.<hub>_remote`                            | Send commands and control Activities                                                                                        |
| Infrared | `infrared.<hub>_ir_emitter`                      | Let compatible Home Assistant infrared integrations send commands through the hub; requires a recent Home Assistant release |
| Select   | `select.<hub>_activity`                          | View or change the current Activity                                                                                         |
| Button   | `button.<hub>_volume_up`, `button.<hub>_mute`, … | Send Activity-aware commands                                                                                                |

For `remote.send_command`, `remote.turn_on`, and `remote.turn_off` examples, see the [remote entity guide](remote_entity.md).

## ◇ Use hub and remote activity in automations

These entities expose state changes and received commands to Home Assistant.

| Platform      | Default entity                      | Purpose                                                |
| ------------- | ----------------------------------- | ------------------------------------------------------ |
| Sensor        | `sensor.<hub>_activity`             | Current Activity, including while the app is connected |
| Sensor        | `sensor.<hub>_wifi_commands`        | Latest Wifi Command or Wifi Event press                |
| Event         | `event.<hub>_button_press`          | Each Wifi Command or Wifi Event press (`short`/`long`) |
| Event         | `event.<hub>_hub_event`             | Activity started/stopped, powered off, OFF while off   |
| Binary sensor | `binary_sensor.<hub>_hub_connected` | Physical hub connection state                          |
| Binary sensor | `binary_sensor.<hub>_app_connected` | Official-app proxy connection state                    |

The two event entities fire for every occurrence; their state is the time of the last one and the `event_type`
attribute says which it was. `event.<hub>_button_press` carries `device`, `device_id`, `command`, `command_index` and
`transport`. `event.<hub>_hub_event` carries `activity`/`activity_id` (the activity that started, stopped or was
running before power-off) and the `from_`/`to_` pair of the transition; an activity switch fires `activity_stop` then
`activity_start`. Trigger on a state change of the entity and read `trigger.to_state.attributes.event_type`.

For Wifi Commands, Wifi Events, Hub Events, Activity Events, and a sensor automation example, see the [remote and hub trigger guide](wifi_commands.md).

## ◇ Configuration, maintenance, and diagnostics

| Platform | Default entity                         | Purpose                                                                                                                             |
| -------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Sensor   | `sensor.<hub>_index`                   | Diagnostic Activity, Device, command, macro, and favorite index                                                                     |
| Switch   | `switch.<hub>_proxy_enabled`           | Enable or disable proxy discovery and listening                                                                                     |
| Switch   | `switch.<hub>_hex_logging`             | Enable detailed protocol logging                                                                                                    |
| Switch   | `switch.<hub>_wifi_device`             | Control the shared HTTP callback listener; re-enables itself while an HTTP-delivered Wifi Device or the Wifi Events device needs it |
| Button   | `button.<hub>_find_remote`             | Sound the physical remote's buzzer                                                                                                  |
| Button   | `button.<hub>_resync_remote`           | Synchronize the physical remote                                                                                                     |
| Text     | `text.<hub>_ip_address`                | Override the stored hub IP; disabled by default                                                                                     |
| Text     | `text.<hub>_home_assistant_ip_address` | View or override the Home Assistant IPv4 address advertised to this hub; disabled by default                                        |
| Sensor   | `sensor.<hub>_ir_intercept`            | Last command intercepted by the infrared emitter entity (HA 2026.8 or newer); disabled by default                                   |
| Sensor   | `sensor.<hub>_remote_firmware`         | Firmware of the physical remote (X1/X1S), from the hub's version exchange; unknown until the hub has answered one                   |
| Sensor   | `sensor.<hub>_wifi_firmware`           | Firmware of the hub's Wi-Fi module (`major.minor.patch`), from the same exchange                                                    |

The **Home Assistant IP address** entity shows the local address selected for
that hub. Enable it on the hub's device page to set an override; the address
must belong to the Home Assistant host. Clear the field to return to automatic
selection. Its `mode` attribute reports `automatic` or `manual`. This changes
the address the hub uses to connect back to Home Assistant, not the hub's own
IP address. See the [networking guide](networking.md) for multi-interface routing.

## ◇ Availability while the Sofabaton app is connected

Entities that write to the hub become unavailable while the official Sofabaton app is connected through the proxy. This prevents competing commands and configuration writes. Diagnostic and state-reporting entities remain available where possible.

Use `binary_sensor.<hub>_app_connected` to check whether the app owns the connection and `binary_sensor.<hub>_hub_connected` to check the physical hub connection. Close the app to return control to Home Assistant.
