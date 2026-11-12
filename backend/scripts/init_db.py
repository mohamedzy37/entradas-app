"""Inicializa la base de datos PostgreSQL y carga los datos iniciales.

Uso:
    .venv\\Scripts\\python.exe scripts\\init_db.py
    .venv\\Scripts\\python.exe scripts\\init_db.py --reset   (borra y recrea)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app import models  # noqa: E402,F401  (registra las tablas)
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.migrations import apply_schema_updates  # noqa: E402
from app.seed import run_seed  # noqa: E402


def ensure_database() -> None:
    url = make_url(settings.DATABASE_URL)
    database = url.database
    if not database:
        raise RuntimeError("DATABASE_URL no incluye nombre de base de datos")

    # En plataformas gestionadas (Render, RDS, Cloud SQL...) la base de datos ya
    # existe y el usuario no suele tener permiso para crear otras: si se puede
    # conectar directamente, no hay nada que hacer.
    try:
        psycopg2.connect(settings.DATABASE_URL.replace("+psycopg2", "")).close()
        print(f"Base de datos existente: {database}")
        return
    except psycopg2.OperationalError:
        pass

    connection = psycopg2.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname="postgres",
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
                )
                print(f"Base de datos creada: {database}")
            else:
                print(f"Base de datos existente: {database}")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa Entradas API")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra todas las tablas antes de crearlas (destructivo)",
    )
    args = parser.parse_args()

    ensure_database()

    if args.reset:
        print("Borrando tablas existentes...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    apply_schema_updates(engine)
    print("Esquema creado/verificado.")

    if os.environ.get("SEED_DEMO_DATA", "true").strip().lower() in {"0", "false", "no"}:
        print("SEED_DEMO_DATA=false: no se cargan datos ni usuarios de demostracion.")
        return

    with SessionLocal() as db:
        run_seed(db)

    print("\nListo. Usuarios de demostracion:")
    print("  CLIENT  ana.garcia@ejemplo.com / demo1234")
    print("  MANAGER gestor@entradas.com  / Gestor1234")
    print("  ADMIN   admin@entradas.com   / Admin1234")


if __name__ == "__main__":
    main()
