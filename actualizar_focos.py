
import csv
import io
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CLAVE = os.environ.get("NASA_FIRMS_MAP_KEY")
if not CLAVE:
    raise RuntimeError("Falta el secreto NASA_FIRMS_MAP_KEY")

# Rectángulo aproximado que cubre Paraguay.
# En una etapa posterior filtraremos por límites nacionales.
AREA = "-62.7,-27.7,-54.2,-19.2"

FUENTES = [
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "MODIS_NRT"
]

detecciones = []
errores = []

for fuente in FUENTES:
    url = (
        "https://firms.modaps.eosdis.nasa.gov/api/"
        f"area/csv/{CLAVE}/{fuente}/{AREA}/1"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MonitorFocosParaguay/1.0"}
        )

        with urllib.request.urlopen(req, timeout=60) as respuesta:
            contenido = respuesta.read().decode("utf-8-sig")

        lector = csv.DictReader(io.StringIO(contenido))
        if not lector.fieldnames or "latitude" not in lector.fieldnames:
            raise ValueError("Respuesta CSV no válida")

        for fila in lector:
            try:
                lat = float(fila["latitude"])
                lon = float(fila["longitude"])
            except (ValueError, TypeError):
                continue

            detecciones.append({
                "lat": lat,
                "lon": lon,
                "fecha": fila.get("acq_date", ""),
                "hora_utc": fila.get("acq_time", ""),
                "frp": fila.get("frp", ""),
                "confianza": fila.get("confidence", ""),
                "satelite": fila.get("satellite", ""),
                "fuente": fuente
            })

        print(f"{fuente}: consulta correcta")

    except Exception as error:
        errores.append(f"{fuente}: {error}")
        print(f"Error en {fuente}: {error}")

# Evitar publicar una actualización vacía por fallas de API.
if errores:
    raise RuntimeError(
        "No se completaron todas las consultas: "
        + "; ".join(errores)
    )

salida = {
    "actualizado_utc": datetime.now(timezone.utc).isoformat(),
    "area": "Paraguay y zonas limítrofes (consulta preliminar)",
    "total_detecciones": len(detecciones),
    "detecciones": detecciones
}

Path("datos").mkdir(exist_ok=True)

with open("datos/focos.json", "w", encoding="utf-8") as archivo:
    json.dump(salida, archivo, ensure_ascii=False, indent=2)

print(f"Archivo generado: {len(detecciones)} detecciones")
