"""Entorno de Alembic.

La URL de la base no se toma de alembic.ini sino del motor de la aplicacion,
para que las migraciones corran sobre la base real del usuario en
%LOCALAPPDATA% sin tener que configurar nada a mano.
"""

from logging.config import fileConfig

from alembic import context

from gym.data.database import create_db_engine
from gym.data.models import Base
from gym.data.types import EnumValue

config = context.config

# Cuando la aplicacion migra al arrancar nos pasa su propia conexion. En ese
# caso no se toca el registro: `fileConfig` reconstruye el logger raiz desde
# alembic.ini y dejaria la aplicacion sin su archivo de log.
_embedded = config.attributes.get("connection") is not None
if config.config_file_name is not None and not _embedded:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """En la base, EnumValue no es mas que texto; se escribe asi en la migracion.

    Evita que los scripts generados dependan de codigo de la aplicacion, que
    puede cambiar de nombre o desaparecer y romper migraciones ya publicadas.
    """
    if type_ == "type" and isinstance(obj, EnumValue):
        autogen_context.imports.add("import sqlalchemy as sa")
        return f"sa.String(length={obj.impl.length})"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)

    if connectable is not None:
        _run(connectable)
        return

    override = config.get_main_option("sqlalchemy.url", "")
    engine = create_db_engine(override.replace("sqlite:///", "") or None)
    with engine.connect() as connection:
        _run(connection)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite no soporta ALTER COLUMN; batch recrea la tabla al migrar.
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
