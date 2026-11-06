# Herdr Voice

A compact voice dictation button in the bottom bar of Herdr App. It starts and stops a local Voxtype recording and inserts the result into the selected agent pane for review. The preview shows the Spanish button.

![Herdr Voice button](preview.png)

## What you see

A 155 px wide block in the 28 px bottom status row, to the left of the existing workspace status. It uses Herdr's chrome background, foreground text, 12 px type and a raised hover background. The button reads “🎙 Dictar” when idle, “■ Detener dictado” while recording and “◌ Transcribiendo…” during transcription. The installer can translate these labels into English.

## How it behaves

Click the button to start recording and click again to stop. The button polls Voxtype's state every 1.5 seconds. Agent states such as working, blocked, done and idle do not affect it. After transcription, the helper pastes into the original focused pane if its pane and tab have not changed; otherwise the transcript is copied to the clipboard. The helper does not press Enter. The button is not a built-in microphone feature and depends on a separately installed local service.

## Built from

`mods/dictado/main.js` is a gpui-kit `View` using `exec` and `theme`; `mods/dictado/mod.json` declares `place: none`. `install.py` clones the active Herdr layout, wraps its `status` block in a row and adds the mod. The scripts `dictado-alternar` and `dictado-herdr-pegar` run `voxtype`, `herdr-app`, `wl-copy`, and `notify-send`. Voxtype reads from the local microphone and transcribes using the configured engine; the helpers read and write temporary files under `XDG_RUNTIME_DIR`. The mod itself does not perform network requests. Voxtype can be configured separately, so its behavior depends on the chosen engine.

## Watch out

Experimental and tested only on one Fedora/GNOME/Wayland machine. Requires Linux, Python 3, `wl-copy`, `notify-send`, Herdr App, and a running Voxtype user service with a downloaded model. It does not work with Herdr TUI. It changes Voxtype's output settings and language; back up existing configuration first. Installation requires the helper scripts and configured service, not merely copying the mod folder. Do not overwrite an existing layout, mod, or helper. The output can be placed on the clipboard, and Voxtype may log transcripts. Transcription and paste into different agents and repeated recordings still need testing. Remote agent panes are untested.

## Done when

- `herdr-app check mods/dictado` passes.
- The cloned layout displays the button without a layout or mod error.
- Clicking twice starts and stops recording, then transcription returns to idle.
- In a real voice test, text appears in the same local agent pane without sending it; switching panes retains the text on the clipboard.
- A second recording works after the first finishes.
