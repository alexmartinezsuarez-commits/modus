import streamlit as st
import pandas as pd
import numpy as np
import requests
from scipy.stats import poisson
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import time

st.set_page_config(page_title="Modus Super Series App", layout="wide", page_icon="🎯")

URLS = {
    "Grupo A Lunes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=770660826&single=true&output=csv",
    "Grupo A Martes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=1188400317&single=true&output=csv",
    "Grupo A Miércoles": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=611921899&single=true&output=csv",
    "Grupo C Jueves": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=1451632905&single=true&output=csv",
    "Grupo B Jueves": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=838707746&single=true&output=csv",
    "Grupo C Viernes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=951305991&single=true&output=csv",
    "Grupo B Viernes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=895443076&single=true&output=csv",
    "Final Sábado": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=843639863&single=true&output=csv",
    "Resumen Semanal": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=701394558&single=true&output=csv",
    "Value Bets": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRpzkL3TKUdIptc202-w-A0ifJtiFIIP9rI0q0zQzn_I4VKX8qUi_-r1XXfPkwefN03rIQzYUNyg9xP/pub?gid=2019911134&single=true&output=csv"
}

CORTES = {
    "Resumen Semanal": {"filas": (5, 20), "cols": (1, 10), "der_nombres": 5, "der_cols": (1, 10)},
    "Grupo A Lunes":      {"izq_filas": (5, 36), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo A Martes":     {"izq_filas": (5, 36), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo A Miércoles":  {"izq_filas": (5, 36), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo C Jueves":     {"izq_filas": (5, 36), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo B Jueves":     {"izq_filas": (5, 26), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo C Viernes":    {"izq_filas": (5, 36), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Grupo B Viernes":    {"izq_filas": (5, 26), "izq_cols": (0, 5), "der_nombres": 5,  "der_cols": (6, 12)},
    "Final Sábado":       {"izq_filas": (5, 24), "izq_cols": (0, 5), "der_nombres": 6,  "der_cols": (6, 12)},
    "Value Bets":         {"unica_filas": (6, 28), "unica_cols": (0, 10)}
}

PESTANAS_CON_STATS = [k for k in URLS if k not in ("Value Bets",)]

BANDERAS = {
    "GB": "🇬🇧", "NL": "🇳🇱", "BE": "🇧🇪", "PT": "🇵🇹", "AU": "🇦🇺",
    "DE": "🇩🇪", "PL": "🇵🇱", "IE": "🇮🇪", "CA": "🇨🇦",
    "SE": "🇸🇪", "DK": "🇩🇰", "FR": "🇫🇷", "ES": "🇪🇸",
}

JUGADORES_PAISES = {
    # Reino Unido
    "luke littler": "GB", "gary anderson": "GB", "peter wright": "GB", "gerwyn price": "GB",
    "jonny clayton": "GB", "james wade": "GB", "dave chisnall": "GB", "rob cross": "GB",
    "nathan aspinall": "GB", "chris dobey": "GB", "josh rock": "GB", "luke humphries": "GB",
    "michael smith": "GB", "ross smith": "GB", "stephen bunting": "GB", "andrew gilding": "GB",
    "brendan dolan": "GB", "ritchie edhouse": "GB", "ryan searle": "GB", "callan rydz": "GB",
    "joe cullen": "GB", "cameron menzies": "GB", "connor scutt": "GB", "glenn de bois": "GB",
    "nick kenny": "GB", "nathan rafferty": "GB", "steve west": "GB", "neil duff": "GB",
    "boris krcmar": "GB", "lewis williams": "GB", "scott waites": "GB", "kristjan karer": "GB",
    "kyle anderson": "GB", "martin adams": "GB", "john lowe": "GB", "barry hearn": "GB",
    
    # Países Bajos
    "michael van gerwen": "NL", "danny noppert": "NL", "wessel nijman": "NL", "dirk van duijvenbode": "NL",
    "kevin doets": "NL", "jelle klaasen": "NL", "maik kuivenhoven": "NL", "benito van de pas": "NL",
    "michiel kiemeneij": "NL", "mervyn king": "NL",
    
    # Bélgica
    "dimitri van den bergh": "BE", "kim huybrechts": "BE", "alexis toylo": "BE",
    
    # Portugal
    "jose de sousa": "PT", "noa lynn": "PT", "paulo costa": "PT",
    
    # Australia
    "damon heta": "AU",
    
    # Alemania
    "martin schindler": "DE", "gabriel clemens": "DE", "ricardo pietreczko": "DE", 
    "florian hempel": "DE", "max hopp": "DE",
    
    # Polonia
    "krzysztof ratajski": "PL", "przemyslaw cecot": "PL",
    
    # Irlanda
    "keane barry": "IE", "william o'connor": "IE", "ciaran teeters": "IE", "dylan slevin": "IE",
    "paddy power": "IE",
    
    # Canadá
    "matt campbell": "CA",
    
    # Suecia
    "rikard karlsson": "SE",
    
    # Dinamarca
    "anders hertz": "DK",
    
    # Francia
    "boris krcmar": "FR",
    
    # España
    "carlos garcia": "ES",
}

if "vb_fuente" not in st.session_state:
    st.session_state.vb_fuente = "Resumen Semanal"
if "vb_j1" not in st.session_state:
    st.session_state.vb_j1 = None
if "vb_j2" not in st.session_state:
    st.session_state.vb_j2 = None
if "vb_calcular" not in st.session_state:
    st.session_state.vb_calcular = False
if "last_update" not in st.session_state:
    st.session_state.last_update = {}

def arreglar_columnas(df):
    nuevas_cols = []
    for i, col in enumerate(df.columns):
        nombre = str(col)
        if nombre == 'nan' or nombre.strip() == '':
            nombre = f"Dato_{i}"
        while nombre in nuevas_cols:
            nombre = f"{nombre}_{i}"
        nuevas_cols.append(nombre)
    df.columns = nuevas_cols
    return df

def pintar_partidos(fila):
    if (fila.name // 2) % 2 == 0:
        return ['background-color: rgba(150, 150, 150, 0.15)'] * len(fila)
    return ['background-color: transparent'] * len(fila)

def extraer_stats_diarias(df, fila_n, col_rango):
    try:
        nombres = df.iloc[fila_n, col_rango[0]:col_rango[1]].values
        jugadores = [str(n).strip() for n in nombres if str(n).strip() not in ['nan', '']]
        data_final = {}
        for i, j in enumerate(jugadores):
            stats = {}
            curr_f = fila_n + 1
            while curr_f + 1 < len(df) and curr_f < fila_n + 35:
                tit = str(df.iloc[curr_f, col_rango[0]]).strip()
                if tit != 'nan' and tit != '':
                    val_fila1 = str(df.iloc[curr_f + 1, col_rango[0] + i]).strip() if curr_f + 1 < len(df) else 'nan'
                    val_fila2 = str(df.iloc[curr_f + 2, col_rango[0] + i]).strip() if curr_f + 2 < len(df) else 'nan'
                    val = val_fila1 if val_fila1 != 'nan' else val_fila2
                    if val != 'nan' and val != '':
                        stats[tit] = val
                curr_f += 1
            data_final[j] = stats
        return data_final
    except:
        return {}

def extraer_stats_resumen_semanal(df):
    try:
        headers = [str(v).strip() for v in df.iloc[5].values if str(v).strip() not in ['', 'nan']]
        data = df.iloc[6:].copy()
        jugadores = {}
        for idx, row in data.iterrows():
            nombre = str(row.iloc[1]).strip() if len(row) > 1 else ""
            if nombre in ['nan', '', '=']:
                continue
            stats = {}
            col_idx = 2
            header_idx = 1
            while col_idx < len(row) and header_idx < len(headers):
                valor = row.iloc[col_idx]
                header = headers[header_idx]
                if header.strip() == '=':
                    col_idx += 1
                    header_idx += 1
                    continue
                if str(valor).strip() not in ['nan', '', '=']:
                    stats[header.lower().strip()] = valor
                col_idx += 1
                header_idx += 1
            if stats:
                jugadores[nombre.lower()] = stats
        return jugadores
    except Exception as e:
        st.error(f"Error extrayendo Resumen Semanal: {e}")
        return {}

@st.cache_data(ttl=5)
def cargar_jugadores_desde(pestana: str):
    try:
        url = URLS.get(pestana, "")
        if not url:
            return {}
        df = pd.read_csv(url, header=None)
        st.session_state.last_update[pestana] = datetime.now()
        fila_header = None
        for i, row in df.iterrows():
            if any(str(v).strip().lower() == "jugador" for v in row.values):
                fila_header = i
                break
        if fila_header is None:
            corte = CORTES.get(pestana, {})
            if "der_nombres" in corte:
                der_f  = corte["der_nombres"]
                der_c  = corte["der_cols"]
                stats  = extraer_stats_diarias(df, der_f, der_c)
                jugadores = {}
                for nombre, s in stats.items():
                    pr       = safe_float(_buscar_stat(s, ["global", "puntuación", "puntuacion"]))
                    lam_180  = safe_float(_buscar_stat(s, ["180", "ciento"]))
                    lam_legs = safe_float(_buscar_stat(s, ["legs por partido", "promedio legs", "leg por partido"]))
                    promedio_dardos = safe_float(_buscar_stat(s, ["promedio puntos", "average", "promedio dardos", "ppd", "media puntos"]))
                    checkouts = safe_float(str(_buscar_stat(s, ["checkout"])).replace("%", ""))
                    pct_vic = safe_float(str(_buscar_stat(s, ["porcentaje victoria", "% victoria"])).replace("%", ""))
                    jugadores[nombre.lower()] = {
                        "nombre_original": nombre,
                        "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                        "promedio_dardos": promedio_dardos,
                        "checkouts": checkouts, "pct_victorias": pct_vic
                    }
                return jugadores
            return {}
        headers = [str(v).strip() for v in df.iloc[fila_header].values]
        data    = df.iloc[fila_header + 1:].copy()
        data.columns = headers
        data = data.reset_index(drop=True)
        def buscar_col(keywords):
            for h in headers:
                if any(kw.lower() in h.lower() for kw in keywords):
                    return h
            return None
        col_jugador = buscar_col(["jugador", "nombre"])
        col_pr      = buscar_col(["puntuación global", "puntuacion global", "global", "power"])
        col_180     = buscar_col(["180"])
        col_legs    = buscar_col(["legs", "leg"])
        col_promedio_dardos = buscar_col(["promedio puntos", "average", "promedio dardos", "ppd", "media puntos"])
        col_checkouts = buscar_col(["checkout"])
        col_pct_vic = buscar_col(["porcentaje victoria", "% victoria", "% victoria", "%victoria"])
        jugadores = {}
        for _, fila in data.iterrows():
            nombre = str(fila.get(col_jugador, "")).strip() if col_jugador else ""
            if not nombre or nombre.lower() in ["nan", "jugador", ""]:
                continue
            pr       = safe_float(fila.get(col_pr,    0)) if col_pr    else 0.0
            lam_180  = safe_float(fila.get(col_180,   0)) if col_180   else 0.0
            lam_legs = safe_float(fila.get(col_legs,  0)) if col_legs  else 0.0
            promedio_dardos = safe_float(fila.get(col_promedio_dardos, 0)) if col_promedio_dardos else 0.0
            checkouts = safe_float(str(fila.get(col_checkouts, 0)).replace("%", "")) if col_checkouts else 0.0
            pct_vic = safe_float(str(fila.get(col_pct_vic, 0)).replace("%", "")) if col_pct_vic else 0.0
            jugadores[nombre.lower()] = {
                "nombre_original": nombre,
                "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                "promedio_dardos": promedio_dardos,
                "checkouts": checkouts, "pct_victorias": pct_vic
            }
        return jugadores
    except Exception as e:
        st.error(f"Error cargando {pestana}: {e}")
        return {}

@st.cache_data(ttl=5)
def cargar_todo(url, opcion, cortes):
    try:
        df = pd.read_csv(url, header=None)
        st.session_state.last_update[opcion] = datetime.now()
        if opcion == "Resumen Semanal":
            stats = extraer_stats_resumen_semanal(df)
            df_list = []
            for nombre_lower, stat_dict in stats.items():
                fila = {"Jugador": nombre_lower}
                orden_columnas = [
                    "legs por partido", "media 180 por partida", "promedio puntos",
                    "diferencia legs", "promedio checkouts", "número victorias",
                    "número derrotas", "porcentaje victoria"
                ]
                for col in orden_columnas:
                    for k, v in stat_dict.items():
                        if col in k.lower():
                            fila[k] = v
                for k, v in stat_dict.items():
                    if "puntuación" in k.lower() or "puntacion" in k.lower():
                        fila[k] = v
                df_list.append(fila)
            df_display = pd.DataFrame(df_list) if df_list else pd.DataFrame()
            return df_display, stats
        elif opcion == "Value Bets":
            f, c = cortes["unica_filas"], cortes["unica_cols"]
            res = df.iloc[f[0]:f[1], c[0]:c[1]]
            res.columns = res.iloc[0]; res = res[1:]
            return arreglar_columnas(res.dropna(how='all')), None
        else:
            f, c = cortes["izq_filas"], cortes["izq_cols"]
            izq = df.iloc[f[0]:f[1], c[0]:c[1]]
            izq.columns = izq.iloc[0]; izq = izq[1:]
            s = extraer_stats_diarias(df, cortes["der_nombres"], cortes["der_cols"])
            return arreglar_columnas(izq.dropna(how='all')), s
    except Exception as e:
        st.error(f"Error cargando {opcion}: {e}")
        return None, None

@st.cache_data(ttl=10)
def obtener_partidos_vivos_api():
    try:
        base_url = "https://api-igamedc.igamemedia.com/api/mss-web"
        response = requests.get(f"{base_url}/results-fixtures", timeout=5)
        if response.status_code != 200:
            return None
        data = response.json()
        week_activa = data.get("selected", {}).get("week", "")
        grupos = data.get("selected", {}).get("groups", [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 8}])
        partidos_vivos = []
        for grupo in grupos:
            url = f"{base_url}/results-fixtures?group={grupo['id']}"
            if week_activa:
                url += f"&week={week_activa}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    fixtures = resp.json().get("Fixtures", resp.json().get("fixtures", []))
                    for fixture in fixtures:
                        if fixture.get("status", "").lower() != "not started":
                            fixture_id = fixture.get("gameId") or fixture.get("Id") or fixture.get("id")
                            if fixture_id:
                                try:
                                    detail_resp = requests.get(f"{base_url}/fixtures/{fixture_id}", timeout=5)
                                    if detail_resp.status_code == 200:
                                        detail = detail_resp.json()
                                        stats = detail.get("playersStatistics", {}).get("statistics", [])
                                        if stats and len(stats) >= 2:
                                            partidos_vivos.append({
                                                "id": fixture_id,
                                                "fecha": fixture.get("fixture", ""),
                                                "j1": fixture.get("playerHome", ""),
                                                "j2": fixture.get("playerAway", ""),
                                                "score_j1": fixture.get("scorePlayerHome", ""),
                                                "score_j2": fixture.get("scorePlayerAway", ""),
                                                "j1_average": stats[0].get("average", ""),
                                                "j2_average": stats[1].get("average", ""),
                                                "j1_180s": stats[0].get("turns180", ""),
                                                "j2_180s": stats[1].get("turns180", ""),
                                                "j1_checkout": stats[0].get("checkoutPercentage", ""),
                                                "j2_checkout": stats[1].get("checkoutPercentage", "")
                                            })
                                except:
                                    pass
            except:
                continue
        return partidos_vivos if partidos_vivos else None
    except Exception as e:
        st.warning(f"⚠️ Error obteniendo datos de MODUS: {e}")
        return None

def get_jornada_actual():
    ahora = datetime.now()
    hora_actual = ahora.hour + ahora.minute / 60
    dia_semana = ahora.weekday()
    if dia_semana in [0, 1, 2]:
        if 10.0 <= hora_actual < 16.0:
            jornadas_grupo_a = {
                0: ("Grupo A Lunes", URLS["Grupo A Lunes"]),
                1: ("Grupo A Martes", URLS["Grupo A Martes"]),
                2: ("Grupo A Miércoles", URLS["Grupo A Miércoles"])
            }
            nombre, url = jornadas_grupo_a[dia_semana]
            return nombre, url, True
    if dia_semana in [3, 4]:
        if 13.0 <= hora_actual < 19.0:
            jornadas_grupo_c = {
                3: ("Grupo C Jueves", URLS["Grupo C Jueves"]),
                4: ("Grupo C Viernes", URLS["Grupo C Viernes"])
            }
            nombre, url = jornadas_grupo_c[dia_semana]
            return nombre, url, True
    if hora_actual >= 22.0:
        if dia_semana == 3:
            return "Grupo B Jueves", URLS["Grupo B Jueves"], True
        elif dia_semana == 4:
            return "Grupo B Viernes", URLS["Grupo B Viernes"], True
    if dia_semana == 5 and hora_actual >= 20.0:
        return "Final Sábado", URLS["Final Sábado"], True
    elif hora_actual < 3.0:
        ayer = ahora - timedelta(days=1)
        dia_ayer = ayer.weekday()
        if dia_ayer == 3:
            return "Grupo B Jueves", URLS["Grupo B Jueves"], True
        elif dia_ayer == 4:
            return "Grupo B Viernes", URLS["Grupo B Viernes"], True
        elif dia_ayer == 5:
            return "Final Sábado", URLS["Final Sábado"], True
    return None, None, False

def get_proxima_jornada():
    jornadas_orden = [
        ("Grupo A Lunes", URLS["Grupo A Lunes"], 0, 10.0),
        ("Grupo A Martes", URLS["Grupo A Martes"], 1, 10.0),
        ("Grupo A Miércoles", URLS["Grupo A Miércoles"], 2, 10.0),
        ("Grupo C Jueves", URLS["Grupo C Jueves"], 3, 13.0),
        ("Grupo B Jueves", URLS["Grupo B Jueves"], 3, 22.0),
        ("Grupo C Viernes", URLS["Grupo C Viernes"], 4, 13.0),
        ("Grupo B Viernes", URLS["Grupo B Viernes"], 4, 22.0),
        ("Final Sábado", URLS["Final Sábado"], 5, 20.0),
    ]
    ahora = datetime.now()
    hora_actual = ahora.hour + ahora.minute / 60
    dia_semana = ahora.weekday()
    for nombre, url, dia, hora_inicio in jornadas_orden:
        if dia > dia_semana or (dia == dia_semana and hora_inicio > hora_actual):
            return nombre, url
    return jornadas_orden[0][0], jornadas_orden[0][1]

def obtener_bandera(nombre_jugador):
    nombre_lower = nombre_jugador.lower().strip().replace("_", " ")
    codigo_pais = JUGADORES_PAISES.get(nombre_lower, None)
    if codigo_pais and codigo_pais in BANDERAS:
        return BANDERAS[codigo_pais]
    return None

def calcular_tendencia(valor_actual, valor_semanal, etiqueta):
    """Calcula tendencia con reglas específicas: 5% general, 3% para Puntuación Global"""
    try:
        val_act = float(str(valor_actual).replace('%', '').strip())
        val_sem = float(str(valor_semanal).replace('%', '').strip())
    except:
        return "", valor_actual, ""
    
    # No mostrar indicador para Victorias o Derrotas
    if "victoria" in etiqueta.lower() or "derrota" in etiqueta.lower():
        return "", valor_actual, ""
    
    # Calcular porcentaje de cambio
    if val_sem == 0:
        porcentaje_cambio = 0
    else:
        porcentaje_cambio = ((val_act - val_sem) / abs(val_sem)) * 100
    
    # Umbral diferente para Puntuación Global
    umbral = 3 if "puntiación" in etiqueta.lower() else 5
    
    # Mostrar indicador solo si supera el umbral
    if abs(porcentaje_cambio) >= umbral:
        if porcentaje_cambio > 0:
            indicador = f"🟢 ↑"
        else:
            indicador = f"🔴 ↓"
        comparativa = f"({val_sem:.1f})"
        return indicador, valor_actual, comparativa
    else:
        comparativa = f"({val_sem:.1f})"
        return "", valor_actual, comparativa

def verificar_alerta_excepcional(valor_actual, valor_semanal, etiqueta):
    """Detecta mejoras excepcionales (>15%) para alertas"""
    try:
        val_act = float(str(valor_actual).replace('%', '').strip())
        val_sem = float(str(valor_semanal).replace('%', '').strip())
    except:
        return False, 0
    
    if val_sem == 0:
        return False, 0
    
    porcentaje_cambio = ((val_act - val_sem) / abs(val_sem)) * 100
    es_excepcional = abs(porcentaje_cambio) > 15
    return es_excepcional, porcentaje_cambio

@st.cache_data(ttl=30, show_spinner=False)
def extraer_h2h_semanal(j1_nombre, j2_nombre):
    h2h_data = {
        "victorias_j1": 0,
        "victorias_j2": 0,
        "partidos": []
    }
    dias_semana = [
        "Grupo A Lunes", "Grupo A Martes", "Grupo A Miércoles",
        "Grupo C Jueves", "Grupo B Jueves",
        "Grupo C Viernes", "Grupo B Viernes",
        "Final Sábado"
    ]
    j1_lower = j1_nombre.lower().strip().replace("_", " ")
    j2_lower = j2_nombre.lower().strip().replace("_", " ")
    for dia in dias_semana:
        try:
            df_partidos, _ = cargar_todo(URLS[dia], dia, CORTES[dia])
            if df_partidos is None or len(df_partidos) < 2:
                continue
            for i in range(0, len(df_partidos) - 1, 2):
                fila_j1 = df_partidos.iloc[i]
                fila_j2 = df_partidos.iloc[i + 1]
                nombre_j1 = str(fila_j1.iloc[0]).strip().lower().replace("_", " ")
                nombre_j2 = str(fila_j2.iloc[0]).strip().lower().replace("_", " ")
                es_enfrentamiento = (
                    (j1_lower in nombre_j1 or nombre_j1 in j1_lower) and
                    (j2_lower in nombre_j2 or nombre_j2 in j2_lower)
                ) or (
                    (j2_lower in nombre_j1 or nombre_j1 in j2_lower) and
                    (j1_lower in nombre_j2 or nombre_j2 in j1_lower)
                )
                if es_enfrentamiento:
                    resultado_j1 = str(fila_j1.iloc[1]).strip() if len(fila_j1) > 1 else ""
                    resultado_j2 = str(fila_j2.iloc[1]).strip() if len(fila_j2) > 1 else ""
                    ganador = None
                    marcador = f"{resultado_j1}-{resultado_j2}"
                    if "4" in resultado_j1:
                        ganador = nombre_j1.title()
                        if j1_lower in nombre_j1 or nombre_j1 in j1_lower:
                            h2h_data["victorias_j1"] += 1
                        else:
                            h2h_data["victorias_j2"] += 1
                    elif "4" in resultado_j2:
                        ganador = nombre_j2.title()
                        if j1_lower in nombre_j2 or nombre_j2 in j1_lower:
                            h2h_data["victorias_j1"] += 1
                        else:
                            h2h_data["victorias_j2"] += 1
                    if ganador:
                        h2h_data["partidos"].append({
                            "dia": dia,
                            "jugador1": nombre_j1.title(),
                            "jugador2": nombre_j2.title(),
                            "marcador": marcador,
                            "ganador": ganador
                        })
        except Exception as e:
            continue
    return h2h_data

def safe_float(val, default=0.0):
    try:
        v = float(str(val).replace(',', '.').strip())
        if not np.isfinite(v):
            return default
        return v
    except:
        return default

def sanitize_prob(p):
    if not np.isfinite(p) or p <= 0:
        return 0.0001
    if p >= 1:
        return 0.9999
    return max(0.0001, min(0.9999, p))

def prob_victoria(pr1, pr2):
    if pr1 <= 0 and pr2 <= 0:
        return 0.5, 0.5
    num = (pr1 ** 4.5) * 1.12
    den = num + (pr2 ** 4.5)
    if den == 0:
        return 0.5, 0.5
    p1 = num / den
    return sanitize_prob(p1), sanitize_prob(1 - p1)

def prob_180s(lam1, lam2):
    lam_total = lam1 + lam2
    ambos_05 = sanitize_prob((1 - poisson.cdf(0, lam1)) * (1 - poisson.cdf(0, lam2)))
    return {
        "J1 +0.5": sanitize_prob(1 - poisson.cdf(0, lam1)),
        "J1 +1.5": sanitize_prob(1 - poisson.cdf(1, lam1)),
        "J2 +0.5": sanitize_prob(1 - poisson.cdf(0, lam2)),
        "J2 +1.5": sanitize_prob(1 - poisson.cdf(1, lam2)),
        "Ambos +0.5": ambos_05,
        "Ambos +1.5": sanitize_prob(1 - poisson.cdf(1, lam_total)),
        "Ambos +2.5": sanitize_prob(1 - poisson.cdf(2, lam_total)),
    }

def quien_hace_mas_180s(lam1, lam2):
    p_empate = sum(poisson.pmf(k, lam1) * poisson.pmf(k, lam2) for k in range(3))
    lam_sum = lam1 + lam2
    if lam_sum == 0:
        return 1/3, 1/3, 1/3
    p_j1 = (1 - p_empate) * (lam1 / lam_sum)
    p_j2 = (1 - p_empate) * (lam2 / lam_sum)
    return sanitize_prob(p_j1), sanitize_prob(p_empate), sanitize_prob(p_j2)

def handicaps_legs(v1, v2):
    denom = v1 * (1 - v2) + v2 * (1 - v1)
    if denom == 0:
        return {k: 0.5 for k in ["J1 -1.5 Legs", "J1 -2.5 Legs", "J1 +1.5 Legs", 
                                  "J1 +2.5 Legs", "J2 -1.5 Legs", "J2 -2.5 Legs",
                                  "J2 +1.5 Legs", "J2 +2.5 Legs"]}
    R = (v1 * (1 - v2)) / denom
    R2 = 1 - R
    return {
        "J1 -1.5 Legs": sanitize_prob(R * 0.75),
        "J1 -2.5 Legs": sanitize_prob(R * 0.50),
        "J1 +1.5 Legs": sanitize_prob(R + (1 - R) * 0.40),
        "J1 +2.5 Legs": sanitize_prob(R + (1 - R) * 0.70),
        "J2 -1.5 Legs": sanitize_prob(R2 * 0.75),
        "J2 -2.5 Legs": sanitize_prob(R2 * 0.50),
        "J2 +1.5 Legs": sanitize_prob(R2 + (1 - R2) * 0.40),
        "J2 +2.5 Legs": sanitize_prob(R2 + (1 - R2) * 0.70),
    }

def legs_totales(lam_legs1, lam_legs2):
    if lam_legs1 + lam_legs2 == 0:
        p = 0.5
    else:
        p = lam_legs1 / (lam_legs1 + lam_legs2)
    q = 1 - p
    prob_4_0_j1 = p ** 4
    prob_4_1_j1 = 4 * (p ** 4) * q
    prob_4_0_j2 = q ** 4
    prob_4_1_j2 = 4 * (q ** 4) * p
    prob_under_5_5 = prob_4_0_j1 + prob_4_1_j1 + prob_4_0_j2 + prob_4_1_j2
    prob_over_5_5 = 1 - prob_under_5_5
    return {
        "Más de 5.5": sanitize_prob(prob_over_5_5),
        "Menos de 5.5": sanitize_prob(prob_under_5_5)
    }

def prob_a_cuota(p):
    p_safe = sanitize_prob(p)
    cuota = 1.0 / p_safe
    return max(1.01, min(999.0, cuota))

def pct(p):
    return f"{p * 100:.1f}%"

def calcular_yield(prob, cuota_bookie):
    return (prob * cuota_bookie) - 1

def badge_yield(y):
    if y > 0:
        return f"✅ +{y*100:.1f}%"
    elif y < -0.05:
        return f"❌ {y*100:.1f}%"
    else:
        return f"➖ {y*100:.1f}%"

def _buscar_stat(stats_dict, keywords):
    for k, v in stats_dict.items():
        if any(kw in k.lower() for kw in keywords):
            return v
    return 0.0

def buscar_jugador(nombre, db):
    nombre_lower = nombre.strip().lower()
    if nombre_lower in db:
        return db[nombre_lower]
    for k, v in db.items():
        if nombre_lower in k or k in nombre_lower:
            return v
    return None

def render_barras_enfrentadas(j1_nombre, j1_prob, j2_nombre, j2_prob, j1_color="#1f77b4", j2_color="#ff7f0e"):
    total = j1_prob + j2_prob
    if total == 0:
        j1_prob = j2_prob = 0.5
    j1_pct = (j1_prob / total * 100) if total > 0 else 50
    j2_pct = (j2_prob / total * 100) if total > 0 else 50
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
            <div style="flex: 0 0 25%; text-align: right;">
                <p style="margin: 0; font-weight: bold; font-size: 1.1em; color: {j1_color};">{j1_nombre}</p>
                <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: bold; color: {j1_color};">{j1_pct:.1f}%</p>
            </div>
            <div style="flex: 1;">
                <div style="display: flex; height: 45px; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="width: {j1_pct}%; background: linear-gradient(90deg, {j1_color}, {j1_color}dd); display: flex; align-items: center; justify-content: flex-end; padding-right: 10px;">
                        <span style="color: white; font-weight: bold; font-size: 0.9em;">{j1_prob*100:.1f}%</span>
                    </div>
                    <div style="width: {j2_pct}%; background: linear-gradient(90deg, {j2_color}dd, {j2_color}); display: flex; align-items: center; justify-content: flex-start; padding-left: 10px;">
                        <span style="color: white; font-weight: bold; font-size: 0.9em;">{j2_prob*100:.1f}%</span>
                    </div>
                </div>
            </div>
            <div style="flex: 0 0 25%; text-align: left;">
                <p style="margin: 0; font-weight: bold; font-size: 1.1em; color: {j2_color};">{j2_nombre}</p>
                <p style="margin: 5px 0 0 0; font-size: 1.3em; font-weight: bold; color: {j2_color};">{j2_pct:.1f}%</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def mostrar_cuota_justa(cuota):
    st.caption(f"💡 Cuota justa: **{cuota:.2f}**")

def render_mas_180s_barras(j1_nombre, p_j1, j2_nombre, p_j2, p_emp, j1_color="#1f77b4", j2_color="#ff7f0e"):
    p_j1 = sanitize_prob(p_j1)
    p_j2 = sanitize_prob(p_j2)
    p_emp = sanitize_prob(p_emp)
    total = p_j1 + p_emp + p_j2
    if total <= 0:
        total = 1.0
    pct_j1 = (p_j1 / total * 100)
    pct_emp = (p_emp / total * 100)
    pct_j2 = (p_j2 / total * 100)
    html_str = f"""
    <div style="margin: 20px 0;">
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
            <div style="flex: 0 0 20%; text-align: right;">
                <p style="margin: 0; font-weight: bold; font-size: 0.95em; color: {j1_color};">{j1_nombre}</p>
                <p style="margin: 5px 0 0 0; font-size: 1.1em; font-weight: bold; color: {j1_color};">{pct_j1:.1f}%</p>
            </div>
            <div style="flex: 1;">
                <div style="display: flex; height: 45px; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="width: {pct_j1}%; background: linear-gradient(90deg, {j1_color}, {j1_color}dd); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">
                        <span style="color: white; font-weight: bold; font-size: 0.8em;">{p_j1*100:.1f}%</span>
                    </div>
                    <div style="width: {pct_emp}%; background: linear-gradient(90deg, #999, #777); display: flex; align-items: center; justify-content: center;">
                        <span style="color: white; font-weight: bold; font-size: 0.8em;">{p_emp*100:.1f}%</span>
                    </div>
                    <div style="width: {pct_j2}%; background: linear-gradient(90deg, {j2_color}dd, {j2_color}); display: flex; align-items: center; justify-content: flex-start; padding-left: 8px;">
                        <span style="color: white; font-weight: bold; font-size: 0.8em;">{p_j2*100:.1f}%</span>
                    </div>
                </div>
            </div>
            <div style="flex: 0 0 20%; text-align: left;">
                <p style="margin: 0; font-weight: bold; font-size: 0.95em; color: {j2_color};">{j2_nombre}</p>
                <p style="margin: 5px 0 0 0; font-size: 1.1em; font-weight: bold; color: {j2_color};">{pct_j2:.1f}%</p>
            </div>
        </div>
    </div>
    """
    st.markdown(html_str, unsafe_allow_html=True)

def render_pentagono_svg(pr, lam_180, promedio_dardos, checkouts, pct_vic, color="#1f77b4"):
    """Renderiza solo el SVG del pentágono sin los datos."""
    
    # Normalizar valores entre 0-100
    pr_norm = min(100, max(0, pr))
    lam_180_norm = min(100, max(0, (lam_180 / 3.0) * 100))
    promedio_dardos_norm = min(100, max(0, (promedio_dardos / 100) * 100))
    checkouts_norm = min(100, max(0, checkouts))
    pct_vic_norm = min(100, max(0, pct_vic))
    
    values = [pr_norm, lam_180_norm, promedio_dardos_norm, checkouts_norm, pct_vic_norm]
    labels = ["Power", "λ 180s", "Ø Dardos", "Checkout", "% Vic"]
    
    # SVG centrado perfecto
    svg_size = 340
    center_x, center_y = svg_size / 2, svg_size / 2
    radius = 90
    angle_offset = -90
    
    # Calcular puntos del pentágono base
    points = []
    label_pos = []
    for i in range(5):
        angle = angle_offset + (i * 72)
        rad = np.radians(angle)
        
        x = center_x + radius * np.cos(rad)
        y = center_y + radius * np.sin(rad)
        points.append((x, y))
        
        label_radius = radius + 30
        lx = center_x + label_radius * np.cos(rad)
        ly = center_y + label_radius * np.sin(rad)
        label_pos.append((lx, ly))
    
    # Calcular puntos de datos
    data_points = []
    for i in range(5):
        angle = angle_offset + (i * 72)
        rad = np.radians(angle)
        data_radius = (values[i] / 100) * radius
        x = center_x + data_radius * np.cos(rad)
        y = center_y + data_radius * np.sin(rad)
        data_points.append((x, y))
    
    svg_parts = []
    svg_parts.append(f'<svg width="{svg_size}" height="{svg_size}" xmlns="http://www.w3.org/2000/svg">')
    svg_parts.append(f'<rect width="{svg_size}" height="{svg_size}" fill="white"/>')
    
    # Círculos de referencia
    for r_pct in [25, 50, 75, 100]:
        r = (r_pct / 100) * radius
        svg_parts.append(f'<circle cx="{center_x}" cy="{center_y}" r="{r}" fill="none" stroke="rgba(200,200,200,0.25)" stroke-width="0.8"/>')
    
    # Líneas radiales
    for point in points:
        svg_parts.append(f'<line x1="{center_x}" y1="{center_y}" x2="{point[0]}" y2="{point[1]}" stroke="rgba(200,200,200,0.15)" stroke-width="0.8"/>')
    
    # Pentágono base
    pentagon_path = "M " + " L ".join([f"{p[0]},{p[1]}" for p in points]) + " Z"
    svg_parts.append(f'<path d="{pentagon_path}" fill="none" stroke="rgba(150,150,150,0.2)" stroke-width="1"/>')
    
    # Área de datos
    data_path = "M " + " L ".join([f"{p[0]},{p[1]}" for p in data_points]) + " Z"
    rgb_color = color.lstrip('#')
    rgb_tuple = tuple(int(rgb_color[i:i+2], 16) for i in (0, 2, 4))
    svg_parts.append(f'<path d="{data_path}" fill="rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.15)" stroke="{color}" stroke-width="2.5"/>')
    
    # Puntos de datos
    for point in data_points:
        svg_parts.append(f'<circle cx="{point[0]}" cy="{point[1]}" r="3.5" fill="{color}" stroke="white" stroke-width="1.5"/>')
    
    # Etiquetas
    for i, (x, y) in enumerate(label_pos):
        svg_parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" font-size="9" font-family="Arial" fill="#666" font-weight="500">{labels[i]}</text>')
    
    svg_parts.append('</svg>')
    
    return "\n".join(svg_parts)

def render_pentagono_habilidades(pr, lam_180, promedio_dardos, checkouts, pct_vic, color="#1f77b4"):
    """Renderiza pentágono con datos debajo."""
    
    valores_display = [f"{pr:.1f}", f"{lam_180:.2f}", f"{promedio_dardos:.1f}", f"{checkouts:.0f}%", f"{pct_vic:.0f}%"]
    svg_html = render_pentagono_svg(pr, lam_180, promedio_dardos, checkouts, pct_vic, color)
    
    rgb_color = color.lstrip('#')
    rgb_tuple = tuple(int(rgb_color[i:i+2], 16) for i in (0, 2, 4))
    
    # HTML para los datos debajo del pentágono
    html_datos = f"""
    <div style="margin-top: 10px;">
        {svg_html}
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 8px; margin-top: 20px; text-align: center;">
            <div style="background: rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.1); padding: 8px; border-radius: 6px; border-left: 3px solid {color};">
                <p style="margin: 0; font-size: 11px; color: #666;">Power</p>
                <p style="margin: 3px 0 0 0; font-size: 13px; font-weight: bold; color: {color};">{valores_display[0]}</p>
            </div>
            <div style="background: rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.1); padding: 8px; border-radius: 6px; border-left: 3px solid {color};">
                <p style="margin: 0; font-size: 11px; color: #666;">λ 180s</p>
                <p style="margin: 3px 0 0 0; font-size: 13px; font-weight: bold; color: {color};">{valores_display[1]}</p>
            </div>
            <div style="background: rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.1); padding: 8px; border-radius: 6px; border-left: 3px solid {color};">
                <p style="margin: 0; font-size: 11px; color: #666;">Ø Dardos</p>
                <p style="margin: 3px 0 0 0; font-size: 13px; font-weight: bold; color: {color};">{valores_display[2]}</p>
            </div>
            <div style="background: rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.1); padding: 8px; border-radius: 6px; border-left: 3px solid {color};">
                <p style="margin: 0; font-size: 11px; color: #666;">Checkout</p>
                <p style="margin: 3px 0 0 0; font-size: 13px; font-weight: bold; color: {color};">{valores_display[3]}</p>
            </div>
            <div style="background: rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.1); padding: 8px; border-radius: 6px; border-left: 3px solid {color};">
                <p style="margin: 0; font-size: 11px; color: #666;">% Vic</p>
                <p style="margin: 3px 0 0 0; font-size: 13px; font-weight: bold; color: {color};">{valores_display[4]}</p>
            </div>
        </div>
    </div>
    """
    
    return html_datos

def render_jugador_visual(player, stats, stats_resumen, selected, mostrar_tendencias=True):
    """Renderiza un jugador con tarjetas visuales y Puntuación Global destacada al final."""
    
    # Iconos por estadística
    iconos_stats = {
        "Media 180 por partida": "🎯",
        "Promedio puntos total": "📊",
        "Legs por partido": "🎮",
        "Promedio Checkouts": "✅",
        "Número victorias": "🏆",
        "Número derrotas": "❌",
        "Porcentaje victoria": "📈",
    }
    
    orden_stats = [
        "Media 180 por partida", "Promedio puntos total",
        "Legs por partido", "Promedio Checkouts", "Número victorias",
        "Número derrotas", "Porcentaje victoria"
    ]
    
    # Grid de tarjetas para estadísticas básicas
    cards_html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 10px 0 20px 0;">'
    
    for etiqueta in orden_stats:
        valor = "-"
        clave_encontrada = None
        for k, v in stats.items():
            if etiqueta.lower() in str(k).lower():
                valor = v
                clave_encontrada = k
                break
        
        if not clave_encontrada:
            continue
        
        icono = iconos_stats.get(etiqueta, "📌")
        
        # Tendencia (solo si no es Resumen Semanal y hay datos disponibles)
        indicador = ""
        comparativa = ""
        if mostrar_tendencias and stats_resumen and player in stats_resumen:
            valor_semanal = "-"
            for k_sem, v_sem in stats_resumen[player].items():
                if etiqueta.lower() in str(k_sem).lower():
                    valor_semanal = v_sem
                    break
            indicador, _, comparativa = calcular_tendencia(valor, valor_semanal, etiqueta)
        
        # Color según tipo de estadística
        if "derrota" in etiqueta.lower():
            color_borde = "#dc3545"
            color_valor = "#dc3545"
            bg_grad = "rgba(220, 53, 69, 0.08)"
        elif "victoria" in etiqueta.lower() or "checkout" in etiqueta.lower() or "180" in etiqueta:
            color_borde = "#28a745"
            color_valor = "#28a745"
            bg_grad = "rgba(40, 167, 69, 0.08)"
        else:
            color_borde = "#1f77b4"
            color_valor = "#1f77b4"
            bg_grad = "rgba(31, 119, 180, 0.08)"
        
        tend_html = (
            f'<span style="font-size: 11px; color: #888;">{indicador} {comparativa}</span>'
            if (indicador or comparativa) else ''
        )
        
        cards_html += f'''
        <div style="
            background: linear-gradient(135deg, {bg_grad} 0%, rgba(255,255,255,0.01) 100%);
            border-left: 3px solid {color_borde};
            border-radius: 8px;
            padding: 12px 15px;
        ">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span style="font-size: 18px;">{icono}</span>
                <span style="font-size: 12px; color: #888; font-weight: 600;">{etiqueta}</span>
            </div>
            <div style="display: flex; align-items: baseline; justify-content: space-between;">
                <span style="font-size: 22px; font-weight: bold; color: {color_valor};">{valor}</span>
                {tend_html}
            </div>
        </div>
        '''
    
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)
    
    # Otros datos no contemplados (excluyendo Puntuación Global)
    otros = []
    for k, v in stats.items():
        k_lower = str(k).lower()
        if any(etiqueta.lower() in k_lower for etiqueta in orden_stats):
            continue
        if "puntiación" in k_lower or "puntuación" in k_lower or "puntacion" in k_lower:
            continue
        otros.append((k, v))
    
    if otros:
        otros_html = '<div style="margin: 0 0 15px 0; padding: 10px 15px; background: rgba(120,120,120,0.05); border-radius: 6px; font-size: 13px;">'
        for k, v in otros:
            otros_html += f'<div style="margin: 3px 0;"><span style="color: #888;">{k}:</span> <strong>{v}</strong></div>'
        otros_html += '</div>'
        st.markdown(otros_html, unsafe_allow_html=True)
    
    # ⭐ Tarjeta destacada de Puntuación Global al final
    puntuacion_global_data = None
    for k, v in stats.items():
        k_lower = str(k).lower()
        if "puntiación" in k_lower or "puntuación" in k_lower or "puntacion" in k_lower:
            puntuacion_global_data = (k, v)
            break
    
    if puntuacion_global_data:
        k_pg, v_pg = puntuacion_global_data
        
        indicador_pg = ""
        comparativa_pg = ""
        if mostrar_tendencias and stats_resumen and player in stats_resumen:
            valor_semanal_pg = "-"
            for k_sem, v_sem in stats_resumen[player].items():
                k_sem_lower = str(k_sem).lower()
                if "puntiación" in k_sem_lower or "puntuación" in k_sem_lower or "puntacion" in k_sem_lower:
                    valor_semanal_pg = v_sem
                    break
            indicador_pg, _, comparativa_pg = calcular_tendencia(v_pg, valor_semanal_pg, k_pg)
        
        # Color y nivel según puntuación
        try:
            pg_num = float(str(v_pg).replace(',', '.').strip())
            if pg_num >= 75:
                color_pg, bg_color, nivel = "#28a745", "rgba(40, 167, 69, 0.15)", "Excelente"
            elif pg_num >= 50:
                color_pg, bg_color, nivel = "#ffc107", "rgba(255, 193, 7, 0.15)", "Bueno"
            elif pg_num >= 25:
                color_pg, bg_color, nivel = "#fd7e14", "rgba(253, 126, 20, 0.15)", "Regular"
            else:
                color_pg, bg_color, nivel = "#dc3545", "rgba(220, 53, 69, 0.15)", "Bajo"
        except:
            color_pg, bg_color, nivel = "#6c757d", "rgba(108, 117, 125, 0.15)", ""
        
        tend_pg_html = (
            f'<p style="margin: 4px 0 0 0; font-size: 13px; color: #888;">{indicador_pg} {comparativa_pg}</p>'
            if (indicador_pg or comparativa_pg) else ''
        )
        
        nivel_html = f"· {nivel}" if nivel else ""
        
        st.markdown(f'''
        <div style="
            background: linear-gradient(135deg, {bg_color} 0%, rgba(255,255,255,0.02) 100%);
            border: 2px solid {color_pg};
            border-radius: 12px;
            padding: 20px 24px;
            margin-top: 10px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        ">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
                <div style="display: flex; align-items: center; gap: 14px;">
                    <span style="font-size: 38px;">⭐</span>
                    <div>
                        <p style="margin: 0; font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600;">Puntuación Global</p>
                        <p style="margin: 3px 0 0 0; font-size: 11px; color: #aaa;">Rendimiento general (0-100) {nivel_html}</p>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 40px; font-weight: bold; color: {color_pg};">{v_pg}</span>
                    {tend_pg_html}
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

def render_value_bets():
    st.title("💰 Value Bets — Motor de Probabilidades")
    value_bets_list = []
    with st.expander("⚙️ Configuración", expanded=True):
        fuente = st.selectbox(
            "📂 Fuente de datos",
            PESTANAS_CON_STATS,
            index=PESTANAS_CON_STATS.index(st.session_state.vb_fuente),
            key="selector_fuente"
        )
        st.session_state.vb_fuente = fuente
    with st.spinner(f"Cargando datos de '{fuente}'..."):
        db_jugadores = cargar_jugadores_desde(fuente)
    if not db_jugadores:
        st.warning(f"⚠️ No se encontraron jugadores en '{fuente}'.")
        return
    nombres_disponibles = sorted([v["nombre_original"] for v in db_jugadores.values()])
    if fuente in st.session_state.last_update:
        tiempo_transcurrido = (datetime.now() - st.session_state.last_update[fuente]).seconds
        st.info(f"📊 {len(nombres_disponibles)} jugadores | ⏱️ Actualizado hace {tiempo_transcurrido}s")
    st.markdown("### 🥊 Seleccionar Enfrentamiento")
    if st.session_state.vb_j1 is None or st.session_state.vb_j1 not in nombres_disponibles:
        st.session_state.vb_j1 = nombres_disponibles[0]
    if st.session_state.vb_j2 is None or st.session_state.vb_j2 not in nombres_disponibles:
        opciones_j2 = [n for n in nombres_disponibles if n != st.session_state.vb_j1]
        st.session_state.vb_j2 = opciones_j2[0] if opciones_j2 else nombres_disponibles[0]
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        j1_sel = st.selectbox(
            "Jugador 1",
            nombres_disponibles,
            index=nombres_disponibles.index(st.session_state.vb_j1),
            key="sel_j1"
        )
        st.session_state.vb_j1 = j1_sel
    with col2:
        opciones_j2 = [n for n in nombres_disponibles if n != j1_sel]
        if st.session_state.vb_j2 not in opciones_j2:
            st.session_state.vb_j2 = opciones_j2[0] if opciones_j2 else nombres_disponibles[0]
        j2_sel = st.selectbox(
            "Jugador 2",
            opciones_j2,
            index=opciones_j2.index(st.session_state.vb_j2) if st.session_state.vb_j2 in opciones_j2 else 0,
            key="sel_j2"
        )
        st.session_state.vb_j2 = j2_sel
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔢 Calcular", type="primary", use_container_width=True, help="Calcular probabilidades"):
            st.session_state.vb_calcular = True
    if not st.session_state.vb_calcular:
        st.info("👆 Selecciona los jugadores y pulsa **Calcular**")
        return
    j1 = buscar_jugador(j1_sel, db_jugadores)
    j2 = buscar_jugador(j2_sel, db_jugadores)
    if not j1 or not j2:
        st.error("No se encontraron datos para uno de los jugadores.")
        return
    pr1, pr2     = j1["PR"],       j2["PR"]
    lam1, lam2   = j1["lam_180"],  j2["lam_180"]
    legs1, legs2 = j1["lam_legs"], j2["lam_legs"]
    st.markdown("---")
    st.markdown("### 📊 Comparativa de Jugadores")
    
    # Mostrar pentágonos lado a lado con Streamlit columns
    col_p1, col_vs, col_p2 = st.columns([1, 0.15, 1])
    
    with col_p1:
        st.markdown(f"<h3 style='text-align: center; color: #1f77b4;'>{j1['nombre_original']}</h3>", unsafe_allow_html=True)
        svg_j1 = render_pentagono_svg(pr1, lam1, j1["promedio_dardos"], j1["checkouts"], j1["pct_victorias"], color="#1f77b4")
        st.markdown(f"<div style='text-align: center;'>{svg_j1}</div>", unsafe_allow_html=True)
        
        # Datos en 5 columnas coloreados en azul
        dcols = st.columns(5)
        datos_j1 = [
            ("Power", f"{pr1:.1f}"),
            ("λ 180s", f"{lam1:.2f}"),
            ("Ø Dardos", f"{j1['promedio_dardos']:.1f}"),
            ("Checkout", f"{j1['checkouts']:.0f}%"),
            ("% Vic", f"{j1['pct_victorias']:.0f}%")
        ]
        for idx, (label, valor) in enumerate(datos_j1):
            with dcols[idx]:
                st.markdown(f"""
                <div style='text-align: center; padding: 10px; background: rgba(31, 119, 180, 0.1); border-radius: 6px; border-left: 3px solid #1f77b4;'>
                    <p style='margin: 0; font-size: 11px; color: #666;'>{label}</p>
                    <p style='margin: 5px 0 0 0; font-size: 18px; font-weight: bold; color: #1f77b4;'>{valor}</p>
                </div>
                """, unsafe_allow_html=True)
    
    with col_vs:
        st.markdown("""
        <div style='display: flex; align-items: center; justify-content: center; height: 100%; padding: 150px 0;'>
            <p style='font-size: 32px; font-weight: bold; color: #999; margin: 0;'>vs</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_p2:
        st.markdown(f"<h3 style='text-align: center; color: #ff7f0e;'>{j2['nombre_original']}</h3>", unsafe_allow_html=True)
        svg_j2 = render_pentagono_svg(pr2, lam2, j2["promedio_dardos"], j2["checkouts"], j2["pct_victorias"], color="#ff7f0e")
        st.markdown(f"<div style='text-align: center;'>{svg_j2}</div>", unsafe_allow_html=True)
        
        # Datos en 5 columnas coloreados en naranja
        dcols = st.columns(5)
        datos_j2 = [
            ("Power", f"{pr2:.1f}"),
            ("λ 180s", f"{lam2:.2f}"),
            ("Ø Dardos", f"{j2['promedio_dardos']:.1f}"),
            ("Checkout", f"{j2['checkouts']:.0f}%"),
            ("% Vic", f"{j2['pct_victorias']:.0f}%")
        ]
        for idx, (label, valor) in enumerate(datos_j2):
            with dcols[idx]:
                st.markdown(f"""
                <div style='text-align: center; padding: 10px; background: rgba(255, 127, 14, 0.1); border-radius: 6px; border-left: 3px solid #ff7f0e;'>
                    <p style='margin: 0; font-size: 11px; color: #666;'>{label}</p>
                    <p style='margin: 5px 0 0 0; font-size: 18px; font-weight: bold; color: #ff7f0e;'>{valor}</p>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🔥 Head to Head Semanal")
    with st.spinner("Analizando enfrentamientos directos..."):
        h2h = extraer_h2h_semanal(j1['nombre_original'], j2['nombre_original'])
    
    if h2h["partidos"]:
        # Head to Head con nombres prominentes
        html_h2h = f"""
        <div style="display: flex; justify-content: space-around; align-items: center; gap: 30px; margin: 30px 0;">
            <div style="text-align: center; flex: 1;">
                <h2 style="color: #1f77b4; margin: 0; font-size: 32px;">{j1['nombre_original']}</h2>
                <p style="color: #1f77b4; font-size: 48px; font-weight: bold; margin: 10px 0;">{h2h["victorias_j1"]}</p>
                <p style="color: #666; font-size: 14px; margin: 0;">Victorias H2H</p>
            </div>
            <div style="text-align: center; font-size: 28px; color: #999;">vs</div>
            <div style="text-align: center; flex: 1;">
                <h2 style="color: #ff7f0e; margin: 0; font-size: 32px;">{j2['nombre_original']}</h2>
                <p style="color: #ff7f0e; font-size: 48px; font-weight: bold; margin: 10px 0;">{h2h["victorias_j2"]}</p>
                <p style="color: #666; font-size: 14px; margin: 0;">Victorias H2H</p>
            </div>
        </div>
        """
        st.markdown(html_h2h, unsafe_allow_html=True)
        
        with st.expander("📋 Ver historial de enfrentamientos"):
            for partido in h2h["partidos"]:
                st.markdown(f"**{partido['dia']}**: {partido['jugador1']} vs {partido['jugador2']} - **{partido['marcador']}** (Ganador: {partido['ganador']})")
    else:
        st.info("ℹ️ No se encontraron enfrentamientos directos esta semana")
    v1, v2 = prob_victoria(pr1, pr2)
    m180 = prob_180s(lam1, lam2)
    p_j1_mas, p_emp, p_j2_mas = quien_hace_mas_180s(lam1, lam2)
    hcaps = handicaps_legs(v1, v2)
    legs_total_dict = legs_totales(legs1, legs2)
    st.markdown("---")
    st.markdown("### 🎲 Mercados Disponibles")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Victoria", "🎯 180s", "🥇 ¿Quién hace más 180?", "📐 Hándicaps", "📊 Total Legs"])
    with tab1:
        st.markdown("#### 🏆 Mercado de Victoria")
        render_barras_enfrentadas(j1['nombre_original'], v1, j2['nombre_original'], v2, j1_color="#1f77b4", j2_color="#ff7f0e")
        st.markdown("---")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown(f"<p style='color: #1f77b4; font-weight: bold;'>🎯 Gana {j1['nombre_original']}</p>", unsafe_allow_html=True)
            cuota_justa = prob_a_cuota(v1)
            mostrar_cuota_justa(cuota_justa)
            c1 = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="vic_j1", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{v1*100:.1f}% probabilidad")
            if c1 and c1 > 0:
                y = calcular_yield(v1, c1)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"Gana {j1['nombre_original']}", "Probabilidad": v1, "Cuota Justa": cuota_justa, "Cuota Bookie": c1, "Yield": y})
        with col_v2:
            st.markdown(f"<p style='color: #ff7f0e; font-weight: bold;'>🎯 Gana {j2['nombre_original']}</p>", unsafe_allow_html=True)
            cuota_justa = prob_a_cuota(v2)
            mostrar_cuota_justa(cuota_justa)
            c2 = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="vic_j2", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{v2*100:.1f}% probabilidad")
            if c2 and c2 > 0:
                y = calcular_yield(v2, c2)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"Gana {j2['nombre_original']}", "Probabilidad": v2, "Cuota Justa": prob_a_cuota(v2), "Cuota Bookie": c2, "Yield": y})
    with tab2:
        st.markdown("#### 🎯 Mercado de 180s (Distribución Poisson)")
        st.markdown(f"<h5 style='color: #1f77b4;'>{j1['nombre_original']}</h5>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**+0.5 180s** (Al menos 1 180)")
            cuota_justa = prob_a_cuota(m180["J1 +0.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j1_05", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['J1 +0.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["J1 +0.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} +0.5 180s", "Probabilidad": m180["J1 +0.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_b:
            st.markdown("**+1.5 180s** (Al menos 2 180s)")
            cuota_justa = prob_a_cuota(m180["J1 +1.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j1_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['J1 +1.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["J1 +1.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} +1.5 180s", "Probabilidad": m180["J1 +1.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        # Mercados negativos para J1
        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("**-0.5 180s** (Menos de 1 180)")
            prob_neg = 1 - m180["J1 +0.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j1_neg05", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} -0.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_d:
            st.markdown("**-1.5 180s** (Menos de 2 180s)")
            prob_neg = 1 - m180["J1 +1.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j1_neg15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} -1.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        st.markdown("---")
        st.markdown(f"<h5 style='color: #ff7f0e;'>{j2['nombre_original']}</h5>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**+0.5 180s** (Al menos 1 180)")
            cuota_justa = prob_a_cuota(m180["J2 +0.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j2_05", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['J2 +0.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["J2 +0.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} +0.5 180s", "Probabilidad": m180["J2 +0.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_b:
            st.markdown("**+1.5 180s** (Al menos 2 180s)")
            cuota_justa = prob_a_cuota(m180["J2 +1.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j2_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['J2 +1.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["J2 +1.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} +1.5 180s", "Probabilidad": m180["J2 +1.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        # Mercados negativos para J2
        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("**-0.5 180s** (Menos de 1 180)")
            prob_neg = 1 - m180["J2 +0.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j2_neg05", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} -0.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_d:
            st.markdown("**-1.5 180s** (Menos de 2 180s)")
            prob_neg = 1 - m180["J2 +1.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_j2_neg15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} -1.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        st.markdown("---")
        st.markdown("##### 🤝 Ambos Jugadores")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Ambos +1.5 180s**")
            cuota_justa = prob_a_cuota(m180["Ambos +1.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_ambos_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['Ambos +1.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["Ambos +1.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Ambos +1.5 180s", "Probabilidad": m180["Ambos +1.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_b:
            st.markdown("**Ambos +2.5 180s**")
            cuota_justa = prob_a_cuota(m180["Ambos +2.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_ambos_25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{m180['Ambos +2.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(m180["Ambos +2.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Ambos +2.5 180s", "Probabilidad": m180["Ambos +2.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        # Mercados negativos para Ambos
        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("**Ambos -1.5 180s** (Menos de 2 180s cada uno)")
            prob_neg = 1 - m180["Ambos +1.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_ambos_neg15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Ambos -1.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_d:
            st.markdown("**Ambos -2.5 180s** (Menos de 3 180s cada uno)")
            prob_neg = 1 - m180["Ambos +2.5"]
            cuota_justa = prob_a_cuota(prob_neg)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key=f"180_ambos_neg25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob_neg*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob_neg, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Ambos -2.5 180s", "Probabilidad": prob_neg, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
    with tab3:
        st.markdown("#### 🥇 ¿Quién hace más 180s?")
        render_mas_180s_barras(j1['nombre_original'], p_j1_mas, j2['nombre_original'], p_j2_mas, p_emp, j1_color="#1f77b4", j2_color="#ff7f0e")
        st.markdown("---")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(f"<p style='color: #1f77b4; font-weight: bold;'>{j1['nombre_original']}</p>", unsafe_allow_html=True)
            cuota_justa = prob_a_cuota(p_j1_mas)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota {j1['nombre_original']}", min_value=1.01, max_value=50.0, value=None, step=0.05, key="mas_j1", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{p_j1_mas*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(p_j1_mas, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"Más 180s: {j1['nombre_original']}", "Probabilidad": p_j1_mas, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_m2:
            st.markdown("**Empate**")
            cuota_justa = prob_a_cuota(p_emp)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota empate", min_value=1.01, max_value=50.0, value=None, step=0.05, key="mas_emp", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{p_emp*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(p_emp, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Empate 180s", "Probabilidad": p_emp, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_m3:
            st.markdown(f"<p style='color: #ff7f0e; font-weight: bold;'>{j2['nombre_original']}</p>", unsafe_allow_html=True)
            cuota_justa = prob_a_cuota(p_j2_mas)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota {j2['nombre_original']}", min_value=1.01, max_value=50.0, value=None, step=0.05, key="mas_j2", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{p_j2_mas*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(p_j2_mas, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"Más 180s: {j2['nombre_original']}", "Probabilidad": p_j2_mas, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
    with tab4:
        st.markdown("#### 🎯 Hándicaps 180 de Legs")
        
        # JUGADOR 1
        st.markdown(f"<h4 style='color: #1f77b4;'>{j1['nombre_original']}</h4>", unsafe_allow_html=True)
        
        # Hándicaps Positivos J1
        st.markdown("**Hándicaps Positivos**")
        col_pos_j1_1, col_pos_j1_2 = st.columns(2)
        with col_pos_j1_1:
            st.markdown("**+1.5 Legs**")
            prob = hcaps["J1 +1.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j1_pos_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} +1.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        with col_pos_j1_2:
            st.markdown("**+2.5 Legs**")
            prob = hcaps["J1 +2.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j1_pos_25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} +2.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        # Hándicaps Negativos J1
        st.markdown("**Hándicaps Negativos**")
        col_neg_j1_1, col_neg_j1_2 = st.columns(2)
        with col_neg_j1_1:
            st.markdown("**-1.5 Legs**")
            prob = hcaps["J1 -1.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j1_neg_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} -1.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        with col_neg_j1_2:
            st.markdown("**-2.5 Legs**")
            prob = hcaps["J1 -2.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j1_neg_25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j1['nombre_original']} -2.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        st.divider()
        
        # JUGADOR 2
        st.markdown(f"<h4 style='color: #ff7f0e;'>{j2['nombre_original']}</h4>", unsafe_allow_html=True)
        
        # Hándicaps Positivos J2
        st.markdown("**Hándicaps Positivos**")
        col_pos_j2_1, col_pos_j2_2 = st.columns(2)
        with col_pos_j2_1:
            st.markdown("**+1.5 Legs**")
            prob = hcaps["J2 +1.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j2_pos_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} +1.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        with col_pos_j2_2:
            st.markdown("**+2.5 Legs**")
            prob = hcaps["J2 +2.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j2_pos_25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} +2.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        # Hándicaps Negativos J2
        st.markdown("**Hándicaps Negativos**")
        col_neg_j2_1, col_neg_j2_2 = st.columns(2)
        with col_neg_j2_1:
            st.markdown("**-1.5 Legs**")
            prob = hcaps["J2 -1.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j2_neg_15", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} -1.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        
        with col_neg_j2_2:
            st.markdown("**-2.5 Legs**")
            prob = hcaps["J2 -2.5 Legs"]
            cuota_justa = prob_a_cuota(prob)
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="hcap_j2_neg_25", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{prob*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(prob, c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": f"{j2['nombre_original']} -2.5 Legs", "Probabilidad": prob, "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
    with tab5:
        st.markdown("#### 📊 Total Legs (First to 4)")
        render_barras_enfrentadas("Más de 5.5", legs_total_dict["Más de 5.5"], "Menos de 5.5", legs_total_dict["Menos de 5.5"], j1_color="#28a745", j2_color="#dc3545")
        st.markdown("---")
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.markdown("**Más de 5.5 Legs**")
            cuota_justa = prob_a_cuota(legs_total_dict["Más de 5.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="legs_mas", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{legs_total_dict['Más de 5.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(legs_total_dict["Más de 5.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Más de 5.5 Legs", "Probabilidad": legs_total_dict["Más de 5.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
        with col_l2:
            st.markdown("**Menos de 5.5 Legs**")
            cuota_justa = prob_a_cuota(legs_total_dict["Menos de 5.5"])
            mostrar_cuota_justa(cuota_justa)
            c = st.number_input(f"Tu cuota", min_value=1.01, max_value=50.0, value=None, step=0.05, key="legs_menos", label_visibility="collapsed", placeholder="Introduce cuota")
            st.caption(f"{legs_total_dict['Menos de 5.5']*100:.1f}% probabilidad")
            if c and c > 0:
                y = calcular_yield(legs_total_dict["Menos de 5.5"], c)
                yield_color = "🟢" if y > 0 else ("🔴" if y < -0.05 else "⚪")
                st.metric("Yield", f"{yield_color} {'+' if y > 0 else ''}{y*100:.1f}%")
                if y > 0:
                    value_bets_list.append({"Mercado": "Menos de 5.5 Legs", "Probabilidad": legs_total_dict["Menos de 5.5"], "Cuota Justa": cuota_justa, "Cuota Bookie": c, "Yield": y})
    if value_bets_list:
        st.markdown("---")
        st.markdown("### 💎 Resumen de Value Bets Encontradas")
        value_bets_list.sort(key=lambda x: x["Yield"], reverse=True)
        for vb in value_bets_list:
            yield_pct = vb["Yield"] * 100
            st.markdown(f"""
            <div style="
                border-left: 4px solid #28a745;
                padding: 15px;
                margin: 10px 0;
                background: linear-gradient(90deg, rgba(40,167,69,0.1) 0%, rgba(40,167,69,0.02) 100%);
                border-radius: 5px;
            ">
                <div style="display: grid; grid-template-columns: 3fr 1fr 1fr 1fr 1fr; gap: 15px; align-items: center;">
                    <div>
                        <p style="margin: 0; font-size: 1.1em; font-weight: bold; color: #333;">{vb["Mercado"]}</p>
                    </div>
                    <div style="text-align: center;">
                        <p style="margin: 0; font-size: 0.8em; color: #666;">Probabilidad</p>
                        <p style="margin: 0; font-size: 1.1em; font-weight: bold; color: #1f77b4;">{vb["Probabilidad"]*100:.1f}%</p>
                    </div>
                    <div style="text-align: center;">
                        <p style="margin: 0; font-size: 0.8em; color: #666;">Cuota Justa</p>
                        <p style="margin: 0; font-size: 1.1em; font-weight: bold;">{vb["Cuota Justa"]:.2f}</p>
                    </div>
                    <div style="text-align: center;">
                        <p style="margin: 0; font-size: 0.8em; color: #666;">Cuota Bookie</p>
                        <p style="margin: 0; font-size: 1.1em; font-weight: bold; color: #ff7f0e;">{vb["Cuota Bookie"]:.2f}</p>
                    </div>
                    <div style="text-align: center;">
                        <p style="margin: 0; font-size: 0.8em; color: #666;">Yield</p>
                        <p style="margin: 0; font-size: 1.3em; font-weight: bold; color: #28a745;">+{yield_pct:.1f}%</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.success(f"✅ Se encontraron **{len(value_bets_list)}** mercados con value positivo")
    else:
        st.info("ℹ️ No se encontraron value bets con las cuotas introducidas")

st.sidebar.title("🎯 MODUS SUPER SERIES")
st.sidebar.markdown("---")

opcion_principal = st.sidebar.radio(
    "Selecciona sección:",
    ["🔴 LIVE", "💰 VALUE BETS", "📊 RESULTADOS Y ESTADÍSTICAS"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Actualización")
st.sidebar.caption("Caché: 30 segundos")

if st.sidebar.button("♻️ Forzar Refresh", help="Recarga inmediata"):
    st.cache_data.clear()
    st.session_state.last_update = {}
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Ejecutar Script")

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyF0-GxHiaX4NW55-2UJt39a9V_aJhGXahq5NL5z2szpbFd7RdtKtr5ww7r852RAm2f/exec"

if st.sidebar.button("▶️ Ejecutar Actualización", type="primary", use_container_width=True, help="Ejecuta el script de actualización de datos"):
    with st.sidebar.spinner("🔄 Ejecutando script..."):
        try:
            # Intentar con GET primero (más compatible con Apps Script)
            response = requests.get(SCRIPT_URL, timeout=120)
            if response.status_code == 200:
                st.sidebar.success("✅ Script ejecutado correctamente")
                st.sidebar.info("📊 Los datos se actualizarán en breve...")
                st.balloons()
                time.sleep(2)
                st.cache_data.clear()
                st.session_state.last_update = {}
                st.rerun()
            else:
                st.sidebar.warning(f"⚠️ Respuesta HTTP {response.status_code}")
                st.sidebar.info("💡 El script podría estar ejecutándose. Intenta refrescar en 5 segundos.")
        except requests.exceptions.Timeout:
            st.sidebar.warning("⏱️ Tiempo de espera agotado (>120s)")
            st.sidebar.info("💡 El script está ejecutándose en segundo plano. Los datos se actualizarán en breve.")
        except requests.exceptions.ConnectionError:
            st.sidebar.error("🔗 Error de conexión")
            st.sidebar.error("Verifica tu conexión a internet y que el script sea público")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
            st.sidebar.info("📝 Verifica que el script esté publicado como web app")

st.sidebar.divider()

if "🔴 LIVE" in opcion_principal:
    st.title("🔴 LIVE")
    jornada_actual, url_actual, es_activa = get_jornada_actual()
    
    # Cargar resumen semanal para comparativas (solo si hay jornada activa)
    stats_resumen_live = None
    if es_activa and jornada_actual and jornada_actual != "Resumen Semanal":
        _, stats_resumen_live = cargar_todo(URLS["Resumen Semanal"], "Resumen Semanal", CORTES.get("Resumen Semanal", 2))
    
    if es_activa and jornada_actual:
        st.success(f"✅ Jornada activa: **{jornada_actual}** (datos en tiempo real)")
        st.markdown("---")
        
        d1, d2 = cargar_todo(url_actual, jornada_actual, CORTES.get(jornada_actual, 2))
        if jornada_actual in st.session_state.last_update:
            tiempo = (datetime.now() - st.session_state.last_update[jornada_actual]).seconds
            st.caption(f"⏱️ Datos actualizados hace {tiempo} segundos")
        
        if d2 is not None:
            st.subheader("📈 Estadísticas por Jugador")
            for player, stats in d2.items():
                bandera = obtener_bandera(player)
                player_display = f"{bandera} {player.title()}" if bandera else f"👤 {player.title()}"
                with st.expander(player_display, expanded=False):
                    render_jugador_visual(player, stats, stats_resumen_live, jornada_actual, mostrar_tendencias=True)
        
        if d1 is not None:
            st.subheader("⚔️ Partidos")
            st.dataframe(d1.style.apply(pintar_partidos, axis=1), use_container_width=True, hide_index=True)
    else:
        proxima, url_proxima = get_proxima_jornada()
        st.info(f"📅 **Próxima jornada:** {proxima}")
        st.markdown("---")
        d1, d2 = cargar_todo(url_proxima, proxima, CORTES.get(proxima, 2))
        if proxima in st.session_state.last_update:
            tiempo = (datetime.now() - st.session_state.last_update[proxima]).seconds
            st.caption(f"⏱️ Datos actualizados hace {tiempo} segundos")
        
        if d2 is not None:
            st.subheader("📈 Estadísticas")
            for player, stats in d2.items():
                bandera = obtener_bandera(player)
                player_display = f"{bandera} {player.title()}" if bandera else f"👤 {player.title()}"
                with st.expander(player_display, expanded=False):
                    render_jugador_visual(player, stats, None, proxima, mostrar_tendencias=False)
        
        if d1 is not None:
            st.subheader("⚔️ Partidos")
            st.dataframe(d1.style.apply(pintar_partidos, axis=1), use_container_width=True, hide_index=True)

elif "💰 VALUE BETS" in opcion_principal:
    render_value_bets()

elif "📊 RESULTADOS Y ESTADÍSTICAS" in opcion_principal:
    st.title("📊 RESULTADOS Y ESTADÍSTICAS")
    jornadas_dict = {
        "Grupo A Lunes": URLS["Grupo A Lunes"],
        "Grupo A Martes": URLS["Grupo A Martes"],
        "Grupo A Miércoles": URLS["Grupo A Miércoles"],
        "Grupo C Jueves": URLS["Grupo C Jueves"],
        "Grupo C Viernes": URLS["Grupo C Viernes"],
        "Grupo B Jueves": URLS["Grupo B Jueves"],
        "Grupo B Viernes": URLS["Grupo B Viernes"],
        "Final Sábado": URLS["Final Sábado"],
        "Resumen Semanal": URLS["Resumen Semanal"],
    }
    selected = st.selectbox("Selecciona una jornada:", list(jornadas_dict.keys()), key="jornada_select")
    selected_url = jornadas_dict[selected]
    st.markdown("---")
    d1, d2 = cargar_todo(selected_url, selected, CORTES.get(selected, 2))
    
    if selected in st.session_state.last_update:
        tiempo = (datetime.now() - st.session_state.last_update[selected]).seconds
        st.caption(f"⏱️ Datos actualizados hace {tiempo} segundos")
    
    if d2 is not None:
        st.subheader("📈 Estadísticas por Jugador")
        
        # Cargar resumen semanal solo si estamos viendo otra jornada
        stats_resumen = None
        mostrar_tendencias = selected != "Resumen Semanal"
        if mostrar_tendencias:
            _, stats_resumen = cargar_todo(URLS["Resumen Semanal"], "Resumen Semanal", CORTES.get("Resumen Semanal", 2))
        
        for player, stats in d2.items():
            bandera = obtener_bandera(player)
            player_display = f"{bandera} {player.title()}" if bandera else f"👤 {player.title()}"
            with st.expander(player_display, expanded=False):
                render_jugador_visual(player, stats, stats_resumen, selected, mostrar_tendencias=mostrar_tendencias)
    
    if d1 is not None:
        st.subheader("⚔️ Detalles")
        if selected not in ["Resumen Semanal", "Value Bets"]:
            st.dataframe(d1.style.apply(pintar_partidos, axis=1), use_container_width=True, hide_index=True)
        else:
            st.dataframe(d1, use_container_width=True, hide_index=True)
