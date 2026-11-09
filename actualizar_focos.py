
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

# Área rectangular para consultar NASA FIRMS.
# Luego se filtra por el límite real de Paraguay.
AREA = "-62.7,-27.7,-54.2,-19.2"

FUENTES = [
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "MODIS_NRT"
]

URL_LIMITES = (
    "https://www.geoboundaries.org/api/current/"
    "gbOpen/PRY/ADM0/"
)


def descargar_json(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MonitorFocosParaguay/1.0"
        }
    )

    with urllib.request.urlopen(
        solicitud, timeout=90
    ) as respuesta:
        return json.load(respuesta)


def obtener_poligonos():
    print("Descargando límites de Paraguay...")

    metadatos = descargar_json(URL_LIMITES)

    url_geojson = (
        metadatos.get("simplifiedGeometryGeoJSON")
        or metadatos.get("gjDownloadURL")
    )

    if not url_geojson:
        raise RuntimeError(
            "No se encontró el GeoJSON de Paraguay"
        )

    geojson = descargar_json(url_geojson)

    if geojson.get("type") == "FeatureCollection":
        geometria = geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        geometria = geojson["geometry"]
    else:
        geometria = geojson

    tipo = geometria["type"]
    coordenadas = geometria["coordinates"]

    if tipo == "Polygon":
        poligonos = [coordenadas]
    elif tipo == "MultiPolygon":
        poligonos = coordenadas
    else:
        raise RuntimeError(
            "Geometría territorial no compatible"
        )

    if not poligonos:
        raise RuntimeError("Límite territorial vacío")

    print("Límites de Paraguay cargados")
    return poligonos


def punto_en_anillo(lon, lat, anillo):
    dentro = False
    anterior = anillo[-1]

    for actual in anillo:
        x1, y1 = anterior
        x2, y2 = actual

        if (y1 > lat) != (y2 > lat):
            interseccion = (
                (x2 - x1) * (lat - y1)
                / (y2 - y1) + x1
            )

            if lon < interseccion:
                dentro = not dentro

        anterior = actual

    return dentro


def dentro_de_paraguay(lat, lon, poligonos):
    for poligono in poligonos:
        if not punto_en_anillo(
            lon, lat, poligono[0]
        ):
            continue

        # Excluir huecos interiores del polígono.
        en_hueco = any(
            punto_en_anillo(lon, lat, hueco)
            for hueco in poligono[1:]
        )

        if not en_hueco:
            return True

    return False


poligonos_paraguay = obtener_poligonos()

detecciones = []
errores = []
descartadas = 0

for fuente in FUENTES:
    url = (
        "https://firms.modaps.eosdis.nasa.gov/api/"
        f"area/csv/{CLAVE}/{fuente}/{AREA}/1"
    )

    try:
        solicitud = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MonitorFocosParaguay/1.0"
            }
        )

        with urllib.request.urlopen(
            solicitud, timeout=60
        ) as respuesta:
            contenido = respuesta.read().decode(
                "utf-8-sig"
            )

        lector = csv.DictReader(
            io.StringIO(contenido)
        )

        if (
            not lector.fieldnames
            or "latitude" not in lector.fieldnames
            or "longitude" not in lector.fieldnames
        ):
            raise ValueError(
                "Respuesta CSV no válida"
            )

        cantidad_fuente = 0

        for fila in lector:
            try:
                lat = float(fila["latitude"])
                lon = float(fila["longitude"])
            except (ValueError, TypeError):
                continue

            if not dentro_de_paraguay(
                lat, lon, poligonos_paraguay
            ):
                descartadas += 1
                continue

            detecciones.append({
                "lat": lat,
                "lon": lon,
                "fecha": fila.get("acq_date", ""),
                "hora_utc": fila.get("acq_time", ""),
                "frp": fila.get("frp", ""),
                "confianza": fila.get(
                    "confidence", ""
                ),
                "satelite": fila.get(
                    "satellite", ""
                ),
                "fuente": fuente
            })

            cantidad_fuente += 1

        print(
            f"{fuente}: {cantidad_fuente} "
            "detecciones en Paraguay"
        )

    except Exception as error:
        errores.append(f"{fuente}: {error}")
        print(f"Error en {fuente}: {error}")

# No reemplazar datos anteriores si falla una consulta.
if errores:
    raise RuntimeError(
        "No se completaron todas las consultas: "
        + "; ".join(errores)
    )

salida = {
    "actualizado_utc": (
        datetime.now(timezone.utc).isoformat()
    ),
    "area": "República del Paraguay",
    "filtro_geografico": (
        "Límite nacional ADM0 - geoBoundaries"
    ),
    "total_detecciones": len(detecciones),
    "detecciones": detecciones
}

Path("datos").mkdir(exist_ok=True)

with open(
    "datos/focos.json",
    "w",
    encoding="utf-8"
) as archivo:
    json.dump(
        salida,
        archivo,
        ensure_ascii=False,
        indent=2
    )

print(
    f"Archivo generado: "
    f"{len(detecciones)} detecciones en Paraguay"
)

print(
    f"Detecciones fuera de Paraguay "
    f"descartadas: {descartadas}"
)
