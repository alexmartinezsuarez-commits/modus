"""auto_registrar.py — Script de auto-registro de predicciones.

Disenado para ejecutarse desde GitHub Actions cada 15 minutos durante
horario de jornada. Detecta los proximos partidos NO empezados y los
registra en la pestana 'Predicciones', con datos lo mas frescos posibles.

REGLAS DE FUNCIONAMIENTO:
  1. Solo se ejecuta los dias mar/mie/vie/sab (lunes y jueves NO porque
     son inicio de grupo, datos poco fiables).
  2. Solo si hay una jornada activa por hora.
  3. Detecta partidos terminados: alguien con 4 legs en alguna fila.
  4. Detecta partidos en curso: hay algun dato en las filas pero ninguno
     llega a 4 -> NO se registra.
  5. Registra hasta 2 partidos "no empezados" (sin datos en ninguna fila).
  6. Si los 2 siguientes no empezados comparten algun jugador, solo
     se registra el primero.
  7. Sobrescribe los registros si ya existian, sin tocar resultado/acierto.
  8. Apunta en la pestana 'Log Auto Registro' lo que hizo cada vez.

USO:
  python auto_registrar.py

VARIABLES DE ENTORNO REQUERIDAS:
  GOOGLE_SERVICE_ACCOUNT_JSON  - JSON completo de la cuenta de servicio
                                 (el mismo que usa la app Streamlit).

EXIT CODES:
  0 - OK (registro o nada que hacer).
  1 - Error (configuracion, conexion, etc).
"""

from __future__ import annotations

import os
import sys
import json
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────────────────────────────────────

# Dias que SI registramos (weekday: lun=0, mar=1, mie=2, jue=3, vie=4, sab=5)
DIAS_REGISTRABLES = {1, 2, 4, 5}  # mar, mie, vie, sab

# Maximo de partidos a registrar por ejecucion
MAX_PARTIDOS_POR_RONDA = 2

# Fila de inicio de partidos en las pestanas de jornada (1-indexed)
FILA_INICIO_PARTIDOS = 7

# Maximo numero de partidos al dia (15 partidos = 30 filas)
NUM_PARTIDOS_POR_JORNADA = 15


# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZACION
# ─────────────────────────────────────────────────────────────────────────────

def configurar_credenciales():
    """Lee GOOGLE_SERVICE_ACCOUNT_JSON del entorno y lo deja accesible
    para que el resto del codigo (data_loading, predicciones) lo encuentre.

    Lo guarda en una variable global accesible desde st.secrets-like.
    """
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("ERROR: no esta definida GOOGLE_SERVICE_ACCOUNT_JSON",
              file=sys.stderr)
        sys.exit(1)
    try:
        creds_dict = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: GOOGLE_SERVICE_ACCOUNT_JSON no es JSON valido: {e}",
              file=sys.stderr)
        sys.exit(1)

    # Inyectar las credenciales en un st.secrets-like que data_loading
    # espera. Stub minimo de streamlit suficiente para que importe.
    import types
    st_stub = types.ModuleType("streamlit")
    st_stub.secrets = {"gcp_service_account": creds_dict}

    # Cache decoradores sin efecto
    class _Cache:
        def __call__(self, *args, **kwargs):
            if len(args) == 1 and callable(args[0]) and not kwargs:
                return args[0]
            def decorador(fn):
                return fn
            return decorador
        def clear(self):
            pass

    st_stub.cache_data = _Cache()
    st_stub.cache_resource = _Cache()

    class _SS(dict):
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
        def __setattr__(self, k, v): self[k] = v
        def get(self, k, d=None): return dict.get(self, k, d)
    st_stub.session_state = _SS()

    # Funciones de UI que data_loading podria invocar — todas no-op
    def _noop(*a, **k):
        return None
    for fn in ("warning", "error", "info", "success", "write", "markdown",
                "caption", "title", "subheader", "spinner"):
        setattr(st_stub, fn, _noop)

    sys.modules["streamlit"] = st_stub


# ─────────────────────────────────────────────────────────────────────────────
# DETECCION DE PARTIDOS
# ─────────────────────────────────────────────────────────────────────────────

def _celda_tiene_dato(valor):
    """True si la celda tiene algun valor (no es ni None ni vacio)."""
    if valor is None:
        return False
    s = str(valor).strip()
    return s != "" and s != "0,00%" and s != "0%"


