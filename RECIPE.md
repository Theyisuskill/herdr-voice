# Herdr Voice UI recipe

A native 350 px dictation control in the layout's status row. The main button starts/stops recording and shows elapsed time against a five-minute cap. A cancel control is visible while recording, transcribing or preparing delivery; the menu opens recovery and settings.

The same `dictado` mod renders a 520×650 popup with the last action's result, copy/retry/raw-copy/clear actions, comma-separated context terms and paired correction inputs. It uses theme colors and native opacity animation for processing. Status is polled once per second, without redrawing unchanged idle state. Each callback uses its own Herdr context.

`dictado-control` owns session IDs, temporary result files, cancellation, recovery and the detached settings job. Workers never log transcripts or store audio. `targeted_paste.py` uses the verified native core framed protocol to paste into the captured local terminal without Enter, with clipboard fallback. The controller validates the original space/tab/pane/terminal before preparing delivery and invalidates cancelled sessions before final input.

The installer validates dependencies and layout before modifying the app. Its manifest tracks owned files/configuration, with durable private rollback snapshots. Legacy migration can import a verified pre-plugin Voxtype config for safe eventual removal. CPU/Vulkan and the speech model are preserved.

Validation: controller/installer regressions, isolated core bracketed-paste capture, `herdr-app check`, live status and screenshots. Real voice acceptance remains necessary on each target machine; context vocabulary improves hints but cannot guarantee correct words. Remote terminal delivery is clipboard-only.
