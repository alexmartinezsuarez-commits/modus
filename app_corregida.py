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
}

JUGADORES_PAISES = {
    "luke littler": "GB", "gary anderson": "GB", "peter wright": "GB", "gerwyn price": "GB",
    "jonny clayton": "GB", "james wade": "GB", "dave chisnall": "GB", "rob cross": "GB",
    "nathan aspinall": "GB", "chris dobey": "GB", "josh rock": "GB", "luke humphries": "GB",
    "michael smith": "GB", "ross smith": "GB", "stephen bunting": "GB", "joe cullen": "GB",
    "danny noppert": "NL", "michiel kiemeneij": "NL", "wessel nijman": "NL", "dirk van duijvenbode": "NL",
    "kevin doets": "NL", "jelle klaasen": "NL", "maik kuivenhoven": "NL",
    "dimitri van den bergh": "BE", "mike de decker": "BE",
    "jose de sousa": "PT", "noa lynn": "PT",
    "kyle anderson": "GB", "dave clayton": "GB", "joe murnan": "GB",
    "andrew gilding": "GB", "lewis williams": "GB", "brendan dolan": "GB",
}

@st.cache_data(ttl=30)
def cargar_datos(url):
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def obtener_bandera(nombre):
    nombre_lower = nombre.lower()
    pais = JUGADORES_PAISES.get(nombre_lower, "ES")
    return BANDERAS.get(pais, "🇪🇸")

def prob_victoria(pr1, pr2):
    if pr1 == 0 or pr2 == 0:
        return 0.5
    ratio = pr1 / pr2
    return ratio**4.5 / (1 + ratio**4.5)

def prob_180s(lam1, lam2):
    return poisson.pmf(1, lam1) + poisson.pmf(2, lam1) + poisson.pmf(3, lam1)

def handicaps_legs(v1, v2):
    return {"+1.5": (v1 + 1.5) / 4, "-1.5": v1 / 4, "+2.5": (v1 + 2.5) / 4, "-2.5": v1 / 4}

def legs_totales(lam1, lam2):
    total_dardos = (lam1 + lam2) / 2
    expected_legs = min(int(total_dardos / 18) + 1, 7)
    return max(3, expected_legs)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - CONTROL
# ═══════════════════════════════════════════════════════════════

st.sidebar.markdown("# 🎯 MODUS SUPER SERIES")
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Actualización")

if st.sidebar.button("♻️ Forzar Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Ejecutar Script")

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwNQnY-jfmOGZSN0D1cNPFyijkNtrzWSBzUs0mByzQl0mCDRvhn6MOMInDZ9yXw0cf9/exec"

if st.sidebar.button("▶️ Ejecutar Actualización", type="primary", use_container_width=True):
    st.sidebar.info("🔄 Ejecutando script...")
    try:
        response = requests.post(SCRIPT_URL, timeout=120)
        if response.status_code == 200:
            st.sidebar.success("✅ Script ejecutado correctamente")
            st.balloons()
            time.sleep(2)
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.warning(f"⚠️ Respuesta HTTP {response.status_code}")
    except requests.exceptions.Timeout:
        st.sidebar.warning("⏱️ Script ejecutándose en segundo plano")
    except Exception as e:
        st.sidebar.error(f"❌ Error: {str(e)}")

# ═══════════════════════════════════════════════════════════════
# PESTAÑAS PRINCIPALES
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs(["🔴 LIVE", "💰 VALUE BETS", "📊 RESULTADOS Y ESTADÍSTICAS"])

with tab1:
    st.markdown("## 🔴 LIVE - Partidos en Directo")
    
    ahora = datetime.now()
    dia_semana = ahora.weekday()
    hora = ahora.hour
    
    nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    if dia_semana < 3:
        jornada_actual = f"Grupo A {nombres_dias[dia_semana]}"
    elif dia_semana == 3 or dia_semana == 4:
        if hora < 13:
            jornada_actual = f"Grupo C {nombres_dias[dia_semana]}"
        elif hora < 22:
            jornada_actual = f"Grupo C {nombres_dias[dia_semana]}"
        else:
            jornada_actual = f"Grupo B {nombres_dias[dia_semana]}"
    elif dia_semana == 5:
        jornada_actual = "Final Sábado"
    else:
        jornada_actual = "Próxima jornada: Grupo A Lunes"
    
    st.info(f"📋 Próxima jornada: {jornada_actual}")
    
    ahora_timestamp = datetime.now().timestamp()
    if 'last_update' not in st.session_state:
        st.session_state.last_update = {}
    
    segundos_atras = int(ahora_timestamp - st.session_state.last_update.get('timestamp', ahora_timestamp))
    st.caption(f"⏰ Datos actualizados hace {segundos_atras} segundos")