def _legs_de_celda(valor):
    """Convierte el contenido de una celda de legs a int. 0 si vacia."""
    if valor is None:
        return 0
    s = str(valor).strip().replace(",", ".")
    if not s:
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def clasificar_partidos(filas_partidos):
    """Recibe lista de filas crudas (cada fila = lista de celdas A..E) y
    devuelve, por cada partido (de 2 filas consecutivas), su estado.

    Devuelve lista de dicts:
      [{idx: 0, j1, j2, estado: 'no_empezado'|'en_curso'|'terminado'},
       {idx: 1, j1, j2, estado: ...},
       ...]
    """
    partidos = []
    for i in range(0, len(filas_partidos), 2):
        if i + 1 >= len(filas_partidos):
            break  # fila impar suelta, ignorar
        fila_j1 = filas_partidos[i]
        fila_j2 = filas_partidos[i + 1]

        j1 = (fila_j1[0] if len(fila_j1) > 0 else "").strip()
        j2 = (fila_j2[0] if len(fila_j2) > 0 else "").strip()

        if not j1 or not j2:
            # Fila sin nombre -> ya no hay mas partidos validos
            break

        # Celdas de stats: columnas B-E (indices 1-4)
        celdas_j1 = fila_j1[1:5] if len(fila_j1) >= 5 else fila_j1[1:]
        celdas_j2 = fila_j2[1:5] if len(fila_j2) >= 5 else fila_j2[1:]

        legs_j1 = _legs_de_celda(fila_j1[1] if len(fila_j1) > 1 else "")
        legs_j2 = _legs_de_celda(fila_j2[1] if len(fila_j2) > 1 else "")

        terminado = (legs_j1 >= 4 or legs_j2 >= 4)
        algun_dato = (any(_celda_tiene_dato(c) for c in celdas_j1) or
                       any(_celda_tiene_dato(c) for c in celdas_j2))

        if terminado:
            estado = "terminado"
        elif algun_dato:
            estado = "en_curso"
        else:
            estado = "no_empezado"

        partidos.append({
            "idx": i // 2,
            "j1": j1,
            "j2": j2,
            "estado": estado,
            "legs_j1": legs_j1,
            "legs_j2": legs_j2,
        })
    return partidos


