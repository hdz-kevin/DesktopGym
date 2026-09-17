# Contexto para el agente

Sistema de gestión de gimnasio de escritorio, en Python + PySide6, pensado para
correr en la PC de recepción de un gimnasio real: sin internet, sin servidor y
sin que nadie tenga que abrir una terminal.

Es la reescritura de un sistema web en Laravel que vive en la carpeta superior
de este repositorio. **Esa carpeta no es visible si abriste `desktop/` como raíz,
y no la necesitas**: todo lo que importaba del sistema viejo ya está trasladado
aquí, y este código es la fuente de verdad. No intentes consultar el proyecto
Laravel ni replicar sus decisiones; varias se corrigieron a propósito (ver
"Invariantes").

`README.md` describe el producto para una persona. Este archivo describe el
código para quien lo va a modificar.

## Comandos

```bash
uv sync --all-extras                  # instalar dependencias (requiere uv)
uv run python -m gym                  # ejecutar la aplicación
uv run python -m gym.seed seed        # llena la base del usuario con datos de prueba
uv run python -m gym.seed reset       # deja solo el catalogo inicial de precios
uv run pytest                         # 383 pruebas, ~3 s
uv run ruff check . && uv run ruff format .
uv run python packaging/build.py      # compilar el ejecutable a dist/
uv run python packaging/screenshots.py screenshots   # render de cada pantalla a PNG
```

Para no tocar los datos reales al probar algo, antepón `GYM_DATA_DIR=./.demo`.
`python -m gym.seed` usa la base del usuario (`data_dir()`), la misma que la
aplicación; `GYM_DATA_DIR` también la desvía. En un entorno sin pantalla (CI,
contenedor), agrega `QT_QPA_PLATFORM=offscreen`; sin eso Qt aborta al no
encontrar servidor gráfico. Las pruebas ya se aíslan solas: la fixture `app_db`
redirige `GYM_DATA_DIR` a un `tmp_path`.

## Arquitectura

Cuatro capas con una regla de dependencia que sí se respeta y conviene mantener:

```
gym/domain/     reglas puras: fechas, dinero, enums. No importa nada de Qt ni de SQLAlchemy.
gym/data/       modelos SQLAlchemy, motor SQLite, migraciones. Importa domain.
gym/services/   casos de uso. Único lugar que abre sesiones de base de datos.
gym/ui/         pantallas PySide6. Llama a services; nunca consulta la base.
```

La interfaz sí importa modelos de `gym.data.models`, pero solo para leer objetos
que un servicio ya cargó. **Si en `gym/ui/` aparece un `session_scope()` o un
`select()`, la lógica está en el lugar equivocado**: muévela a un servicio.

Como los servicios cierran la sesión antes de devolver, cada uno precarga con
`selectinload` lo que la interfaz va a leer (ver `_eager()` en `members.py`).
Si agregas un acceso a relación en una pantalla y salta `DetachedInstanceError`,
la solución es ampliar ese `_eager()`, no abrir una sesión desde la interfaz.

El motor es global y se inicializa una sola vez en el arranque
(`init_engine()`); `session_scope()` lo resuelve. SQLite va en modo WAL con
llaves foráneas activas, configurado por conexión en `data/database.py`.

## Invariantes del dominio

Estas decisiones son deliberadas y varias corrigen errores del sistema Laravel
original. Romperlas produce errores de dinero o de vigencias, que es justo lo
que un gimnasio nota:

- **El dinero se guarda siempre en centavos enteros** (`price_cents`,
  `total_cents`, `subtotal_cents`). Nunca `float`, nunca `Decimal` en la base.
  Convierte con `gym.domain.money` (`to_cents`, `to_pesos`, `format_money`).
- **Los estados no se guardan, se calculan.** `Member.status` es un
  `hybrid_property`: activo si algun pago tiene `end_date` vigente, si no
  vencido (tambien quien nunca pago). La misma regla corre en Python y dentro
  de un `WHERE` de SQL. No agregues una columna `status`; el sistema viejo lo
  hizo y dependia de una tarea programada que al fallar dejaba socios vencidos
  marcados como activos. Un `Payment` no tiene estado: ya se cobro.