with tab2:
    st.markdown("## 💰 VALUE BETS - Análisis de Cuotas")
    
    if 'vb_j1' not in st.session_state:
        st.session_state.vb_j1 = ""
    if 'vb_j2' not in st.session_state:
        st.session_state.vb_j2 = ""
    if 'vb_calcular' not in st.session_state:
        st.session_state.vb_calcular = False
    
    df_vb = cargar_datos(URLS["Value Bets"])
    nombres_disponibles = list(set([n.strip() for n in df_vb.iloc[:, 0] if isinstance(n, str) and n.strip()]))[:20]
    
    if not nombres_disponibles:
        st.warning("No hay datos disponibles")
    else:
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            j1_sel = st.selectbox(
                "Jugador 1",
                nombres_disponibles,
                index=nombres_disponibles.index(st.session_state.vb_j1) if st.session_state.vb_j1 in nombres_disponibles else 0,
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
            if st.button("🔢 Calcular", type="primary", use_container_width=True):
                st.session_state.vb_calcular = True
        
        st.divider()
        
        col_cuota1, col_cuota2 = st.columns(2)
        
        with col_cuota1:
            st.markdown(f"### {j1_sel}")
            cuota_j1 = st.number_input(f"Cuota para {j1_sel}", min_value=1.0, max_value=100.0, value=1.5, step=0.01, key="cuota_j1")
        
        with col_cuota2:
            st.markdown(f"### {j2_sel}")
            cuota_j2 = st.number_input(f"Cuota para {j2_sel}", min_value=1.0, max_value=100.0, value=2.5, step=0.01, key="cuota_j2")
        
        st.divider()
        
        if st.session_state.vb_calcular and cuota_j1 > 0 and cuota_j2 > 0:
            
            pr1 = 100
            pr2 = 85
            
            prob_1 = prob_victoria(pr1, pr2)
            prob_2 = 1 - prob_1
            
            yield_1 = (prob_1 * cuota_j1) - 1
            yield_2 = (prob_2 * cuota_j2) - 1
            
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.metric(
                    f"Victoria {j1_sel}",
                    f"{yield_1:.2%}",
                    delta="Value" if yield_1 > 0 else "No Value",
                    delta_color="normal" if yield_1 > 0 else "inverse"
                )
            
            with col_right:
                st.metric(
                    f"Victoria {j2_sel}",
                    f"{yield_2:.2%}",
                    delta="Value" if yield_2 > 0 else "No Value",
                    delta_color="normal" if yield_2 > 0 else "inverse"
                )
            
            st.divider()
            
            st.markdown("### 📊 Probabilidades")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{j1_sel}:** {prob_1:.1%}")
            with col2:
                st.write(f"**{j2_sel}:** {prob_2:.1%}")

with tab3:
    st.markdown("## 📊 RESULTADOS Y ESTADÍSTICAS")
    
    jornadas = [k for k in URLS.keys() if k not in ("Value Bets", "Resumen Semanal")]
    jornada_selec = st.selectbox("Selecciona jornada:", jornadas, index=0)
    
    if jornada_selec:
        df = cargar_datos(URLS[jornada_selec])
        
        if not df.empty:
            st.markdown(f"### {jornada_selec}")
            
            config = CORTES.get(jornada_selec)
            if config:
                if "unica_filas" in config:
                    inicio, fin = config["unica_filas"]
                    cols_range = config["unica_cols"]
                    datos = df.iloc[inicio:fin, cols_range[0]:cols_range[1]]
                    st.dataframe(datos, use_container_width=True)
                else:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### Estadísticas Detalladas")
                        if "izq_filas" in config:
                            inicio, fin = config["izq_filas"]
                            cols_range = config["izq_cols"]
                            datos_izq = df.iloc[inicio:fin, cols_range[0]:cols_range[1]]
                            st.dataframe(datos_izq, use_container_width=True)
                    
                    with col2:
                        st.markdown("#### Resumen")
                        if "der_nombres" in config:
                            nombres_fila = config["der_nombres"]
                            cols_range = config["der_cols"]
                            datos_der = df.iloc[nombres_fila:nombres_fila+10, cols_range[0]:cols_range[1]]
                            st.dataframe(datos_der, use_container_width=True)
        else:
            st.warning(f"No hay datos disponibles para {jornada_selec}")

st.markdown("---")
st.caption("🎯 Modus Super Series Analytics | Última actualización: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
