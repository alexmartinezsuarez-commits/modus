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

    # 1) Ganador del partido -> UNA sola linea.
    #    "Gana J1" y "Gana J2" son la misma apuesta opuesta; registrar las dos
    #    contaria cada resultado dos veces. Guardamos una linea con el
    #    favorito del modelo.
    p1, p2 = prob_victoria(pr1, pr2)
    if p1 >= p2:
        favorito_ganador = "Gana J1"
        prob_ganador = p1
    else:
        favorito_ganador = "Gana J2"
        prob_ganador = p2
    filas.append({
        "mercado": "Ganador",
        "linea": "Ganador del partido",
        "prob": prob_ganador,
        "prediccion": favorito_ganador,
    })

    # 2) Handicaps de legs (8 lineas).
    #    Aqui SI son 8 apuestas distintas (J1 -1.5, J1 -2.5, J2 +1.5...),
    #    no redundantes: cada hándicap es un mercado propio.
    handicaps = handicaps_legs(pr1, pr2)
    for linea, prob in handicaps.items():
        filas.append({
            "mercado": "Handicap legs",
            "linea": linea,
            "prob": prob,
            "prediccion": "Si" if prob >= 0.5 else "No",
        })

    # 3) Total de legs -> UNA sola linea.
    #    "Más de 5.5" y "Menos de 5.5" son opuestos: una sola apuesta.
    #    Guardamos el lado que el modelo considera mas probable.
    totales = legs_totales(pr1, pr2)
    p_over = totales.get("Más de 5.5", 0.5)
    p_under = totales.get("Menos de 5.5", 0.5)
    if p_over >= p_under:
        linea_total, prob_total, pred_total = "Más de 5.5", p_over, "Más de 5.5"
    else:
        linea_total, prob_total, pred_total = "Menos de 5.5", p_under, "Menos de 5.5"
    filas.append({
        "mercado": "Total legs",
        "linea": "Total de legs",
        "prob": prob_total,
        "prediccion": pred_total,
    })

    # 4) Mercados de 180s (7 lineas).
    #    Son 7 apuestas distintas (J1 +0.5, Ambos +2.5...), no redundantes.
    mercados_180 = prob_180s(lam1, lam2, pr1, pr2)
    for linea, prob in mercados_180.items():
        filas.append({
            "mercado": "180s",
            "linea": linea,
            "prob": prob,
            "prediccion": "Si" if prob >= 0.5 else "No",
        })

    # 5) Quien hace mas 180s (H2H) -> UNA sola linea.
    #    Es un mercado de 3 vias (J1 / Empate / J2). Guardamos una unica
    #    linea con el favorito del modelo, no las 3.
    p_j1_180, p_emp_180, p_j2_180 = quien_hace_mas_180s(lam1, lam2, pr1, pr2)
    opciones_180 = [("J1 mas 180s", p_j1_180),
                    ("Empate 180s", p_emp_180),
                    ("J2 mas 180s", p_j2_180)]
    favorito_180, prob_fav_180 = max(opciones_180, key=lambda x: x[1])
    filas.append({
        "mercado": "Mas 180s (H2H)",
        "linea": "Quien hace mas 180s",
        "prob": prob_fav_180,
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
            hoja.append_rows(filas_nuevas, value_input_option="RAW")
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
    vacio = {"evaluadas": 0, "pendientes": 0, "no_jugado": 0, "aciertos": 0,
             "tasa_acierto": 0.0, "brier": None, "calibracion": [],
             "por_mercado": []}
    if df is None or df.empty or "Acierto" not in df.columns:
        return vacio

    # Normalizar la columna Acierto. Tres estados posibles:
    #   1 / 0   -> prediccion verificada (acierto / fallo)
    #   "no jugado" -> el enfrentamiento no se disputo (categoria aparte)
    #   vacio   -> aun pendiente de verificar
    def _norm_acierto(v):
        s = str(v).strip().lower()
        if s in ("1", "si", "sí", "true", "verdadero", "acierto", "ok"):
            return 1
        if s in ("0", "false", "falso", "fallo"):
            return 0
        if s in ("no jugado", "no_jugado", "nojugado", "n/a", "na"):
            return "no_jugado"
        if s == "no":
            return 0
        return None  # vacio / desconocido -> pendiente

    df = df.copy()
    df["_acierto"] = df["Acierto"].apply(_norm_acierto)

    # Separar las tres categorias
    no_jugado = int((df["_acierto"] == "no_jugado").sum())
    pendientes = int(df["_acierto"].isna().sum())
    # Solo 1 y 0 cuentan como evaluadas
    evaluadas_df = df[df["_acierto"].isin([0, 1])].copy()
    n_eval = len(evaluadas_df)
    if n_eval == 0:
        vacio["pendientes"] = pendientes
        vacio["no_jugado"] = no_jugado
        return vacio

    # En evaluadas_df, _acierto solo tiene 0 y 1: lo forzamos a entero para
    # que los calculos numericos (suma, media, Brier) funcionen sin mezclas.
    evaluadas_df["_acierto"] = evaluadas_df["_acierto"].astype(int)

    aciertos = int(evaluadas_df["_acierto"].sum())
    tasa = 100.0 * aciertos / n_eval

    # Probabilidad del modelo como numero entre 0 y 1.
    # Una probabilidad SOLO puede estar entre 0 y 1. Si un valor llega
    # corrupto (mal formato de celda, separador de miles, etc.) y queda
    # fuera de ese rango, lo descartamos: incluirlo dispararia el Brier
    # score a valores absurdos. Tambien intentamos rescatar valores que
    # vengan como porcentaje (ej. 58.33 -> 0.5833).
    def _num(v):
        try:
            x = float(str(v).strip().replace(",", "."))
        except Exception:
            return None
        # Caso normal: ya esta entre 0 y 1
        if 0.0 <= x <= 1.0:
            return x
        # Caso porcentaje: entre 1 y 100 -> dividir por 100
        if 1.0 < x <= 100.0:
            return x / 100.0
        # Cualquier otro valor es corrupto: se descarta
        return None

    evaluadas_df["_prob"] = evaluadas_df["Probabilidad modelo"].apply(_num)

    # Brier score: media de (prob - resultado)^2 sobre las filas con prob
    # valida (0-1). Como _num ya garantiza el rango, el Brier siempre saldra
    # entre 0 y 1. Por seguridad extra, lo recortamos a [0, 1].
    con_prob = evaluadas_df[evaluadas_df["_prob"].notna()]
    brier = None
    if len(con_prob) > 0:
        difs = (con_prob["_prob"] - con_prob["_acierto"]) ** 2
        brier = float(difs.mean())
        # Salvaguarda: el Brier nunca puede salir de [0, 1]
        if brier < 0.0:
            brier = 0.0
        elif brier > 1.0:
            brier = 1.0

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

    # Desglose por tipo de mercado: para cada mercado (Ganador, Handicap
    # legs, Total legs, 180s, Mas 180s (H2H)), cuantas predicciones se
    # verificaron, cuantas se acertaron y la tasa de acierto. Esto permite
    # ver en que mercados el modelo funciona bien y en cuales no.
    por_mercado = []
    if "Mercado" in evaluadas_df.columns and n_eval > 0:
        for mercado, grupo in evaluadas_df.groupby("Mercado"):
            n_m = len(grupo)
            ac_m = int(grupo["_acierto"].sum())
            por_mercado.append({
                "mercado": str(mercado),
                "verificadas": n_m,
                "aciertos": ac_m,
                "tasa": 100.0 * ac_m / n_m if n_m > 0 else 0.0,
            })
        # Ordenar de mejor a peor tasa de acierto
        por_mercado.sort(key=lambda x: x["tasa"], reverse=True)

    return {
        "evaluadas": n_eval,
        "pendientes": pendientes,
        "no_jugado": no_jugado,
        "aciertos": aciertos,
        "tasa_acierto": tasa,
        "brier": brier,
        "calibracion": calibracion,
        "por_mercado": por_mercado,
    }


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICACION AUTOMATICA DE RESULTADOS (FASE 2)
# ─────────────────────────────────────────────────────────────────────────────

# Pestanas de jornada donde buscar los resultados reales de los partidos.
JORNADAS_VERIFICABLES = [
    "Grupo A Lunes", "Grupo A Martes", "Grupo A Miércoles",
    "Grupo C Jueves", "Grupo B Jueves",
    "Grupo C Viernes", "Grupo B Viernes",
    "Final Sábado",
]


def listar_partidos_registrados(df):
    """Agrupa las predicciones por partido y devuelve una lista resumida.

    Cada partido genera ~18 filas en la hoja (una por mercado). Esta
    funcion las agrupa para mostrar UNA fila por enfrentamiento.

    Recibe el DataFrame de cargar_predicciones. Devuelve una lista de dicts:
      {jornada, partido, semana, mercados, estado}
    donde 'estado' es uno de: "Verificado", "Pendiente", "No jugado",
    "Mixto" (si las filas del partido no coinciden todas en estado).

    La lista se ordena por jornada y luego por partido.
    """
    if df is None or df.empty:
        return []

    # Columnas necesarias
    cols = df.columns
    if "Jugador 1" not in cols or "Jugador 2" not in cols:
        return []

    def _estado_fila(v):
        s = str(v).strip().lower()
        if s in ("1", "0", "si", "sí", "no", "true", "false",
                 "verdadero", "falso", "acierto", "fallo", "ok"):
            return "verificado"
        if s in ("no jugado", "no_jugado", "nojugado", "n/a", "na"):
            return "no_jugado"
        return "pendiente"  # vacio

    partidos = {}
    for _, fila in df.iterrows():
        j1 = str(fila.get("Jugador 1", "")).strip()
        j2 = str(fila.get("Jugador 2", "")).strip()
        jornada = str(fila.get("Jornada", "")).strip()
        semana = str(fila.get("Semana", "")).strip()
        if not j1 or not j2:
            continue
        # Clave unica del partido: jornada + los dos jugadores
        clave = f"{jornada}|{j1}|{j2}"
        if clave not in partidos:
            partidos[clave] = {
                "jornada": jornada,
                "partido": f"{j1} vs {j2}",
                "semana": semana,
                "mercados": 0,
                "estados": [],
            }
        partidos[clave]["mercados"] += 1
        partidos[clave]["estados"].append(
            _estado_fila(fila.get("Acierto", "")))

    # Resolver el estado global de cada partido
    resultado = []
    for p in partidos.values():
        estados = set(p["estados"])
        if estados == {"verificado"}:
            estado = "✅ Verificado"
        elif estados == {"pendiente"}:
            estado = "⏳ Pendiente"
        elif estados == {"no_jugado"}:
            estado = "🚫 No jugado"
        elif "pendiente" in estados:
            # Si queda algo pendiente, el partido esta a medias
            estado = "⏳ Pendiente"
        else:
            # Mezcla de verificado y no jugado (raro pero posible)
            estado = "✅ Verificado"
        resultado.append({
            "Jornada": p["jornada"],
            "Partido": p["partido"],
            "Semana": p["semana"],
            "Mercados": p["mercados"],
            "Estado": estado,
        })

    resultado.sort(key=lambda x: (x["Jornada"], x["Partido"]))
    return resultado


def _emparejar_nombre_simple(nombre, candidatos):
    """Empareja un nombre con uno de una lista (exacto -> subcadena -> apellido).
    Devuelve el nombre del candidato que coincide, o None.
    """
    if not nombre:
        return None
    n = str(nombre).lower().strip()
    for c in candidatos:
        if str(c).lower().strip() == n:
            return c
    for c in candidatos:
        cl = str(c).lower().strip()
        if n in cl or cl in n:
            return c
    ape = n.split()[-1] if n.split() else n
    for c in candidatos:
        if ape and ape in str(c).lower():
            return c
    return None


def _extraer_partidos_jugados(jornada):
    """Lee una pestana de jornada y devuelve los partidos realmente jugados.

    Cada partido son DOS filas consecutivas en la zona de partidos (columnas
    A-E): nombre, RESULTADO (legs), Nº 180S. Empareja las filas de dos en dos.

    Devuelve una lista de dicts, uno por partido:
      {j1, j2, legs1, legs2, t180_1, t180_2}

    Tiene en cuenta que 'Final Sábado' tiene todo desplazado una fila mas
    abajo (eso ya lo gestiona cargar_todo via los CORTES de config.py, asi
    que aqui solo emparejamos las filas que cargar_todo devuelve).
    """
    from data_loading import cargar_todo
    from config import URLS, CORTES

    url = URLS.get(jornada, "")
    cortes = CORTES.get(jornada, {})
    if not url or not cortes:
        return []

    try:
        df_izq, _ = cargar_todo(url, jornada, cortes)
    except Exception:
        return []
    if df_izq is None or len(df_izq) < 2:
        return []

    # df_izq tiene columnas: [JUGADORES, RESULTADO, Nº 180S, Promedio, Checkout].
    # Trabajamos por posicion para no depender de los nombres exactos.
    filas = df_izq.values.tolist()

    def _num(v):
        try:
            return int(float(str(v).replace(",", ".").strip()))
        except Exception:
            return None

    partidos = []
    i = 0
    while i + 1 < len(filas):
        f1 = filas[i]
        f2 = filas[i + 1]
        nombre1 = str(f1[0]).strip() if len(f1) > 0 else ""
        nombre2 = str(f2[0]).strip() if len(f2) > 0 else ""
        # Saltar filas sin nombre valido
        if (not nombre1 or not nombre2 or
                nombre1.lower() in ("nan", "") or
                nombre2.lower() in ("nan", "")):
            i += 1
            continue
        legs1 = _num(f1[1]) if len(f1) > 1 else None
        legs2 = _num(f2[1]) if len(f2) > 1 else None
        t180_1 = _num(f1[2]) if len(f1) > 2 else None
        t180_2 = _num(f2[2]) if len(f2) > 2 else None
        # Un partido valido necesita los legs de ambos
        if legs1 is None or legs2 is None:
            i += 1
            continue
        partidos.append({
            "j1": nombre1, "j2": nombre2,
            "legs1": legs1, "legs2": legs2,
            "t180_1": t180_1 if t180_1 is not None else 0,
            "t180_2": t180_2 if t180_2 is not None else 0,
        })
        i += 2

    return partidos


def _verificar_mercado(mercado, linea, prediccion, legs_a, legs_b,
                       t180_a, t180_b):
    """Comprueba si una prediccion acerto, dado el resultado real del partido.

    'a' es el Jugador 1 de la prediccion, 'b' el Jugador 2 (en el mismo orden
    en que se registraron). legs y t180 son los del partido real.

    Devuelve:
      1   -> la prediccion acerto
      0   -> la prediccion fallo
      None -> el mercado no se puede verificar (raro)
    """
    dif = legs_a - legs_b           # diferencia de legs J1 - J2
    total_legs = legs_a + legs_b
    gana_a = legs_a > legs_b

    # ── Ganador ──────────────────────────────────────────────────────────────
    if mercado == "Ganador":
        # prediccion es "Gana J1" o "Gana J2"
        acerto_es_j1 = "j1" in prediccion.lower()
        if acerto_es_j1:
            return 1 if gana_a else 0
        else:
            return 1 if not gana_a else 0

    # ── Handicap legs ────────────────────────────────────────────────────────
    if mercado == "Handicap legs":
        # 'linea' es del tipo "J1 -1.5 Legs", "J2 +2.5 Legs", etc.
        # 'prediccion' es "Si" / "No": Si = el modelo cree que SE CUMPLE.
        se_cumple = None
        l = linea.lower()
        if l.startswith("j1 -1.5"):
            se_cumple = dif >= 2
        elif l.startswith("j1 -2.5"):
            se_cumple = dif >= 3
        elif l.startswith("j1 +1.5"):
            se_cumple = dif >= -1     # no pierde por 2 o mas
        elif l.startswith("j1 +2.5"):
            se_cumple = dif >= -2
        elif l.startswith("j2 -1.5"):
            se_cumple = (-dif) >= 2
        elif l.startswith("j2 -2.5"):
            se_cumple = (-dif) >= 3
        elif l.startswith("j2 +1.5"):
            se_cumple = (-dif) >= -1
        elif l.startswith("j2 +2.5"):
            se_cumple = (-dif) >= -2
        if se_cumple is None:
            return None
        predijo_si = prediccion.strip().lower() in ("si", "sí")
        return 1 if (se_cumple == predijo_si) else 0

    # ── Total de legs ────────────────────────────────────────────────────────
    if mercado == "Total legs":
        # 'prediccion' es directamente "Más de 5.5" o "Menos de 5.5":
        # el lado que el modelo considero mas probable.
        p = prediccion.strip().lower()
        if "más" in p or "mas" in p:
            # El modelo predijo "mas de 5.5": acierta si hubo > 5.5 legs
            return 1 if total_legs > 5.5 else 0
        elif "menos" in p:
            return 1 if total_legs < 5.5 else 0
        else:
            return None

    # ── 180s (lineas +0.5 / +1.5 / +2.5) ─────────────────────────────────────
    if mercado == "180s":
        l = linea.lower()
        if l.startswith("j1 +0.5"):
            se_cumple = t180_a >= 1
        elif l.startswith("j1 +1.5"):
            se_cumple = t180_a >= 2
        elif l.startswith("j2 +0.5"):
            se_cumple = t180_b >= 1
        elif l.startswith("j2 +1.5"):
            se_cumple = t180_b >= 2
        elif l.startswith("ambos +0.5"):
            se_cumple = (t180_a >= 1) and (t180_b >= 1)
        elif l.startswith("ambos +1.5"):
            se_cumple = (t180_a + t180_b) >= 2
        elif l.startswith("ambos +2.5"):
            se_cumple = (t180_a + t180_b) >= 3
        else:
            return None
        predijo_si = prediccion.strip().lower() in ("si", "sí")
        return 1 if (se_cumple == predijo_si) else 0

    # ── Quien hace mas 180s (H2H) ────────────────────────────────────────────
    if mercado == "Mas 180s (H2H)":
        # 'prediccion' es el favorito: "J1 mas 180s" / "Empate 180s" / "J2 mas 180s"
        if t180_a > t180_b:
            real = "J1 mas 180s"
        elif t180_b > t180_a:
            real = "J2 mas 180s"
        else:
            real = "Empate 180s"
        return 1 if (prediccion.strip().lower() == real.lower()) else 0

    return None


def verificar_resultados(url_sheet=None):
    """Verifica automaticamente las predicciones pendientes comparandolas con
    los resultados reales de los partidos en las pestanas de jornada.

    Para cada prediccion sin 'Acierto':
      - Busca si ese enfrentamiento se jugo de verdad en alguna jornada.
      - Si se jugo: comprueba el mercado y escribe 1 o 0.
      - Si NO se jugo: escribe "no jugado" (enfrentamiento hipotetico que
        nunca llego a disputarse).

    Escribe los resultados en LOTE en la columna 'Acierto' (y 'Resultado
    real') de la hoja Predicciones.

    Devuelve un dict resumen:
      {ok, verificadas, aciertos, fallos, no_jugado, sin_cambios, error}
    """
    hoja, err = _abrir_hoja_predicciones(url_sheet)
    if hoja is None:
        return {"ok": False, "verificadas": 0, "aciertos": 0, "fallos": 0,
                "no_jugado": 0, "sin_cambios": 0,
                "error": err or "No se pudo abrir la hoja."}

    # Leer todas las predicciones
    try:
        registros = hoja.get_all_records()
    except Exception as e:
        return {"ok": False, "verificadas": 0, "aciertos": 0, "fallos": 0,
                "no_jugado": 0, "sin_cambios": 0,
                "error": f"No se pudieron leer las predicciones: {e}"}

    if not registros:
        return {"ok": True, "verificadas": 0, "aciertos": 0, "fallos": 0,
                "no_jugado": 0, "sin_cambios": 0, "error": ""}

    # Cargar los partidos jugados de TODAS las jornadas (una sola vez).
    # partidos_por_jornada[jornada] = lista de dicts de partido.
    partidos_por_jornada = {}
    for jornada in JORNADAS_VERIFICABLES:
        partidos_por_jornada[jornada] = _extraer_partidos_jugados(jornada)

    # Indice de columnas de la hoja (fila 1 = cabecera)
    columnas = hoja.row_values(1)
    try:
        col_acierto = columnas.index("Acierto") + 1
        col_resultado = columnas.index("Resultado real") + 1
    except ValueError:
        return {"ok": False, "verificadas": 0, "aciertos": 0, "fallos": 0,
                "no_jugado": 0, "sin_cambios": 0,
                "error": "La hoja no tiene las columnas 'Acierto' / "
                         "'Resultado real'. ¿Es la hoja correcta?"}

    # Recorrer predicciones y preparar las actualizaciones
    actualizaciones = []   # lista de (fila_hoja, valor_acierto, valor_resultado)
    aciertos = fallos = no_jugado = sin_cambios = 0

    for idx, reg in enumerate(registros):
        fila_hoja = idx + 2   # +1 cabecera, +1 base-1

        # Si ya esta verificada (Acierto no vacio), no la tocamos
        acierto_actual = str(reg.get("Acierto", "")).strip()
        if acierto_actual != "":
            sin_cambios += 1
            continue

        jornada = str(reg.get("Jornada", "")).strip()
        j1_pred = str(reg.get("Jugador 1", "")).strip()
        j2_pred = str(reg.get("Jugador 2", "")).strip()
        mercado = str(reg.get("Mercado", "")).strip()
        linea = str(reg.get("Linea", "")).strip()
        prediccion = str(reg.get("Prediccion", "")).strip()

        partidos = partidos_por_jornada.get(jornada, [])
        if not partidos:
            # Jornada desconocida o sin partidos cargados: lo dejamos pendiente
            continue

        # Buscar el partido real entre estos dos jugadores
        nombres_jornada = []
        for p in partidos:
            nombres_jornada.extend([p["j1"], p["j2"]])
        nombres_jornada = list(set(nombres_jornada))

        j1_real = _emparejar_nombre_simple(j1_pred, nombres_jornada)
        j2_real = _emparejar_nombre_simple(j2_pred, nombres_jornada)

        partido = None
        orden_invertido = False
        if j1_real and j2_real:
            for p in partidos:
                if p["j1"] == j1_real and p["j2"] == j2_real:
                    partido = p
                    orden_invertido = False
                    break
                if p["j1"] == j2_real and p["j2"] == j1_real:
                    partido = p
                    orden_invertido = True
                    break

        if partido is None:
            # El partido no aparece en la pestana de la jornada. Puede ser
            # que aun no se haya jugado: NO lo marcamos. Lo dejamos
            # PENDIENTE para que una verificacion posterior lo recoja
            # cuando el resultado ya este disponible.
            continue

        # Alinear legs/180s con el orden J1/J2 de la PREDICCION
        if not orden_invertido:
            legs_a, legs_b = partido["legs1"], partido["legs2"]
            t180_a, t180_b = partido["t180_1"], partido["t180_2"]
        else:
            legs_a, legs_b = partido["legs2"], partido["legs1"]
            t180_a, t180_b = partido["t180_2"], partido["t180_1"]

        resultado_txt = f"{legs_a}-{legs_b}"
        acierto = _verificar_mercado(mercado, linea, prediccion,
                                     legs_a, legs_b, t180_a, t180_b)
        if acierto is None:
            # Mercado no verificable: lo dejamos pendiente
            continue

        actualizaciones.append((fila_hoja, str(acierto), resultado_txt))
        if acierto == 1:
            aciertos += 1
        else:
            fallos += 1

    # Escribir las actualizaciones en la hoja.
    # Se hace celda por celda agrupando, pero usando update por rangos para
    # no saturar la API. gspread permite actualizar celdas individuales;
    # aqui agrupamos por columna en bloques.
    if actualizaciones:
        try:
            celdas = []
            for fila_hoja, val_acierto, val_resultado in actualizaciones:
                celdas.append(gspread.Cell(fila_hoja, col_acierto, val_acierto))
                celdas.append(gspread.Cell(fila_hoja, col_resultado,
                                           val_resultado))
            hoja.update_cells(celdas, value_input_option="RAW")
        except Exception as e:
            return {"ok": False, "verificadas": 0, "aciertos": 0,
                    "fallos": 0, "no_jugado": 0, "sin_cambios": sin_cambios,
                    "error": f"Error escribiendo los resultados: {e}"}

    return {
        "ok": True,
        "verificadas": aciertos + fallos,
        "aciertos": aciertos,
        "fallos": fallos,
        "no_jugado": no_jugado,
        "sin_cambios": sin_cambios,
        "error": "",
    }
