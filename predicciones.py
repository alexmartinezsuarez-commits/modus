"""
predicciones.py - Registro y seguimiento de predicciones del modelo.








Permite registrar en una hoja de Google Sheets ("Predicciones") todas las
probabilidades que el modelo calcula para los partidos de una jornada, y
despues medir la calidad del modelo comparando cada prediccion con el
resultado real del partido.








Metricas que calcula (FASE 1, sin yield):
- Tasa de acierto: % de veces que el favorito del modelo gano.
- Calibracion: cuando el modelo dice 70%, ¿pasa ~70% de las veces?
- Brier score: medida agregada de la calidad de las predicciones.








Almacenamiento: Google Sheets via gspread + cuenta de servicio. Las
credenciales se leen de st.secrets["gcp_service_account_json"], que debe
contener el JSON de la cuenta de servicio entre triples comillas.








Depende de: config, stats_engine, data_loading.
"""








import json"""
predicciones.py - Registro y seguimiento de predicciones del modelo.

Permite registrar en una hoja de Google Sheets ("Predicciones") todas las
probabilidades que el modelo calcula para los partidos de una jornada, y
despues medir la calidad del modelo comparando cada prediccion con el
resultado real del partido.

Metricas que calcula (FASE 1, sin yield):
  - Tasa de acierto: % de veces que el favorito del modelo gano.
  - Calibracion: cuando el modelo dice 70%, ¿pasa ~70% de las veces?
  - Brier score: medida agregada de la calidad de las predicciones.

Almacenamiento: Google Sheets via gspread + cuenta de servicio. Las
credenciales se leen de st.secrets["gcp_service_account_json"], que debe
contener el JSON de la cuenta de servicio entre triples comillas.

Depende de: config, stats_engine, data_loading.
"""

import json
from datetime import datetime

import streamlit as st
import pandas as pd

from stats_engine import (
    prob_victoria, prob_180s, quien_hace_mas_180s,
    handicaps_legs, legs_totales,
)
from config import SHEET_ID_PREDICCIONES

# Las librerias de Google son opcionales: si no estan instaladas, el modulo
# sigue importando y el resto de la app funciona; solo el tracking queda
# desactivado con un aviso. Esto evita que un fallo de dependencias de
# Google tumbe toda la aplicacion.
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GOOGLE_DISPONIBLE = True
    _GOOGLE_ERROR = ""
except Exception as _e:
    gspread = None
    Credentials = None
    _GOOGLE_DISPONIBLE = False
    _GOOGLE_ERROR = str(_e)


# Nombre EXACTO de la hoja (pestaña) dentro del Google Sheet donde se
# guardan las predicciones. Debe coincidir con la pestaña creada a mano.
NOMBRE_HOJA_PREDICCIONES = "Predicciones"

# Cabecera de la hoja. El orden importa: las filas se escriben en este orden.
# 'ID' es la clave anti-duplicados (semana + partido + mercado + linea).
CABECERA = [
    "ID",
    "Semana",
    "Fecha registro",
    "Jornada",
    "Jugador 1",
    "Jugador 2",
    "Mercado",
    "Linea",
    "Probabilidad modelo",
    "Cuota justa",
    "Prediccion",
    "Resultado real",
    "Acierto",
]