def seleccionar_partidos_a_registrar(partidos):
    """Aplica las reglas: hasta MAX no empezados consecutivos, con la
    restriccion de no solapar jugadores entre los seleccionados.

    Devuelve (lista_a_registrar, lista_descartados_con_motivo).
    """
    a_registrar = []
    descartados = []

    # Recorrer en orden y coger los primeros 'no_empezado'
    candidatos = [p for p in partidos if p["estado"] == "no_empezado"]
    if not candidatos:
        return [], []

    primer = candidatos[0]
    a_registrar.append(primer)
    jugadores_ocupados = {primer["j1"].lower(), primer["j2"].lower()}

    for cand in candidatos[1:]:
        if len(a_registrar) >= MAX_PARTIDOS_POR_RONDA:
            break
        if (cand["j1"].lower() in jugadores_ocupados or
                cand["j2"].lower() in jugadores_ocupados):
            descartados.append(
                f"{cand['j1']} vs {cand['j2']} "
                f"(solapa con partido anterior pendiente)"
            )
            # No avanzamos a posteriores, paramos: hay que esperar a que
            # se juegue el conflicto antes de registrar futuros.
            break
        a_registrar.append(cand)
        jugadores_ocupados.update({cand["j1"].lower(), cand["j2"].lower()})

    return a_registrar, descartados


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    configurar_credenciales()

    # IMPORTANTE: imports DESPUES de configurar_credenciales para que
    # streamlit-stub y st.secrets esten ya listos antes de cargar data_loading.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Ajustar Madrid time
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    wd = ahora.weekday()
    print(f"[auto-registrar] {ahora.isoformat()} (wd={wd})")

    # ── Filtro de dias ────────────────────────────────────────────────────
    if wd not in DIAS_REGISTRABLES:
        print(f"  -> hoy no toca registrar (dia {wd})")
        sys.exit(0)

    # ── Importar modulos de la app ────────────────────────────────────────
    try:
        from data_loading import (
            detectar_jornada_de_hoy, cargar_forma_reciente,
        )
        from predicciones import (
            registrar_predicciones, escribir_log_auto,
        )
    except Exception as e:
        print(f"ERROR importando modulos: {e}")
        traceback.print_exc()
        sys.exit(1)

    # ── Detectar jornada activa ──────────────────────────────────────────
    jornada = detectar_jornada_de_hoy()
    if not jornada:
        print("  -> no hay jornada activa por hora")
        escribir_log_auto(
            jornada="", partidos_registrados=[], partidos_saltados=[],
            estado="NADA", detalles="sin jornada activa por hora",
        )
        sys.exit(0)
    print(f"  -> jornada activa: {jornada}")

    # ── Leer las filas de partidos de la pestana via CSV publico ────────
    try:
        from config import URLS
        import pandas as pd
        import io
        import urllib.request
    except Exception as e:
        print(f"ERROR importando dependencias adicionales: {e}")
        sys.exit(1)

    url_csv = URLS.get(jornada)
    if not url_csv:
        msg = f"No hay URL CSV para jornada '{jornada}'"
        print(f"  -> {msg}")
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=[], estado="ERROR",
                           detalles=msg)
        sys.exit(1)

    try:
        with urllib.request.urlopen(url_csv, timeout=20) as resp:
            csv_text = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        msg = f"Error descargando CSV: {e}"
        print(f"  -> {msg}")
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=[], estado="ERROR",
                           detalles=msg)
        sys.exit(1)

    # Parsear el CSV en lista de listas (lineas crudas)
    import csv as csv_mod
    lineas = list(csv_mod.reader(io.StringIO(csv_text)))
    # Las filas de partidos: desde FILA_INICIO_PARTIDOS (1-indexed) hasta
    # FILA_INICIO_PARTIDOS + 30 (15 partidos = 30 filas). Como Python es
    # 0-indexed, restamos 1.
    idx_inicio = FILA_INICIO_PARTIDOS - 1
    idx_fin = idx_inicio + (NUM_PARTIDOS_POR_JORNADA * 2)
    filas_partidos = lineas[idx_inicio:idx_fin]

    if not filas_partidos:
        msg = "La pestana no tiene filas de partidos"
        print(f"  -> {msg}")
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=[], estado="NADA",
                           detalles=msg)
        sys.exit(0)

    # ── Clasificar partidos por estado ────────────────────────────────────
    partidos = clasificar_partidos(filas_partidos)
    print(f"  -> {len(partidos)} partidos detectados:")
    for p in partidos:
        print(f"     [{p['idx']:>2}] {p['j1']} vs {p['j2']} "
              f"({p['legs_j1']}-{p['legs_j2']}) [{p['estado']}]")

    # ── Seleccionar cuales registrar ─────────────────────────────────────
    a_registrar, descartados = seleccionar_partidos_a_registrar(partidos)

    if not a_registrar:
        print("  -> no hay partidos pendientes que registrar")
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=descartados, estado="NADA",
                           detalles="sin partidos no-empezados pendientes")
        sys.exit(0)

    # ── Cargar Forma reciente ─────────────────────────────────────────────
    try:
        forma_dict = cargar_forma_reciente()
    except Exception as e:
        msg = f"Error cargando Forma reciente: {e}"
        print(f"  -> {msg}")
        traceback.print_exc()
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=[], estado="ERROR",
                           detalles=msg)
        sys.exit(1)

    if not forma_dict:
        msg = "Forma reciente vacia"
        print(f"  -> {msg}")
        escribir_log_auto(jornada=jornada, partidos_registrados=[],
                           partidos_saltados=[], estado="ERROR",
                           detalles=msg)
        sys.exit(1)

    # ── Registrar cada partido seleccionado ──────────────────────────────
    registrados_ok = []
    errores = []
    semana = ahora.strftime("Semana %Y-%m-%d")

    def _buscar_jugador(nombre):
        nl = nombre.strip().lower()
        if nl in forma_dict:
            return forma_dict[nl]
        # match parcial por apellido/sufijo
        for k, v in forma_dict.items():
            if nl in k or k in nl:
                return v
        return None

    for p in a_registrar:
        j1_data = _buscar_jugador(p["j1"])
        j2_data = _buscar_jugador(p["j2"])
        if not j1_data or not j2_data:
            falta = []
            if not j1_data: falta.append(p["j1"])
            if not j2_data: falta.append(p["j2"])
            errores.append(
                f"{p['j1']} vs {p['j2']} (sin stats: {', '.join(falta)})"
            )
            continue
        try:
            res = registrar_predicciones(
                "", [(j1_data, j2_data)], semana, jornada
            )
            if res.get("ok"):
                registrados_ok.append(f"{p['j1']} vs {p['j2']}")
            else:
                errores.append(
                    f"{p['j1']} vs {p['j2']} "
                    f"(error: {res.get('error', 'desconocido')})"
                )
        except Exception as e:
            errores.append(f"{p['j1']} vs {p['j2']} (excepcion: {e})")
            traceback.print_exc()

    # ── Log ──────────────────────────────────────────────────────────────
    if registrados_ok and not errores:
        estado = "OK"
    elif registrados_ok and errores:
        estado = "PARCIAL"
    else:
        estado = "ERROR"
    detalles = f"{len(registrados_ok)} registrados, {len(errores)} errores"
    if errores:
        detalles += " | Errores: " + " ; ".join(errores)

    escribir_log_auto(jornada=jornada, partidos_registrados=registrados_ok,
                       partidos_saltados=descartados + errores,
                       estado=estado, detalles=detalles)
    print(f"  -> {estado}: {detalles}")


if __name__ == "__main__":
    main()
