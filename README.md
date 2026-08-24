# TecnoGym Escritorio

Sistema de gestión de gimnasio para Windows. Funciona sin internet y sin
servidor: toda la información vive en la propia computadora de recepción.

Es la reescritura en Python del sistema web en Laravel que está en la carpeta
superior de este repositorio.

## Qué hace

| Módulo | Atajo | Descripción |
|---|---|---|
| Bienvenida | `F1` | El socio teclea su código y el sistema le dice si puede pasar |
| Socios | `F2` | Alta, edición, foto, búsqueda y filtros por estado |
| Membresías | `F3` | Altas, renovaciones e historial de pagos |
| Visitas | `F4` | Entradas sueltas de quienes no son socios |
| Precios | `F5` | Tipos de membresía y sus duraciones |
| Corte de caja | `F6` | Ingresos del día, la semana o el mes por concepto |
| Productos | `F7` | Catálogo e inventario de la tienda |
| Ventas | `F8` | Punto de venta con carrito |
| Ajustes | `F9` | Datos del gimnasio y respaldos |

`Ctrl+R` recarga la pantalla actual.

## Dónde se guardan los datos

Todo queda en la carpeta de datos del usuario, nunca junto al programa (en
Windows `Program Files` es de solo lectura):

```
%LOCALAPPDATA%\TecnoGym\
├── gym.sqlite      la base de datos
├── photos\         fotos de los socios
├── backups\        respaldos automáticos
└── logs\           registro de eventos
```

Desinstalar el programa **no borra** esta carpeta.

## Respaldos

Se genera un respaldo automáticamente al cerrar el programa y una vez al día
mientras esté abierto, conservando los 30 más recientes (configurable). Se usa
`VACUUM INTO` de SQLite en lugar de copiar el archivo, porque con el modo WAL
activo una copia simple puede quedar incompleta.

Al restaurar un respaldo se guarda primero una copia del estado actual, de modo
que siempre hay camino de regreso.

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
cd desktop
uv sync --all-extras          # instalar dependencias
uv run python -m gym          # ejecutar la aplicación
uv run pytest                 # ejecutar las pruebas
```

Para trabajar sin tocar tus datos reales, apunta la aplicación a otra carpeta:

```bash
GYM_DATA_DIR=./.devdata uv run python -m gym
```

En un servidor sin pantalla, agrega `QT_QPA_PLATFORM=offscreen`.

### Estructura

```
gym/
├── domain/     reglas de negocio puras, sin base de datos ni interfaz
├── data/       modelos de SQLAlchemy y conexión
├── services/   casos de uso; la interfaz llama aquí, nunca a la base
└── ui/         pantallas y widgets de PySide6
migrations/     migraciones de Alembic
packaging/      recetas de compilación e instalador
```

### Decisiones que conviene conocer

- **El dinero se guarda en centavos enteros.** Sumar `0.1 + 0.2` en coma
  flotante no da `0.3`, y en una caja eso se acumula.
- **Los estados no se guardan, se calculan.** Que un socio esté activo depende
  de si alguno de sus periodos sigue vigente. Guardarlo en una columna obligaría
  a una tarea programada que puede fallar y dejar a un socio marcado como activo
  después de vencer. Se implementan como `hybrid_property`, que funciona igual
  en Python y dentro de las consultas SQL.
- **Los periodos vencen al final del día**, no a medianoche: el socio conserva
  el último día completo.
- **Sumar meses recorta al último día válido.** El 31 de enero más un mes vence
  el 28 de febrero, no el 3 de marzo.
- **Las ventas copian el nombre y el precio del producto.** Cambiar un precio
  mañana no debe alterar el ticket de hoy ni los cortes de caja ya emitidos.
- **El stock se vuelve a leer al cobrar**, dentro de la misma transacción. Entre
  que el cajero arma el carrito y cobra, el inventario pudo cambiar.

## Compilar para Windows

En una máquina Windows con Python y [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```bash
uv sync --all-extras
uv run python packaging/make_icon.py        # opcional, regenera el icono
uv run python packaging/build.py --installer
```

El ejecutable queda en `dist\TecnoGym.exe` y el instalador en
`dist\installer\`. El instalador no requiere permisos de administrador y ofrece
crear un acceso directo en el escritorio.

Para comprobar la compilación sin generar instalador, `uv run python
packaging/build.py` produce solo el ejecutable.