# ─────────────────────────────────────────────────────────────────────────────
# CONEXION A GOOGLE SHEETS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _conectar_gsheets():
    """Abre una conexion autenticada a Google Sheets usando la cuenta de
    servicio guardada en los secrets de Streamlit.

    Devuelve una tupla (cliente, error):
      - Si todo va bien: (cliente_gspread, "").
      - Si algo falla:   (None, "mensaje explicando exactamente que fallo").

    Se cachea con cache_resource para no reautenticar en cada rerun.
    """
    # Si gspread / google-auth no estan instaladas, no se puede conectar.
    if not _GOOGLE_DISPONIBLE:
        return None, ("Las librerias de Google no estan instaladas. "
                      "Anade 'gspread' y 'google-auth' a requirements.txt.")

    # Permisos necesarios: leer/escribir Sheets y abrir el archivo via Drive.
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Paso 1: localizar el secreto
    try:
        if "gcp_service_account_json" in st.secrets:
            raw = st.secrets["gcp_service_account_json"]
            try:
                info = json.loads(raw)
            except Exception as e:
                return None, (
                    f"El secreto 'gcp_service_account_json' no es un JSON "
                    f"valido ({e}). Revisa que pegaste el JSON completo "
                    f"entre triples comillas, sin cortar nada."
                )
        elif "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
        else:
            return None, (
                "No se encontro el secreto de Google en Streamlit. Debe "
                "llamarse 'gcp_service_account_json' (o la tabla "
                "[gcp_service_account]). Revisa Manage app -> Settings -> "
                "Secrets."
            )
    except Exception as e:
        return None, f"Error leyendo los secrets de Streamlit: {e}"

    # Paso 2: comprobar que el JSON tiene los campos imprescindibles
    campos_necesarios = ("private_key", "client_email", "token_uri")
    faltan = [c for c in campos_necesarios if not info.get(c)]
    if faltan:
        return None, (
            f"Al secreto le faltan campos obligatorios: {', '.join(faltan)}. "
            f"Asegurate de pegar el JSON completo de la cuenta de servicio."
        )

    # Paso 3: crear credenciales y autorizar
    try:
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    except Exception as e:
        return None, (
            f"Las credenciales no son validas ({e}). Suele ser un problema "
            f"con el campo 'private_key': debe ir entre comillas y conservar "
            f"los \\n tal cual aparecen en el JSON."
        )

    try:
        cliente = gspread.authorize(creds)
        return cliente, ""
    except Exception as e:
        return None, f"Error autorizando con Google: {e}"


def tracking_disponible():
    """Indica si el tracking de predicciones esta operativo.

    Devuelve (disponible: bool, motivo: str). Si no esta disponible, 'motivo'
    explica por que (faltan librerias, falta el secreto, etc.) para mostrarlo
    al usuario sin romper la app.
    """
    if not _GOOGLE_DISPONIBLE:
        return False, (
            "Faltan las librerias de Google. Anade 'gspread' y "
            "'google-auth' al archivo requirements.txt del repositorio."
        )
    tiene_secreto = (
        "gcp_service_account_json" in st.secrets
        or "gcp_service_account" in st.secrets
    )
    if not tiene_secreto:
        return False, (
            "No se encontraron las credenciales de Google en los secrets "
            "de Streamlit. Revisa Manage app -> Settings -> Secrets."
        )
    return True, ""


def diagnostico_conexion(url_sheet):
    """Ejecuta una prueba completa de la conexion a Google Sheets y devuelve
    un texto explicando, paso a paso, que funciona y que no.

    Se usa en la interfaz para que el usuario sepa exactamente donde esta el
    problema sin tener que mirar los logs.
    """
    lineas = []

    # 1) Conexion / credenciales
    cliente, err = _conectar_gsheets()
    if cliente is None:
        lineas.append(f"❌ Credenciales: {err}")
        return "\n\n".join(lineas)
    lineas.append("✅ Credenciales de Google validas.")

    # 2) Abrir el libro por su ID (no por la URL publicada, que gspread no
    #    puede usar para escribir). El ID esta fijado en config.py.
    try:
        libro = cliente.open_by_key(SHEET_ID_PREDICCIONES)
        lineas.append(f"✅ Sheet abierto: '{libro.title}'.")
    except Exception as e:
        nombre_err = type(e).__name__
        if "PermissionError" in nombre_err or "403" in str(e):
            lineas.append(
                "❌ Sin permiso para abrir el Sheet. Comparte el Google "
                "Sheet (boton Compartir) con el email de la cuenta de "
                "servicio, con permiso de Editor."
            )
        elif "SpreadsheetNotFound" in nombre_err or "404" in str(e):
            lineas.append(
                "❌ No se encontro el Sheet. Comprueba que el ID en "
                "config.py (SHEET_ID_PREDICCIONES) es correcto y que el "
                "Sheet esta compartido con la cuenta de servicio."
            )
        else:
            lineas.append(f"❌ No se pudo abrir el Sheet: {nombre_err}: {e}")
        return "\n\n".join(lineas)

    # 3) Acceder/crear la pestana Predicciones
    try:
        libro.worksheet(NOMBRE_HOJA_PREDICCIONES)
        lineas.append(f"✅ Pestana '{NOMBRE_HOJA_PREDICCIONES}' encontrada.")
    except Exception:
        try:
            ws = libro.add_worksheet(title=NOMBRE_HOJA_PREDICCIONES,
                                     rows=2000, cols=len(CABECERA))
            ws.append_row(CABECERA)
            lineas.append(
                f"✅ Pestana '{NOMBRE_HOJA_PREDICCIONES}' creada (no existia)."
            )
        except Exception as e:
            lineas.append(
                f"❌ No se pudo crear la pestana '{NOMBRE_HOJA_PREDICCIONES}': "
                f"{e}. Probablemente la cuenta de servicio no tiene permiso "
                f"de Editor sobre el Sheet."
            )
            return "\n\n".join(lineas)

    lineas.append("✅ Todo correcto: el seguimiento puede escribir y leer.")
    return "\n\n".join(lineas)


