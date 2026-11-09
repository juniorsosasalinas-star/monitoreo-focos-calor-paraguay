                return geom['coordinates']
            raise RuntimeError('Geometría de Paraguay no reconocida')
    raise RuntimeError('No se encontró Paraguay en los límites geográficos')


def dentro_anillo(lon, lat, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][:2]
        xj, yj = anillo[j][:2]
        if (yi > lat) != (yj > lat):
            x_corte = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_corte:
                dentro = not dentro
        j = i
    return dentro


def dentro_paraguay(lon, lat, poligonos):
    for poligono in poligonos:
        if dentro_anillo(lon, lat, poligono[0]) and not any(
            dentro_anillo(lon, lat, hueco) for hueco in poligono[1:]
        ):
            return True
    return False


poligonos = obtener_poligonos()  # Si falla, no reemplazar datos anteriores.
detecciones = []
for fuente in FUENTES:
    url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{CLAVE}/{fuente}/{AREA}/1'
    contenido = descargar(url)
    lector = csv.DictReader(io.StringIO(contenido))
    if not lector.fieldnames or not {'latitude', 'longitude'}.issubset(lector.fieldnames):
        raise RuntimeError(f'Respuesta CSV no válida de {fuente}')
    cantidad = 0
    for fila in lector:
        try:
            lat = float(fila['latitude'])
            lon = float(fila['longitude'])
        except (TypeError, ValueError):
            continue
        if not dentro_paraguay(lon, lat, poligonos):
            continue
        detecciones.append({
            'lat': lat, 'lon': lon,
            'fecha': fila.get('acq_date', ''),
            'hora_utc': fila.get('acq_time', ''),
            'frp': fila.get('frp', ''),
            'confianza': fila.get('confidence', ''),
            'satelite': fila.get('satellite', ''),
            'fuente': fuente
        })
        cantidad += 1
    print(f'{fuente}: {cantidad} detecciones en Paraguay')

salida = {
    'actualizado_utc': datetime.now(timezone.utc).isoformat(),
    'area': 'Paraguay (filtro por frontera nacional)',
    'total_detecciones': len(detecciones),
    'detecciones': detecciones
}
Path('datos').mkdir(exist_ok=True)
temporal = Path('datos/focos.json.tmp')
temporal.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
temporal.replace('datos/focos.json')
print(f'Archivo generado: {len(detecciones)} detecciones dentro de Paraguay')
