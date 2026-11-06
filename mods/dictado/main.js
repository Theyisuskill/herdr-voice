import { View, div } from "gpui-kit";
import { h_flex, v_flex, InputState, Input } from "gpui-base";
import { exec, theme, props, openOverlay, closeOverlay } from "herdr";

const active = ["starting", "recording", "stopping", "transcribing", "delivering", "cancelling", "updating"];
const clock = (s) => `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

export default class Dictation extends View {
  init(_props, cx) {
    this.data = { state: "checking", elapsed: 0, limit: 300 };
    this.panel = Boolean(props()?.panel || props()?.overlay);
    this.busy = false;
    this.refreshing = false;
    this.error = "";
    this.inputsReady = false;
    this.ruleInputs = [];
    this.refresh(cx);
    cx.timer.every(1000, (cx) => this.refresh(cx));
  }

  text(es, en) { return this.data.ui_language === "en" ? en : es; }

  setupInputs(cx) {
    if (!this.panel || this.inputsReady) return;
    this.glossary = InputState.new({ value: (this.data.glossary ?? []).join(", ") });
    this.glossary.on("change", (_e, cx) => cx.notify());
    for (const rule of this.data.rules ?? []) this.addRule(rule.from, rule.to, cx);
    this.inputsReady = true;
  }

  addRule(from, to, cx) {
    const row = { from: InputState.new({ value: from }), to: InputState.new({ value: to }) };
    row.from.on("change", (_e, cx) => cx.notify());
    row.to.on("change", (_e, cx) => cx.notify());
    this.ruleInputs.push(row);
    cx.notify();
  }

  refresh(cx) {
    if (this.refreshing || this.busy) return;
    this.refreshing = true;
    cx.spawn(async (cx) => {
      try {
        const r = await exec("dictado-control", ["status"]);
        const data = JSON.parse(r.stdout);
        if (!data.ok) throw new Error(data.error);
        const changed = JSON.stringify(this.data) !== JSON.stringify(data);
        if (!this.busy) this.data = data;
        this.setupInputs(cx);
        if (changed) cx.notify();
      } catch (_) {
        if (!this.busy && this.data.state !== "unavailable") {
          this.data.state = "unavailable";
          cx.notify();
        }
      } finally { this.refreshing = false; }
    });
  }

  action(name, cx, args = []) {
    if (this.busy) return;
    this.busy = true;
    this.error = "";
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        const r = await exec("dictado-control", [name, ...args]);
        const data = JSON.parse(r.stdout);
        if (!data.ok) this.error = data.error;
        else this.data = data;
      } catch (_) {
        this.error = this.text("No se pudo completar la acción. Revisa Voxtype.", "Action failed. Check Voxtype.");
      } finally { this.busy = false; }
      cx.notify();
    });
  }

  save(cx) {
    const glossary = this.glossary.value().split(",").map(s => s.trim()).filter(Boolean);
    const rules = this.ruleInputs.map(r => ({ from: r.from.value(), to: r.to.value() }));
    this.action("settings", cx, ["--glossary", JSON.stringify(glossary), "--rules", JSON.stringify(rules)]);
  }

  button(id, label, enabled, action, small = false) {
    const t = theme();
    return div().id(id).px(small ? 7 : 10).py(small ? 2 : 6).rounded(5)
      .bg(t.raised).text_color(enabled ? t.foreground : t.dim).text_size(12)
      .disabled(!enabled).hover(s => enabled ? s.bg(t.hover) : s)
      .on_click((_e, cx) => { if (enabled) action(cx); }).child(label);
  }

  label() {
    const s = this.data.state;
    if (this.busy) return this.text("Procesando…", "Processing…");
    if (s === "recording") return this.text("■ Detener", "■ Stop") + ` ${clock(this.data.elapsed)} / ${clock(this.data.limit)}`;
    if (s === "transcribing") return this.text("Transcribiendo…", "Transcribing…");
    if (s === "delivering") return this.text("Preparando pegado…", "Preparing paste…");
    if (s === "updating") return this.text("Aplicando ajustes…", "Applying settings…");
    if (s === "starting") return this.text("Iniciando…", "Starting…");
    if (s === "stopping") return this.text("Deteniendo…", "Stopping…");
    if (s === "cancelling") return this.text("Cancelando…", "Cancelling…");
    if (s === "unavailable" || s === "external_busy") return this.text("Dictado no disponible", "Dictation unavailable");
    if (s === "checking") return this.text("Comprobando…", "Checking…");
    return this.text("🎙 Dictar", "🎙 Dictate");
  }

  input(state, placeholder) {
    const t = theme();
    return Input.new(state).h(32).px(8).rounded(5).border_1().border_color(t.input)
      .bg(t.background).text_color(t.foreground).text_size(12);
  }

  panelView(cx) {
    const t = theme();
    const running = active.includes(this.data.state);
    const disabled = running || this.busy;
    const caption = text => div().pt(12).pb(5).text_size(12).font_semibold().child(text);
    const section = v_flex().id("dictado-settings-scroll").w_full().max_h(620).overflow_y_scrollbar()
      .p(16).gap(8).bg(t.popover).text_color(t.foreground)
      .child(h_flex().items_center().gap(10)
        .child(div().flex_1().font_semibold().child(this.text("Dictado", "Dictation")))
        .child(this.button("close", "×", true, () => closeOverlay(props().overlay))))
      .child(div().text_size(12).text_color(t.muted).child(this.label()))
      .child(div().text_size(12).text_color(this.error ? t.blocked : t.muted).child(this.error || this.data.message || ""))
      .child(caption(this.text("Último dictado de esta sesión", "Last dictation of this session")))
      .child(h_flex().gap(8)
        .child(this.button("copy", this.text("Copiar", "Copy"), this.data.has_last && !this.busy, cx => this.action("copy", cx)))
        .child(this.button("retry", this.text("Reintentar pegado", "Retry paste"), this.data.has_last && !disabled, cx => this.action("retry", cx))))
      .child(h_flex().gap(8)
        .child(this.button("copy-raw", this.text("Copiar sin reglas", "Copy without rules"), this.data.has_last && !this.busy, cx => this.action("copy-raw", cx)))
        .child(this.button("clear", this.text("Borrar", "Clear"), this.data.has_last && !this.busy, cx => this.action("clear", cx))))
      .child(div().text_size(11).text_color(t.dim).child(this.text("Solo se conserva el último texto. No se guarda audio.", "Only the last text is retained. No audio is saved.")));
    if (running && this.data.state !== "updating") section.child(this.button("cancel-panel", this.text("Cancelar dictado", "Cancel dictation"), !this.busy, cx => this.action("cancel", cx)));
    if (!this.inputsReady) return section;
    section.child(caption(this.text("Vocabulario de contexto", "Context vocabulary")))
      .child(div().text_size(11).text_color(t.dim).child(this.text("Términos separados por comas. Ayudan al reconocimiento; no garantizan el resultado.", "Comma-separated terms. They guide recognition; results are not guaranteed.")))
      .child(this.input(this.glossary))
      .child(caption(this.text("Corregir errores repetidos", "Correct recurring errors")));
    this.ruleInputs.forEach((row, index) => {
      section.child(h_flex().gap(6).items_center()
        .child(div().flex_1().child(this.input(row.from)))
        .child(div().child("→"))
        .child(div().flex_1().child(this.input(row.to)))
        .child(this.button(`remove-${index}`, "×", !disabled, cx => { this.ruleInputs.splice(index, 1); cx.notify(); })));
    });
    section.child(this.button("add-rule", this.text("Añadir corrección", "Add correction"), !disabled, cx => this.addRule("", "", cx)))
      .child(div().text_size(11).text_color(t.dim).child(this.text("Se reemplazan palabras o frases completas. Evita reglas ambiguas.", "Replaces whole words or phrases. Avoid ambiguous rules.")))
      .child(this.button("save-settings", this.text("Guardar ajustes", "Save settings"), !disabled, cx => this.save(cx)))
      .child(div().text_size(11).text_color(t.dim).child(this.text("Los ajustes se aplican cuando no hay un dictado activo.", "Settings can be applied when no dictation is active.")));
    return section;
  }

  render(cx) {
    if (this.panel) return this.panelView(cx);
    const t = theme();
    const s = this.data.state;
    const canToggle = !this.busy && ["idle", "error", "recording"].includes(s);
    return h_flex().size_full().px(8).gap(6).items_center().bg(t.chrome)
      .text_color(t.foreground).text_size(12)
      .child(div().flex_1().tooltip(this.error || this.data.message || this.label())
        .child(this.button("dictation-toggle", this.label(), canToggle, cx => this.action(s === "recording" ? "stop" : "start", cx), true)
          .when(["transcribing", "delivering"].includes(s), el => el.loop("opacity", { from: 0.5, to: 1, period: 1200 }))))
      .when(active.includes(s) && s !== "updating", el => el.child(this.button("dictation-cancel", "×", !this.busy, cx => this.action("cancel", cx), true).tooltip(this.text("Cancelar", "Cancel"))))
      .child(this.button("dictation-menu", "⋯", true, () => openOverlay({ mod: "dictado", props: { panel: true }, kind: "popup", width: 520, height: 650 }), true).tooltip(this.text("Recuperar texto y ajustes", "Recover text and settings")));
  }
}