- **El socio tiene categoria** (`plan_category_id`). Los planes del cobro son
  los de esa categoria. Cambiarla no reescribe pagos viejos: el historial
  conserva el `plan_id` cobrado.
- **Los pagos vencen al final del día.** El socio conserva el último día
  completo. Usa los helpers de `gym.domain.dates`, no `datetime` a pelo.
- **Sumar meses recorta al último día válido**: 31 de enero + 1 mes vence el 28
  de febrero, no el 3 de marzo. Está en `dates.add_months`.
- **Las líneas de venta copian nombre y precio del producto** al momento de
  vender (`product_name`, `product_price_cents`). Cambiar un precio hoy no debe
  alterar el ticket ni el corte de caja de ayer.
- **El stock se relee dentro de la transacción de cobro**, no se confía en el
  valor que se leyó al armar el carrito (`services/sales.py: checkout`).
- **Todo producto lleva stock.** Cero es agotado, no ausencia de control.

## Convenciones

- Idioma: código y nombres en inglés; comentarios y docstrings en español **sin
  acentos** (evita problemas de codificación en Windows); textos de interfaz en
  español **con acentos** y redactados para el recepcionista, no para un
  programador.
- Los comentarios explican por qué, no qué. Si un comentario describe lo que la
  línea siguiente hace, sobra.
- `from __future__ import annotations` al inicio de cada módulo.
- Los servicios validan y lanzan `ValidationError`, `NotFoundError` o
  `InsufficientStockError` (`services/errors.py`) con el mensaje ya redactado
  para mostrarse tal cual; la interfaz solo lo despliega en un toast.
- Ruff con línea de 100. Las reglas ignoradas en `pyproject.toml` tienen su
  justificación escrita ahí; léela antes de "arreglar" una.

## Recetas

**Agregar una pantalla**: crea la clase en `gym/ui/pages/` heredando de `Page`
(`ui/main_window.py`), implementa `refresh()` —se llama cada vez que la pantalla
se muestra, para que no queden datos viejos—, añade su `NavItem` a `NAV_ITEMS`
con su tecla de función y regístrala en `build_window()` de `gym/__main__.py`.

**Cambiar el esquema**: edita `gym/data/models.py` y genera la migración con
`uv run alembic revision --autogenerate -m "descripcion"`. La aplicación corre
`alembic upgrade head` sola al arrancar (`data/schema.py: prepare_database`),
porque el usuario final no tiene terminal. Revisa siempre la migración generada:
`migrations/env.py` traduce el tipo `EnumValue` a `sa.String` para que los
archivos de migración no importen código de `gym`.

**Agregar un caso de uso**: función a nivel de módulo en `gym/services/`, que
abra su propio `session_scope()` y devuelva ids o modelos ya precargados. No se
usan clases de servicio.

## Trampas de Qt ya encontradas

- `QComboBox.currentData()` devuelve el valor crudo, no el `Enum`. Reconstrúyelo
  (`MemberGender(combo.currentData())`).
- Limpiar un campo por código dispara `textChanged`. Si eso reinicia la pantalla
  (pasó en el kiosco), bloquea señales con `blockSignals` mientras lo limpias.
- Los toasts se reposicionan al cambiar el tamaño de la ventana; se comprueba
  `shiboken6.isValid()` antes de tocar la ventana porque Qt puede haberla
  destruido ya.
- Las pruebas de fechas deben construirse relativas a `date.today()`. Fijar
  fechas absolutas funciona hoy y falla en unos meses.

## Estado y límites

Funciona de punta a punta: los diez módulos están implementados y probados, y
el ejecutable arranca en una máquina sin Python. Los nueve módulos están
implementados y probados. Lo que **no** tiene, por
decisión de alcance: no hay usuarios ni inicio de sesión (la PC de recepción es
de una sola persona), no hay sincronización entre computadoras, no hay impresión
de tickets y el instalador solo se puede generar desde Windows, porque Inno
Setup no corre en otro sistema.