def _abrir_hoja_predicciones(url_sheet=None):
    """Abre (o crea) la pestaña 'Predicciones' dentro del Google Sheet.

    El parametro url_sheet se mantiene por compatibilidad pero se ignora: el
    Sheet se abre siempre por su ID (SHEET_ID_PREDICCIONES de config.py),
    porque las URLs publicadas no sirven para escribir con gspread.

    Devuelve una tupla (worksheet, error):
      - Si todo va bien: (worksheet, "").
      - Si algo falla:   (None, "mensaje explicando que fallo").
    """
    cliente, err = _conectar_gsheets()
    if cliente is None:
        return None, err

    try:
        libro = cliente.open_by_key(SHEET_ID_PREDICCIONES)
    except Exception as e:
        nombre_err = type(e).__name__
        if "PermissionError" in nombre_err or "403" in str(e):
            return None, (
                "Sin permiso para abrir el Sheet. Comparte el Google Sheet "
                "con el email de la cuenta de servicio (permiso Editor)."
            )
        if "SpreadsheetNotFound" in nombre_err or "404" in str(e):
            return None, (
                "No se encontro el Sheet. Revisa SHEET_ID_PREDICCIONES en "
                "config.py y que el Sheet este compartido con la cuenta de "
                "servicio."
            )
        return None, f"No se pudo abrir el Sheet ({nombre_err}: {e})."

    try:
        hoja = libro.worksheet(NOMBRE_HOJA_PREDICCIONES)
    except Exception:
        # La pestaña no existe todavia: la creamos con la cabecera.
        try:
            hoja = libro.add_worksheet(
                title=NOMBRE_HOJA_PREDICCIONES,
                rows=2000,
                cols=len(CABECERA),
            )
            hoja.append_row(CABECERA)
        except Exception as e:
            return None, (
                f"No se pudo crear la pestana '{NOMBRE_HOJA_PREDICCIONES}' "
                f"({e}). Comprueba que la cuenta de servicio tiene permiso "
                f"de Editor sobre el Sheet."
            )

    # Garantizar que la cabecera existe (hoja recien creada a mano y vacia)
    try:
        primera_fila = hoja.row_values(1)
        if not primera_fila:
            hoja.append_row(CABECERA)
    except Exception:
        pass

    return hoja, ""


# ─────────────────────────────────────────────────────────────────────────────
# CALCULO DE TODOS LOS MERCADOS DE UN PARTIDO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_mercados_partido(j1_data, j2_data):
    """Calcula TODOS los mercados de un enfrentamiento.

    Parametros:
      j1_data, j2_data: dicts de jugador con claves 'PR', 'lam_180',
                        'lam_legs', 'nombre_original'.

    Devuelve una lista de dicts, uno por linea de mercado, cada uno con:
      {mercado, linea, prob, prediccion}
        - mercado:    categoria ("Ganador", "Handicap legs", ...)
        - linea:      la linea concreta ("J1 -1.5", "Mas de 5.5", ...)
        - prob:       probabilidad del modelo (0-1)
        - prediccion: texto legible de lo que predice el modelo

    Son ~22 lineas por partido (ganador, 8 handicaps, 2 totales, 7 de
    180s, y el H2H de 180s con 3 resultados).
    """
    pr1 = j1_data.get("PR", 0.0)
    pr2 = j2_data.get("PR", 0.0)
    lam1 = j1_data.get("lam_180", 0.0)
    lam2 = j2_data.get("lam_180", 0.0)

    filas = []

    # 1) Ganador del partido
    p1, p2 = prob_victoria(pr1, pr2)
    filas.append({
        "mercado": "Ganador",
        "linea": "Gana J1",
        "prob": p1,
        "prediccion": "Gana J1" if p1 >= 0.5 else "Gana J2",
    })
    filas.append({
        "mercado": "Ganador",
        "linea": "Gana J2",
        "prob": p2,
        "prediccion": "Gana J2" if p2 >= 0.5 else "Gana J1",
    })

    # 2) Handicaps de legs (8 lineas)
    handicaps = handicaps_legs(pr1, pr2)
    for linea, prob in handicaps.items():
        filas.append({
            "mercado": "Handicap legs",
            "linea": linea,
            "prob": prob,
            "prediccion": "Si" if prob >= 0.5 else "No",
        })

    # 3) Total de legs over/under (2 lineas)
    totales = legs_totales(pr1, pr2)
    for linea, prob in totales.items():
        filas.append({
            "mercado": "Total legs",
            "linea": linea,
            "prob": prob,
            "prediccion": "Si" if prob >= 0.5 else "No",
        })

    # 4) Mercados de 180s (7 lineas)
    mercados_180 = prob_180s(lam1, lam2, pr1, pr2)
    for linea, prob in mercados_180.items():
        filas.append({
            "mercado": "180s",
            "linea": linea,
            "prob": prob,
            "prediccion": "Si" if prob >= 0.5 else "No",
        })

    # 5) Quien hace mas 180s (H2H) - 3 resultados
    p_j1_180, p_emp_180, p_j2_180 = quien_hace_mas_180s(lam1, lam2, pr1, pr2)
    favorito_180 = max(
        [("J1 mas 180s", p_j1_180),
         ("Empate 180s", p_emp_180),
         ("J2 mas 180s", p_j2_180)],
        key=lambda x: x[1],
    )[0]
    for linea, prob in [("J1 mas 180s", p_j1_180),
                        ("Empate 180s", p_emp_180),
                        ("J2 mas 180s", p_j2_180)]:
        filas.append({
            "mercado": "Mas 180s (H2H)",
            "linea": linea,
            "prob": prob,
            "prediccion": favorito_180,
        })

    return filas


