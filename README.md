# Herdr Voice

[Español](README.es.md) · English

An experimental voice dictation mod for [Herdr App](https://github.com/herdrdev/herdr-app). Click **Dictate**, speak, and click again. [Voxtype](https://voxtype.io/) transcribes locally and the text is pasted into the selected Herdr agent pane. Review it before pressing Enter.

> Early preview: tested on one Fedora/GNOME/Wayland machine. Repeated voice capture and installation on a clean machine still need independent testing. This is a community project, not an official Herdr or Voxtype product.

## Requirements

- Linux, Wayland, Python 3, `wl-copy`, `notify-send`, systemd user services, and Herdr App running locally. Herdr TUI is a different product and is not supported.
- Voxtype installed and on the PATH, with a Whisper model downloaded and its user service named `voxtype` running. See [Voxtype documentation](https://voxtype.io/docs/) for installation and model setup.
- An active Herdr layout with a `status` block, as in the default layout. For this preview, use local agent panes; remote agents are untested.

## Install

Clone or download this repository, open a terminal in its directory, and choose an interface and speech language:

```sh
python3 install.py --ui-language en --speech-language en
```

For a Spanish button and Spanish speech recognition:

```sh
python3 install.py --ui-language es --speech-language es
```

Interface languages are English and Spanish. Whisper language codes such as `en` and `es`, or `auto` for detection, control speech recognition separately; availability and accuracy depend on the model. Use a multilingual model for Spanish.

The installer copies a mod and helper scripts into your user configuration, clones the active layout as `dictado`, activates it, changes Voxtype's output configuration and language, and restarts its user service. It refuses to replace an existing `dictado` layout, mod, or helper scripts. **Back up your Voxtype configuration if you already use it**, as its output settings and speech language are changed. It does not install Voxtype or download a model.

## Use and privacy

Select the target agent pane, click the button once, speak, click it again, and wait until transcription finishes before starting another recording. Do not switch panes while recording; if the selected pane or tab changes, the mod places the text on the clipboard instead of pasting it. It does not press Enter. The text temporarily passes through a file under `XDG_RUNTIME_DIR` and the clipboard. Voxtype may log transcripts; check its configuration and documentation for your privacy needs. The plugin does not send audio to a service, but Voxtype's processing depends on how you configure it.

## Undo

Select your previous layout in Herdr. To restore clipboard output, run `voxtype config set output.mode clipboard`, `voxtype config unset output.post_output_command`, then `systemctl --user restart voxtype`. Restore any previous Voxtype settings from your backup. Remove the installed `dictado` layout and mod and the two `dictado-*` helper scripts if no longer needed.

Contributions and reports are welcome. Never include recordings, private transcripts, tokens, or configuration secrets in reports.
