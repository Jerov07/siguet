#!/usr/bin/env bash
# Lo ejecuta Render cada vez que se sube un cambio a GitHub.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input   # junta el CSS
python manage.py migrate --no-input          # tablas internas de Django (sesiones)
python manage.py crear_tablas                # las 13 tablas de SIGUET, solo si no existen
python manage.py cargar_datos_demo           # datos de prueba (no repite lo que ya existe)
python manage.py actualizar_bd               # columnas nuevas, nombres de restricciones y usuarios
