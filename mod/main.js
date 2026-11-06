import { View, div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { exec, theme } from "herdr";

export default class Dictation extends View {
  init(_props, cx) {
    this.state = "comprobando";
    this.refresh(cx);
    cx.timer.every(1500, (cx) => this.refresh(cx));
  }
  refresh(cx) {
    cx.spawn(async (cx) => {
      try {
        const r = await exec("voxtype", ["status"]);
        this.state = r.code === 0 ? r.stdout.trim() : "no disponible";
      } catch (_) { this.state = "no disponible"; }
      cx.notify();
    });
  }
  toggle(cx) {
    cx.spawn(async (cx) => {
      await exec("dictado-alternar", []);
      this.refresh(cx);
    });
  }
  render(cx) {
    const t = theme();
    const state = this.state;
    const label = state === "recording" ? "■ Detener dictado" : state === "transcribing" ? "◌ Transcribiendo…" : state === "idle" ? "🎙 Dictar" : "🎙 Dictado: " + state;
    return h_flex().size_full().px(12).items_center().bg(t.chrome).text_size(12).text_color(t.foreground)
      .child(div().id("dictation-toggle").px(8).py(3).rounded(4).hover((s) => s.bg(t.raised))
        .on_click((_event, cx) => this.toggle(cx)).child(label));
  }
}
