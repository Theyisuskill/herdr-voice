# Herdr Voice

[English](README.md) · Español

Dictado local para [Herdr App](https://github.com/herdrdev/herdr-app), con [Voxtype](https://voxtype.io/). Pulsa **Dictar**, habla y pulsa **Detener**. El resultado se pega para revisarlo: **el plugin nunca pulsa Enter**.

## Qué incluye

- Contador de grabación, límite de cinco minutos y aviso cuando quedan 30 segundos. Al llegar al límite se transcribe lo capturado.
- Cancelación durante grabación, transcripción o preparación del pegado. Una cancelación aceptada antes de entregar el texto impide un pegado tardío; no deshace texto ya entregado.
- Estados de grabación, transcripción, entrega, cancelación y aplicación de ajustes. No muestra porcentajes de progreso ficticios.
- Recuperación del último texto: **Copiar**, **Reintentar pegado**, **Copiar sin reglas** y **Borrar**, desde el menú **⋯**.
- Vocabulario de contexto y reglas explícitas de corrección, editables desde ese menú.
- Detección de voz Silero para no transcribir grabaciones silenciosas.

El pegado se dirige al terminal original por la conexión nativa de herdr-core. Solo se intenta si siguen coincidiendo espacio, pestaña, panel y terminal. Si cambias de panel, el terminal es remoto o no admite pegado entre corchetes, el resultado queda en el portapapeles. El reintento necesita el panel original. No utiliza `hc send`, que enviaría Enter.

## Requisitos

Linux/Wayland, Python 3.11 o posterior, `wl-copy`, `notify-send`, servicios de usuario systemd y Herdr App abierto, con `hc` disponible. Voxtype 1.1.1 se ha probado con Whisper local. Herdr TUI es otro producto y no es compatible.

Voxtype debe estar instalado, tener un modelo descargado y su servicio `voxtype` activo. Para español se necesita un modelo multilingüe. El instalador conserva tu modelo y ejecutable: no instala Voxtype ni cambia CPU/Vulkan. Sí descarga el pequeño modelo Silero VAD cuando hace falta. Se requiere `XDG_RUNTIME_DIR` y un diseño de Herdr con bloque `status`.

## Instalar, comprobar y actualizar

```sh
python3 install.py --check
python3 install.py --ui-language es --speech-language es
```

Para actualizar una instalación administrada:

```sh
python3 install.py --upgrade
```

La actualización conserva preferencias y modificaciones externas de idioma, contexto y VAD. Se exige mantener el contrato de entrega del plugin: sin envío automático, streaming ni postprocesamiento externo. Los archivos administrados modificados manualmente se detectan antes de sobrescribirlos; guarda tus cambios aparte antes de actualizar. Los cambios del diseño se conservan y solo se adapta el espacio del control.

Para migrar la versión antigua:

```sh
python3 install.py --upgrade --ui-language es --speech-language es \
  --legacy-config-backup /ruta/al/config.toml/anterior/al/plugin
```

El respaldo debe ser realmente anterior a la instalación antigua. Si no existe, se puede migrar sin ese argumento, pero se bloquea la desinstalación destructiva hasta aportar un respaldo: no se inventa la configuración original ni se restaura un hook que apunte a un script eliminado.

El instalador valida antes de cambiar archivos, respalda cada archivo tocado y revierte si falla la actualización o el arranque. No instala ni actualiza durante un dictado activo. Preferencias, manifiesto y respaldos privados están en `~/.config/herdr-voice/` o el equivalente de `XDG_CONFIG_HOME`. Respeta `HERDR_APP_HOME`.

## Reducir errores

Mantén el idioma correcto y usa un micrófono cercano, con poco ruido. En **⋯**, edita el vocabulario, separado por comas. Se incluyen inicialmente Odoo, PostgreSQL, Python, Mercantil, EcoFlow, Herdr, Voxtype, Claude y Codex. El contexto orienta a Whisper; no lo entrena y no garantiza que reconozca cada palabra.

Añade reglas únicamente para errores repetidos que hayas comprobado. Cada regla muestra el texto reconocido y su corrección. Las reglas respetan palabras completas, ignoran mayúsculas y se aplican en una sola pasada; una sustitución no dispara otra. No se incluyen reglas ambiguas por defecto. **Copiar sin reglas** recupera el resultado anterior a las reglas del plugin, no un audio ni una nueva transcripción.

Guardar ajustes se ejecuta en segundo plano con respaldo y reversión; mientras se aplican no se inicia otra grabación. No se añade otro modelo de IA ni se reescriben tus instrucciones. El reconocimiento sigue pudiendo equivocarse: revisa antes de enviar.

## Privacidad y recuperación

Se conserva solamente el último resultado, con su versión anterior a las reglas, en `XDG_RUNTIME_DIR/herdr-voice` (directorio 0700, archivos 0600). Dura hasta borrarlo, sustituirlo o terminar la sesión de usuario. Empezar o cancelar otra grabación no borra el último resultado válido. No hay historial persistente ni se guarda audio.

Los textos pasan por el portapapeles; **Borrar** elimina la copia de recuperación del plugin, no el portapapeles ni historiales de aplicaciones externas. Los fallos de entrega conservan el resultado para reintentar.

Voxtype normalmente registra transcripciones a nivel INFO. La instalación añade un override systemd propio con `RUST_LOG=warn`, conservando advertencias y errores para impedir nuevos registros INFO del texto; también desactiva notificaciones con la transcripción completa. No elimina registros anteriores. Los registros y las pruebas del plugin no deben contener dictados privados.

## Desinstalar

```sh
python3 install.py --uninstall
```

Restaura el diseño anterior si el activo es `dictado`. Restaura solo ajustes que sigan teniendo el valor aplicado por el plugin y elimina archivos administrados sin modificaciones. Preserva cambios posteriores, preferencias y respaldos. No elimina Voxtype, modelos ni Vulkan. No desinstales durante un dictado.

## Validación

```sh
python3 -m unittest discover -s tests -v
herdr-app check mods/dictado
```

Las pruebas usan archivos temporales y dobles de los servicios, sin grabar el micrófono ni escribir en chats reales. La integración del pegado nativo se puede probar por separado con un `HC_SESSION` aislado. Tras actualizar, verifica la interfaz con `herdr-app status` y `herdr-app shot`; después prueba tu voz en Claude y Codex, incluyendo más de 60 segundos, cancelación y cambio de pestaña.

Proyecto comunitario experimental, sin afiliación oficial con Herdr ni Voxtype. No publiques grabaciones, transcripciones privadas ni secretos de configuración en reportes.
