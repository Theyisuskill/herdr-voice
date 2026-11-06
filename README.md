# Herdr Voice

[Español](README.es.md) · English

Local dictation for [Herdr App](https://github.com/herdrdev/herdr-app), powered by [Voxtype](https://voxtype.io/). Click **Dictate**, speak, then click **Stop**. Review the pasted result: **the plugin never presses Enter**.

## Features

- Recording timer, five-minute cap and a warning with 30 seconds left. Hitting the cap transcribes the captured audio.
- Cancel recording, transcription or paste preparation. Cancellation accepted before delivery prevents late paste; it cannot undo text already delivered.
- Explicit recording, transcription, delivery, cancellation and settings states, without invented progress percentages.
- Recover the last text using **Copy**, **Retry paste**, **Copy without rules** and **Clear**, in the **⋯** menu.
- Editable context vocabulary and explicit correction rules, with Silero speech detection to reject silent recordings.

Automatic paste uses a connection to the original herdr-core terminal. Space, tab, pane and terminal must still match. A changed pane, remote terminal or missing bracketed-paste support falls back to clipboard. Retry requires the original pane. The plugin does not use `hc send`, which would submit with Enter.

## Requirements

Linux/Wayland, Python 3.11+, `wl-copy`, `notify-send`, systemd user services, a running Herdr App and `hc` on PATH. Voxtype 1.1.1 with local Whisper was tested. Herdr TUI is a different, unsupported product.

Install Voxtype, download a model and start its `voxtype` user service first. Use a multilingual model for Spanish. The installer preserves your model and CPU/Vulkan executable; it does not install Voxtype. It downloads the small Silero VAD model if needed. `XDG_RUNTIME_DIR` and a Herdr layout with a `status` block are required.

## Install, check and upgrade

```sh
python3 install.py --check
python3 install.py --ui-language en --speech-language en
```

Upgrade a managed installation:

```sh
python3 install.py --upgrade
```

Upgrades retain preferences and external changes to language, context and VAD. The plugin's output contract is enforced: no auto-submit, streaming or external postprocessing. Manually changed managed files are detected before overwrite; preserve your changes separately before upgrading. Layout customization is retained while resizing the dictation control.

Migrate the legacy version:

```sh
python3 install.py --upgrade --ui-language en --speech-language en \
  --legacy-config-backup /path/to/voxtype-config-before-the-plugin.toml
```

Only supply a verified configuration from before the legacy installation. Migration without that argument is possible, but destructive uninstall is blocked until an original backup is supplied. The installer will not invent original values or restore a hook pointing to a deleted helper.

Installation validates first, snapshots every touched file and rolls back if update or startup fails. It requires idle dictation. Private preferences, installation manifest and backups live under `~/.config/herdr-voice/` (or `XDG_CONFIG_HOME`). `HERDR_APP_HOME` is respected.

## Improve recognition

Select the right speech language and use a nearby microphone with little background noise. Edit the comma-separated context vocabulary in **⋯**. Initial terms are Odoo, PostgreSQL, Python, Mercantil, EcoFlow, Herdr, Voxtype, Claude and Codex. Context guides Whisper; it is not model training or a guarantee of correct recognition.

Add correction rules only for verified recurring errors. Each rule contains a recognized word/phrase and its replacement. Matching respects whole words, ignores case and uses a single pass without cascading. No ambiguous rules are enabled by default. **Copy without rules** retrieves the result before this plugin's replacements; it does not recover audio or rerun transcription.

Settings are applied by a detached job with backup and rollback. New recordings are blocked during application. No additional AI model rewrites your instructions. Recognition can still be wrong: review before submitting.

## Privacy and recovery

Only the last result and its pre-rule version are retained in `XDG_RUNTIME_DIR/herdr-voice` (0700 directory, 0600 files). They last until cleared, replaced or the user session ends. Starting or cancelling another recording preserves the last valid result. No persistent transcript history or audio files are stored.

Text passes through the clipboard. **Clear** removes the plugin's recovery copy, not clipboard contents or other applications' histories. Delivery failures retain the result for recovery.

Upstream Voxtype normally logs transcripts at INFO level. Installation adds its own systemd override using `RUST_LOG=warn`, retaining warnings/errors while preventing new INFO transcript logs, and disables notifications containing the full transcript. Existing logs are not deleted. Do not include private dictation in plugin logs or public reports.

## Uninstall

```sh
python3 install.py --uninstall
```

Restores the previous layout when `dictado` is active. Only settings still matching the plugin-applied values are restored, and only unchanged managed files are removed. Later modifications, preferences and backups are preserved. Voxtype, models and Vulkan are retained. Finish any active dictation first.

## Verify

```sh
python3 -m unittest discover -s tests -v
herdr-app check mods/dictado
```

Tests use scratch files and simulated services without recording the microphone or writing into real chats. Native paste can be integration-tested separately in an isolated `HC_SESSION`. After upgrading, inspect `herdr-app status` and `herdr-app shot`, then test your voice in Claude and Codex, including over 60 seconds, cancellation and a tab switch.

Experimental community project, not affiliated with Herdr or Voxtype. Never publish recordings, private transcripts or configuration secrets in reports.
