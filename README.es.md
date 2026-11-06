# Herdr Voice

[English](README.md) · Español

Mod experimental de dictado para [Herdr App](https://github.com/herdrdev/herdr-app). Pulsa **Dictar**, habla y pulsa de nuevo. [Voxtype](https://voxtype.io/) transcribe localmente y pega el texto en el panel seleccionado. Revísalo antes de pulsar Enter.

> Versión preliminar: preparada en un equipo Fedora/GNOME/Wayland. Aún hay que comprobar grabaciones repetidas y la instalación en un equipo limpio. Es un proyecto de la comunidad, sin afiliación oficial con Herdr ni Voxtype.

## Requisitos

Linux con Wayland, Python 3, `wl-copy`, `notify-send`, servicios de usuario de systemd y Herdr App abierto. Necesitas Voxtype instalado y disponible en el PATH, con un modelo Whisper descargado y su servicio de usuario `voxtype` activo; consulta su [documentación](https://voxtype.io/docs/). Usa un modelo multilingüe para español. El diseño activo de Herdr debe tener un bloque `status`, como el diseño predeterminado. Se admite el uso con agentes locales; no se ha comprobado en agentes remotos. Herdr TUI es otro producto y no es compatible.

## Instalar

Clona o descarga este repositorio, abre una terminal en su carpeta y ejecuta:

```sh
python3 install.py --ui-language es --speech-language es
```

Para interfaz y reconocimiento en inglés utiliza `python3 install.py --ui-language en --speech-language en`. La interfaz se ofrece en inglés y español; el idioma hablado se elige por separado con un código compatible con Whisper o `auto` para detección. La precisión depende del modelo.

El instalador copia el mod y dos scripts en tu cuenta, clona el diseño activo como `dictado`, lo activa, cambia la salida y el idioma de Voxtype y reinicia su servicio. No reemplaza un diseño, mod o script existente con esos nombres. **Respalda la configuración de Voxtype si ya la usas**, pues se modificará. El instalador no descarga Voxtype ni modelos.

## Uso y privacidad

Selecciona el panel del agente, pulsa el botón una vez, habla y púlsalo de nuevo. Espera a que termine antes de iniciar otra grabación. Si cambias de panel o pestaña durante el dictado, el texto queda en el portapapeles en vez de pegarse. El mod no pulsa Enter. El texto pasa temporalmente por un archivo en `XDG_RUNTIME_DIR` y por el portapapeles. Voxtype puede registrar transcripciones; revisa su documentación y configuración. El mod no envía audio a un servicio, pero el procesamiento depende de cómo configures Voxtype.

## Desinstalar

Selecciona el diseño anterior en Herdr. Para volver a copiar al portapapeles: `voxtype config set output.mode clipboard`, `voxtype config unset output.post_output_command` y `systemctl --user restart voxtype`. Recupera tu configuración anterior desde el respaldo. Si ya no los necesitas, elimina el diseño y mod `dictado` y los dos scripts `dictado-*` instalados.

No compartas grabaciones, transcripciones privadas, tokens ni secretos de configuración en reportes públicos.
