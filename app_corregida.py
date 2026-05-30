"""
app_corregida.py - Punto de entrada de Modus Super Series App.

Configura la pagina, inicializa el estado de sesion y construye la interfaz
principal (barra lateral + las tres secciones: LIVE, VALUE BETS y RESULTADOS).

La logica esta repartida en modulos:
  - config.py         constantes y configuracion
  - helpers.py        utilidades de bajo nivel
  - data_loading.py   carga y parsing de Google Sheets
  - stats_engine.py   modelo matematico y simulacion
  - rendering.py      renderizado visual
  - clasificacion.py  tablas de clasificacion

Para que Streamlit Cloud lo despliegue, este archivo sigue siendo el main.
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Modus Super Series App", layout="wide", page_icon="🎯")

# CSS global: rejilla de estadísticas responsive
# Desktop/tablet: 4 columnas | Móvil (<=768px): 2 columnas
st.markdown("""
<style>
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin: 10px 0 20px 0;
}
@media (max-width: 768px) {
    .stats-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
    }
}
</style>
""", unsafe_allow_html=True)


# ---- Imports de los modulos de la app ----
from config import URLS, CORTES
from data_loading import cargar_todo, get_jornada_actual, get_proxima_jornada
from helpers import pintar_partidos
from rendering import (
    render_jugador_visual, render_value_bets, render_small_multiples,
    selector_jornada, render_tracking_predicciones, render_historico,
)
from clasificacion import (
    detectar_grupo, construir_grupos_final,
    render_clasificacion_grupo, render_clasificacion_final,
)


# ---- Inicializacion del estado de sesion ----
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


st.sidebar.title("🎯 MODUS SUPER SERIES")

# ── Estado de la jornada actual ─────────────────────────────────────────
# Mostramos un indicador del estado del torneo en este momento, para tener
# contexto sin necesidad de cambiar de seccion. Si la deteccion falla, no
# mostramos nada — no rompemos el sidebar por un error de carga.
try:
    from data_loading import (
        detectar_jornada_de_hoy as _det_jornada,
        proxima_jornada as _prox_jornada,
    )
    _jornada_hoy = _det_jornada()
    if _jornada_hoy:
        st.sidebar.success(f"📅 Hoy: **{_jornada_hoy}**")
    else:
        try:
            _nom, _hora, _dia = _prox_jornada()
        except Exception:
            _nom = None
        if _nom:
            st.sidebar.info(
                f"📅 Sin jornada activa\n\n"
                f"⏭️ Próxima: **{_nom}**\n\n"
                f"🕒 {_dia} a las {_hora}"
            )
        else:
            st.sidebar.info("📅 Sin jornada activa")
except Exception:
    pass

st.sidebar.markdown("---")

# ── Menu de secciones (radio unico, fiable) ──────────────────────────────
# Los emojis ya dan pista del tipo: 🔴💰📊 son del dia a dia,
# 📈📚 son de analisis tranquilo. Antes lo separabamos en dos radios pero
# eso producia un bug intermitente al cambiar de seccion.
opcion_principal = st.sidebar.radio(
    "Selecciona sección:",
    ["🔴 LIVE", "💰 VALUE BETS", "📊 RESULTADOS Y ESTADÍSTICAS",
     "📈 SEGUIMIENTO", "📚 HISTÓRICO"],
    label_visibility="collapsed",
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

if st.sidebar.button("▶️ Ejecutar Actualización", help="Ejecuta el script de actualización de datos"):
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

    # Determinar qué jornada mostrar (activa o próxima si no hay actividad)
    if es_activa and jornada_actual:
        selected = jornada_actual
        selected_url = url_actual
        st.success(f"✅ Jornada activa: **{selected}** (datos en tiempo real)")
        mostrar_tendencias_live = True
        stats_resumen_para_render = stats_resumen_live
    else:
        selected, selected_url = get_proxima_jornada()
        st.info(f"📅 **Próxima jornada:** {selected}")
        mostrar_tendencias_live = False
        stats_resumen_para_render = None

    st.markdown("---")
    d1, d2 = cargar_todo(selected_url, selected, CORTES.get(selected, 2))

    if selected in st.session_state.last_update:
        tiempo = (datetime.now() - st.session_state.last_update[selected]).seconds
        st.caption(f"⏱️ Datos actualizados hace {tiempo} segundos")

    # Bloque idéntico al de Resultados y Estadísticas:
    # 1) Cards de jugadores con tendencias
    # 2) Tabla de partidos
    # 3) Ranking por métrica (small multiples)
    # 4) Clasificación del grupo (si la jornada pertenece a un grupo)

    if d2 is not None:
        st.subheader("📈 Estadísticas por Jugador")
        for player, stats in d2.items():
            player_display = f"👤 {player.title()}"
            with st.expander(player_display, expanded=False):
                render_jugador_visual(
                    player, stats, stats_resumen_para_render, selected,
                    mostrar_tendencias=mostrar_tendencias_live
                )

    if d1 is not None:
        st.subheader("⚔️ Detalles")
        if selected not in ["Resumen Semanal", "Value Bets"]:
            st.dataframe(d1.style.apply(pintar_partidos, axis=1), use_container_width=True, hide_index=True)
        else:
            st.dataframe(d1, use_container_width=True, hide_index=True)

    # Ranking por métrica (sin heatmap): small multiples con Puntuación Global destacada
    if d2 is not None and len(d2) > 0:
        st.markdown("---")
        render_small_multiples(d2, titulo="📊 Ranking por Métrica")

    # Clasificación del grupo (al final del todo)
    grupo_actual_live = detectar_grupo(selected)
    if grupo_actual_live:
        st.markdown("---")
        render_clasificacion_grupo(grupo_actual_live)
    elif selected == "Final Sábado":
        # En Final Sábado renderizamos los DOS grupos de la final (A y B),
        # compuestos según los rankings de la fase de grupos.
        grupos_final = construir_grupos_final()
        st.markdown("---")
        st.subheader("🏆 Grupos de la Final")
        for nombre_grupo, jugadores in grupos_final.items():
            render_clasificacion_final(nombre_grupo, jugadores)
            st.markdown("")
    elif selected == "Resumen Semanal":
        # En Resumen Semanal seguimos mostrando las 3 clasificaciones semanales
        st.markdown("---")
        st.subheader("🏆 Clasificaciones por Grupo")
        for g in ("Grupo A", "Grupo B", "Grupo C"):
            render_clasificacion_grupo(g)
            st.markdown("")

elif "💰 VALUE BETS" in opcion_principal:
    render_value_bets()

elif "📊 RESULTADOS Y ESTADÍSTICAS" in opcion_principal:
    st.title("📊 RESULTADOS Y ESTADÍSTICAS")
    with st.expander("⚙️ Configuración", expanded=True):
        st.markdown("**📂 Selecciona jornada**")
        selected = selector_jornada("res", incluir_resumen=True,
                                    modo_forma_reciente=False)
    selected_url = URLS[selected]
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
            player_display = f"👤 {player.title()}"
            with st.expander(player_display, expanded=False):
                render_jugador_visual(player, stats, stats_resumen, selected, mostrar_tendencias=mostrar_tendencias)
    
    if d1 is not None:
        st.subheader("⚔️ Detalles")
        if selected not in ["Resumen Semanal", "Value Bets"]:
            st.dataframe(d1.style.apply(pintar_partidos, axis=1), use_container_width=True, hide_index=True)
        else:
            st.dataframe(d1, use_container_width=True, hide_index=True)

    # Ranking por métrica (sin heatmap): small multiples con Puntuación Global destacada
    if d2 is not None and len(d2) > 0:
        st.markdown("---")
        render_small_multiples(d2, titulo="📊 Ranking por Métrica")

    # Clasificación del grupo (al final del todo)
    grupo_actual = detectar_grupo(selected)
    if grupo_actual:
        st.markdown("---")
        render_clasificacion_grupo(grupo_actual)
    elif selected == "Final Sábado":
        # En Final Sábado renderizamos los DOS grupos de la final (A y B),
        # compuestos según los rankings de la fase de grupos.
        grupos_final = construir_grupos_final()
        st.markdown("---")
        st.subheader("🏆 Grupos de la Final")
        for nombre_grupo, jugadores in grupos_final.items():
            render_clasificacion_final(nombre_grupo, jugadores)
            st.markdown("")
    elif selected == "Resumen Semanal":
        # En Resumen Semanal mostramos las 3 clasificaciones semanales completas
        st.markdown("---")
        st.subheader("🏆 Clasificaciones por Grupo")
        for g in ("Grupo A", "Grupo B", "Grupo C"):
            render_clasificacion_grupo(g)
            st.markdown("")


elif "📈 SEGUIMIENTO" in opcion_principal:
    st.title("📈 Seguimiento del modelo")
    render_tracking_predicciones()

elif "📚 HISTÓRICO" in opcion_principal:
    st.title("📚 Histórico de jugadores")
    # Jugadores del Resumen Semanal para el boton de guardar la semana.
    try:
        from data_loading import cargar_jugadores_desde
        jugadores_resumen_hist = cargar_jugadores_desde("Resumen Semanal")
    except Exception:
        jugadores_resumen_hist = None
    try:
        from predicciones import cargar_historico
        df_hist = cargar_historico()
    except Exception as e:
        df_hist = None
        st.error(f"No se pudo cargar el histórico: {e}")
    render_historico(df_hist, jugadores_resumen_hist)
