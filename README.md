# reverse-engineer-frontend (RFA)

Skill para Claude Code y otros agentes compatibles con skills: ingeniería
inversa del **frontend** de cualquier sitio web, aplicación web o renderer de
Electron, con dos objetivos encadenados:

1. **Replicar todo el front** (maquetación, componentes, responsive, estados y
   animaciones) en tu propio stack, contrastado con la evidencia capturada.
2. **Convertirlo en una marca blanca**: sacar cada decisión de marca (colores,
   tipografía, logo, nombre, imágenes, textos) a un `brand.config` de variables
   y entregar un tema neutro por defecto, de modo que la plantilla sea genérica
   y reutilizable y los activos protegidos del original se reemplacen en vez de
   arrastrarse.

Es la hermana de [REA (Reverse Engineer Anything)](https://github.com/morluto/rea),
que se centra en binarios, APIs y lógica interna. Esta skill se centra en lo
que REA no cubre: DOM, CSS, tokens de diseño, tipografía, componentes,
responsive, animaciones e interacciones.

## Qué hace

1. **Captura** la página real con Playwright: DOM, estilos computados de cada
   elemento visible, variables CSS, fuentes, hojas de estilo, keyframes,
   media queries, captura de pantalla e inventario de red. Admite varios
   viewports y estados (hover, foco, clic, scroll, modo oscuro, movimiento
   reducido) y puede conectarse a un navegador o Electron ya abiertos por CDP.
2. **Detecta el stack**: framework, meta-framework, estrategia CSS, librería
   de componentes, librería de animación, constructor de sitios, bundler,
   analítica. Cada hallazgo lleva la evidencia literal que lo justifica.
3. **Extrae tokens de diseño**: paleta por uso y rol, escala tipográfica,
   espaciado, radios, sombras, breakpoints, z-index y vocabulario de
   movimiento. Genera `tokens.json`, `tokens.css` y un `theme.extend` para
   Tailwind.
4. **Descompone en componentes** con variantes, estados y contrato de
   accesibilidad.
5. **Reconstruye** en tu stack y **verifica la paridad** comparando capturas
   de pantalla y árboles de nodos.
6. **Marca blanca** con `whitelabel.py`: genera `brand.config.json`, un
   `theme.neutral.css` para publicar, un `theme.captured.css` solo de
   referencia, un tema de Tailwind cableado a las variables y un
   `brand-assets.md` con el logo, nombre, fuentes, imágenes y textos a
   reemplazar. El contrato de theming es el conjunto mínimo de variables que,
   al cambiarlas, re-marcan toda la plantilla.
7. **Informa** con una plantilla que separa hechos medidos de inferencias e
   incluye la sección de marca blanca y notas de licencia.

## Instalación

Copia la carpeta `reverse-engineer-frontend/` en el directorio de skills de tu
agente:

- Claude Code (proyecto): `.claude/skills/reverse-engineer-frontend/`
- Claude Code (usuario): `~/.claude/skills/reverse-engineer-frontend/`
- Agentes que leen `.agents/skills/` (Codex, Cursor y otros): `.agents/skills/reverse-engineer-frontend/`

Captura de sitios reales: añade `--autoscroll` (contenido lazy y reveals) y
`--dismiss` (banners de cookies). Si el entorno no tiene salida a internet, usa
`ingest_har.py` sobre un HAR que exportes del navegador, o `--proxy`. El parser
de color admite `hsl()` y `color(srgb …)` además de rgb.

Los scripts necesitan:

- Node 18+ con `playwright` (`npm i playwright && npx playwright install chromium`)
  o un Chromium existente con `--executable-path`.
- Python 3.9+. Solo `compare_screenshots.py` necesita Pillow (`pip install pillow`).

## Uso rápido

```bash
node scripts/capture_page.js https://ejemplo.com --out ./rfa/ejemplo --viewport 1440x900 --viewport 390x844 --full-page
python3 scripts/detect_stack.py ./rfa/ejemplo
python3 scripts/extract_tokens.py ./rfa/ejemplo --out ./rfa/ejemplo/tokens
python3 scripts/inventory_components.py ./rfa/ejemplo/1440x900 --markdown
node scripts/capture_page.js https://ejemplo.com --out ./rfa/ejemplo-hover --hover ".nav a" --no-har
python3 scripts/diff_captures.py ./rfa/ejemplo/1440x900 ./rfa/ejemplo-hover/1440x900
# ... reconstruye en tu proyecto, captura tu versión igual que la original y:
python3 scripts/compare_screenshots.py ./rfa/ejemplo/1440x900/screenshot.png ./rfa/mio/1440x900/screenshot.png --out diff.png
python3 scripts/diff_captures.py ./rfa/ejemplo/1440x900 ./rfa/mio/1440x900 --mode parity
# marca blanca: plantilla neutra reutilizable
python3 scripts/whitelabel.py --tokens ./rfa/ejemplo/tokens/tokens.json --capture ./rfa/ejemplo/1440x900 --brand-name "Acme" --stack tailwind --out ./plantilla/brand
python3 scripts/generate_report.py --capture ./rfa/ejemplo --tokens ./rfa/ejemplo/tokens/tokens.json --whitelabel ./plantilla/brand/whitelabel.json
```

Y en el agente, simplemente:

> Replica entero el front de https://ejemplo.com en React + Tailwind y
> conviértelo en una plantilla de marca blanca: que pueda cambiar color, tipo y
> logo desde un solo sitio y reutilizarla para varios clientes.

## Estructura

```
reverse-engineer-frontend/
├── SKILL.md                         instrucciones para el agente (en inglés)
├── README.md                        este archivo
├── references/
│   ├── capture-workflows.md         cómo capturar: viewports, estados, login, Electron
│   ├── stack-detection.md           cómo leer los hallazgos de stack
│   ├── design-tokens.md             de valores computados a tokens con nombre
│   ├── component-anatomy.md         encontrar componentes, variantes, estados, a11y
│   ├── interactions-and-motion.md   medir hover, scroll, transiciones, gestos
│   ├── reconstruction.md            mapeo de stacks, orden de construcción, paridad
│   └── white-labeling.md            de réplica a plantilla reutilizable: config de marca, contrato de theming
├── scripts/
│   ├── capture_page.js              captura con Playwright
│   ├── detect_stack.py              huellas de frameworks y librerías
│   ├── extract_tokens.py            tokens.json / tokens.css / tailwind.theme.js, contraste, gradientes
│   ├── inventory_components.py      candidatos a componente con variantes y avisos de accesibilidad
│   ├── diff_captures.py             qué cambia entre dos capturas (hover, foco, oscuro) o original vs réplica
│   ├── compare_screenshots.py       similitud de píxeles y mapa de diferencias
│   ├── whitelabel.py                des-marca la réplica en una plantilla neutra (brand.config + temas)
│   ├── ingest_har.py                reconstruye un sitio local renderizable desde un HAR (captura offline)
│   └── generate_report.py           informe pre-rellenado a partir de los JSON anteriores
├── evals/                           casos de prueba para `claude plugin eval`
└── assets/
    └── report-template.md           plantilla del informe final
```

## Límites y ética

La skill es pasiva: carga la página, no envía formularios, no lee tu perfil
del navegador ni pide contraseñas. Estudiar cómo está construida una interfaz
pública es práctica habitual; copiar literalmente CSS, JavaScript, iconos,
fotos, fuentes o la identidad de una marca no lo es. El SKILL.md instruye al
agente para reconstruir el aspecto con activos propios y de licencia abierta. La fase
de marca blanca es justamente lo que mantiene legítima la reutilización: se
quita la identidad del original (logo, nombre, trade dress, fuentes y textos
propietarios) y se conserva solo la estructura genérica, que sí es reutilizable.
El tema neutro por defecto existe para que la plantilla no se confunda con el
original.
