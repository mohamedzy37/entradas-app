"""Ajustes de esquema idempotentes para bases de datos ya creadas.

`Base.metadata.create_all` crea tablas que faltan pero no modifica las
existentes. Este modulo aplica los cambios de la version stateless:

- anade `users.token_version` (contador para invalidar JWT);
- elimina `refresh_tokens`: la sesion ya no se guarda en el backend;
- anade `users.google_sub` (login con Google) con indice unico.

En un proyecto mayor esto se haria con Alembic.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def apply_schema_updates(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(text("DROP TABLE IF EXISTS refresh_tokens"))
        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_google_sub "
                "ON users (google_sub)"
            )
        )