def _id_prediccion(semana, j1, j2, mercado, linea):
    """Construye el ID unico de una prediccion. Mismo partido + mercado +
    linea + semana -> mismo ID, de modo que registrar dos veces no duplica.
    """
    partes = [str(semana), str(j1), str(j2), str(mercado), str(linea)]
    return "|".join(p.strip().lower() for p in partes)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO DE PREDICCIONES (ESCRITURA EN LOTE)
# ─────────────────────────────────────────────────────────────────────────────

def registrar_predicciones(url_sheet, enfrentamientos, semana, jornada=""):
    """Registra en la hoja 'Predicciones' todos los mercados de todos los
    enfrentamientos de una jornada. Escribe en LOTE (una sola operacion).

    Parametros:
      url_sheet:        URL del Google Sheet.
      enfrentamientos:  lista de tuplas (j1_data, j2_data) con los dicts de
                        jugador de cada partido.
      semana:           identificador de la semana/jornada (string).
      jornada:          texto descriptivo opcional (ej. "Grupo A Lunes").

    Devuelve un dict con el resumen:
      {ok, nuevas, duplicadas, total, error}
        - ok:          True si la operacion se completo.
        - nuevas:      cuantas filas se escribieron.
        - duplicadas:  cuantas se omitieron por ya existir.
        - total:       total de lineas de mercado procesadas.
        - error:       mensaje de error si ok es False.
    """
    hoja, err = _abrir_hoja_predicciones(url_sheet)
    if hoja is None:
        return {"ok": False, "nuevas": 0, "duplicadas": 0, "total": 0,
                "error": err or "No se pudo conectar con la hoja de Google "
                                 "Sheets."}

    # IDs ya presentes en la hoja, para no duplicar
    try:
        registros = hoja.get_all_records()
        ids_existentes = {str(r.get("ID", "")).strip() for r in registros}
    except Exception:
        ids_existentes = set()

    fecha_reg = datetime.now().strftime("%Y-%m-%d %H:%M")
    filas_nuevas = []
    total = 0
    duplicadas = 0

    for j1_data, j2_data in enfrentamientos:
        nombre_j1 = j1_data.get("nombre_original", "?")
        nombre_j2 = j2_data.get("nombre_original", "?")
        mercados = calcular_mercados_partido(j1_data, j2_data)

        for m in mercados:
            total += 1
            id_pred = _id_prediccion(semana, nombre_j1, nombre_j2,
                                     m["mercado"], m["linea"])
            if id_pred in ids_existentes:
                duplicadas += 1
                continue
            ids_existentes.add(id_pred)

            prob = m["prob"]
            cuota = round(1.0 / prob, 2) if prob > 0 else ""
            filas_nuevas.append([
                id_pred,
                str(semana),
                fecha_reg,
                jornada,
                nombre_j1,
                nombre_j2,
                m["mercado"],
                m["linea"],
                round(prob, 4),
                cuota,
                m["prediccion"],
                "",   # Resultado real: se rellena cuando el partido termine
                "",   # Acierto: idem
            ])

    # Escritura en LOTE: una sola llamada a la API con todas las filas.
    if filas_nuevas:
        try:
            hoja.append_rows(filas_nuevas, value_input_option="USER_ENTERED")
        except Exception as e:
            return {"ok": False, "nuevas": 0, "duplicadas": duplicadas,
                    "total": total,
                    "error": f"Error escribiendo en la hoja: {e}"}

    return {"ok": True, "nuevas": len(filas_nuevas),
            "duplicadas": duplicadas, "total": total, "error": ""}


# ─────────────────────────────────────────────────────────────────────────────
# LECTURA Y METRICAS DE CALIBRACION
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def cargar_predicciones(url_sheet):
    """Lee todas las predicciones registradas en la hoja 'Predicciones'.

    Devuelve un DataFrame de pandas (vacio si no hay datos o falla la
    conexion). Cacheado 2 minutos para no releer en cada interaccion.
    """
    hoja, err = _abrir_hoja_predicciones(url_sheet)
    if hoja is None:
        return pd.DataFrame()
    try:
        registros = hoja.get_all_records()
        return pd.DataFrame(registros)
    except Exception:
        return pd.DataFrame()


def calcular_metricas(df):
    """Calcula las metricas de calidad del modelo a partir del DataFrame de
    predicciones. Solo usa las filas que tienen 'Acierto' relleno (es decir,
    partidos ya terminados y verificados).

    Devuelve un dict:
      {
        evaluadas:      nº de predicciones con resultado conocido,
        pendientes:     nº de predicciones aun sin resultado,
        aciertos:       nº de predicciones acertadas,
        tasa_acierto:   % de acierto (0-100),
        brier:          Brier score (0 = perfecto, 0.25 = azar, menor mejor),
        calibracion:    lista de tramos con {rango, n, prob_media, real},
      }
    """
    vacio = {"evaluadas": 0, "pendientes": 0, "aciertos": 0,
             "tasa_acierto": 0.0, "brier": None, "calibracion": []}
    if df is None or df.empty or "Acierto" not in df.columns:
        return vacio

    # Normalizar la columna Acierto: aceptamos 1/0, si/no, true/false, vacio
    def _norm_acierto(v):
        s = str(v).strip().lower()
        if s in ("1", "si", "sí", "true", "verdadero", "acierto", "ok"):
            return 1
        if s in ("0", "no", "false", "falso", "fallo"):
            return 0
        return None  # vacio / desconocido -> pendiente

    df = df.copy()
    df["_acierto"] = df["Acierto"].apply(_norm_acierto)

    pendientes = int(df["_acierto"].isna().sum())
    evaluadas_df = df[df["_acierto"].notna()].copy()
    n_eval = len(evaluadas_df)
    if n_eval == 0:
        vacio["pendientes"] = pendientes
        return vacio

    aciertos = int(evaluadas_df["_acierto"].sum())
    tasa = 100.0 * aciertos / n_eval

    # Probabilidad del modelo como numero (0-1)
    def _num(v):
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return None

    evaluadas_df["_prob"] = evaluadas_df["Probabilidad modelo"].apply(_num)

    # Brier score: media de (prob - resultado)^2 sobre las filas con prob valida
    con_prob = evaluadas_df[evaluadas_df["_prob"].notna()]
    brier = None
    if len(con_prob) > 0:
        difs = (con_prob["_prob"] - con_prob["_acierto"]) ** 2
        brier = float(difs.mean())

    # Calibracion: agrupar por tramos de probabilidad del 10%
    calibracion = []
    if len(con_prob) > 0:
        tramos = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
                  (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
        for lo, hi in tramos:
            grupo = con_prob[(con_prob["_prob"] >= lo) & (con_prob["_prob"] < hi)]
            if len(grupo) == 0:
                continue
            calibracion.append({
                "rango": f"{int(lo*100)}-{int(hi*100)}%",
                "n": len(grupo),
                "prob_media": float(grupo["_prob"].mean()) * 100,
                "real": float(grupo["_acierto"].mean()) * 100,
            })

    return {
        "evaluadas": n_eval,
        "pendientes": pendientes,
        "aciertos": aciertos,
        "tasa_acierto": tasa,
        "brier": brier,
        "calibracion": calibracion,
    
