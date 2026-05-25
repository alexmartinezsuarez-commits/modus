"""
rendering.py - Funciones de renderizado visual de la interfaz Streamlit.

Pentagonos de habilidades, tarjetas de estadisticas de jugador, barras
comparativas, heatmaps, radares y la vista completa de Value Bets.

Depende de: config, helpers, data_loading, stats_engine.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from config import URLS, CORTES, PESTANAS_CON_STATS
from helpers import (
    safe_float, color_volatilidad, calcular_tendencia, sanitize_prob,
    buscar_jugador, calcular_yield, pct, badge_yield, obtener_bandera,
)
from data_loading import (
    cargar_todo, cargar_jugadores_desde, obtener_proximos_partidos_api,
)
from stats_engine import (
    prob_victoria, prob_180s, quien_hace_mas_180s, handicaps_legs,
    legs_totales, prob_a_cuota, extraer_h2h_semanal, obtener_ultimos_partidos,
    _extraer_metricas_jugadores,
)

# El modulo de seguimiento de predicciones es OPCIONAL: si falta el archivo
# o alguna de sus dependencias (gspread, google-auth), la app debe seguir
# funcionando con normalidad y solo se desactiva la seccion de tracking.
try:
    from predicciones import (
        registrar_predicciones, cargar_predicciones, calcular_metricas,
        tracking_disponible, diagnostico_conexion, verificar_resultados,
    )
    _PREDICCIONES_OK = True
    _PREDICCIONES_ERROR = ""
except Exception as _e:
    _PREDICCIONES_OK = False
    _PREDICCIONES_ERROR = f"{type(_e).__name__}: {_e}"
    registrar_predicciones = None
    cargar_predicciones = None
    calcular_metricas = None
    tracking_disponible = None
    diagnostico_conexion = None
    verificar_resultados = None

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
    """Renderiza un jugador con 9 estadísticas en un layout simétrico:
    
        ┌─────────────────────────────────────────────┐
        │       ⭐ PUNTUACIÓN GLOBAL (destacada)        │   ← fila completa
        └─────────────────────────────────────────────┘
        ┌──────────┬──────────┬──────────┬──────────┐
        │ Media 180│ Promedio │   Legs   │ Checkout │   ← fila 1 del grid
        ├──────────┼──────────┼──────────┼──────────┤
        │ Victorias│ Derrotas │ % Victor.│Volatilid.│   ← fila 2 del grid
        └──────────┴──────────┴──────────┴──────────┘
    
    Puntuación Global se destaca en la parte superior con borde grueso dorado,
    fondo degradado y tamaño tipográfico mayor — refleja su importancia como
    métrica clave compuesta.
    
    El Índice de Volatilidad se colorea según el riesgo:
        - Verde (< 8)      → riesgo bajo (rendimiento estable)
        - Amarillo (8-12)  → riesgo medio
        - Rojo (> 12)      → riesgo alto (rendimiento irregular)
    
    Colores estándar: azul por defecto, verde victorias, rojo derrotas, dorado
    puntuación global, traffic-light para volatilidad.
    
    Sistema de sinónimos: cada etiqueta tiene varias formas posibles para que
    funcione tanto con las jornadas diarias (etiquetas largas) como con el
    Resumen Semanal (etiquetas más cortas).
    """
    
    # Configuración: (etiqueta_display, icono, sinónimos_de_más_específico_a_más_genérico)
    # Orden:
    #   - Puntuación Global primero (se renderiza destacada arriba)
    #   - Luego las 8 restantes en grid 2×4
    config_stats = [
        ("Puntuación Global", "⭐",
         ["puntiación global", "puntuación global", "puntacion global", "puntiación", "puntuación", "puntacion"]),
        ("Media 180 por partida", "🎯",
         ["media 180 por partida", "180 por partida", "180 por partido", "media 180", "media de 180"]),
        ("Promedio puntos total", "📊",
         ["promedio puntos total", "promedio puntos", "media puntos", "puntos total", "promedio dardos", "average"]),
        ("Legs por partido", "🎮",
         ["legs totales", "total legs", "legs por partido", "leg por partido"]),
        ("Promedio Checkouts", "✅",
         ["promedio checkouts", "promedio checkout", "checkouts", "checkout"]),
        ("Número victorias", "🏆",
         ["número victorias", "numero victorias", "n. victorias", "n victorias", "victorias"]),
        ("Número derrotas", "❌",
         ["número derrotas", "numero derrotas", "n. derrotas", "n derrotas", "derrotas"]),
        ("Porcentaje victoria", "📈",
         ["porcentaje victoria", "porcentaje de victoria", "% victoria", "%victoria", "porc. victoria"]),
        ("Índice Volatilidad", "🎲",
         ["índice volatilidad", "indice volatilidad", "índice de volatilidad", "volatilidad"]),
    ]
    
    def buscar_valor(stats_dict, sinonimos, claves_excluidas):
        """Busca el primer match (forward only) en stats_dict para alguno de los sinónimos.
        Los sinónimos se prueban en orden, de más específicos a más genéricos.
        """
        for syn in sinonimos:
            syn_lower = syn.lower()
            for k, v in stats_dict.items():
                if k in claves_excluidas:
                    continue
                k_lower = str(k).lower().strip()
                if not k_lower:
                    continue
                if syn_lower in k_lower:
                    return k, v
        return None, "-"
    
    # Match case-insensitive del jugador en stats_resumen
    # (las jornadas diarias guardan nombres con mayúsculas, el resumen en minúsculas)
    stats_jugador_resumen = None
    if mostrar_tendencias and stats_resumen:
        if player in stats_resumen:
            stats_jugador_resumen = stats_resumen[player]
        else:
            player_lower = str(player).lower().strip()
            for k_resumen, v_resumen in stats_resumen.items():
                if str(k_resumen).lower().strip() == player_lower:
                    stats_jugador_resumen = v_resumen
                    break
    
    # Detectar si la jornada del jugador ha comenzado.
    # Si TODOS los valores numéricos son 0 (o no hay ninguno parseable), el jugador
    # aún no ha jugado en esta jornada, así que no tiene sentido mostrar indicadores
    # de tendencia (saldrían 🔴↓ comparando 0 contra el promedio semanal).
    jornada_iniciada = False
    for _, v in stats.items():
        try:
            num = float(str(v).replace('%', '').replace(',', '.').strip())
            if num > 0:
                jornada_iniciada = True
                break
        except:
            continue
    
    # Si la jornada no ha empezado, suprimir los indicadores de tendencia
    if not jornada_iniciada:
        stats_jugador_resumen = None
    
    claves_usadas = set()
    cards_html = '<div class="stats-grid">'
    
    for etiqueta, icono, sinonimos in config_stats:
        clave_encontrada, valor = buscar_valor(stats, sinonimos, claves_usadas)
        
        if not clave_encontrada:
            continue
        
        claves_usadas.add(clave_encontrada)
        
        # Formatear valor: si es decimal con muchos decimales, redondear a 1 decimal
        # (ej. "5,666666667" → "5,7"). Conserva % y enteros tal cual.
        valor_str = str(valor).strip()
        if '%' not in valor_str and not valor_str.startswith('#'):
            try:
                num = float(valor_str.replace(',', '.').strip())
                # Si tiene parte decimal significativa y la cadena original tiene >3 chars decimales
                partes = valor_str.replace(',', '.').split('.')
                if len(partes) == 2 and len(partes[1]) > 2:
                    # Redondear a 1 decimal con coma española
                    valor = f"{num:.1f}".replace('.', ',')
            except:
                pass
        
        # Tendencia (comparación con resumen semanal)
        indicador = ""
        comparativa = ""
        if stats_jugador_resumen:
            _, valor_semanal = buscar_valor(stats_jugador_resumen, sinonimos, set())
            # Para Puntuación Global pasamos la clave original (contiene "puntiación") para activar el umbral del 3%
            etiqueta_para_tendencia = clave_encontrada if etiqueta == "Puntuación Global" else etiqueta
            indicador, _, comparativa = calcular_tendencia(valor, valor_semanal, etiqueta_para_tendencia)
            
            # Para volatilidad la lógica es INVERSA: menos volatilidad = mejor.
            # Invertimos el indicador (🟢↑ era "mejoró subiendo", ahora significa "empeoró subiendo").
            if etiqueta == "Índice Volatilidad":
                if "🟢" in indicador:
                    indicador = indicador.replace("🟢", "🔴")
                elif "🔴" in indicador:
                    indicador = indicador.replace("🔴", "🟢")
        
        # Detectar si es la tarjeta destacada (Puntuación Global)
        es_featured = etiqueta == "Puntuación Global"
        es_volatilidad = etiqueta == "Índice Volatilidad"
        
        # Colores según tipo de estadística
        if etiqueta == "Número victorias":
            color_borde = "#28a745"
            color_valor = "#28a745"
            bg_grad = "rgba(40, 167, 69, 0.08)"
        elif etiqueta == "Número derrotas":
            color_borde = "#dc3545"
            color_valor = "#dc3545"
            bg_grad = "rgba(220, 53, 69, 0.08)"
        elif es_featured:
            color_borde = "#f59e0b"
            color_valor = "#b45309"
            bg_grad = "rgba(245, 158, 11, 0.15)"
        elif es_volatilidad:
            paleta_vol = color_volatilidad(valor)
            color_borde = paleta_vol["borde"]
            color_valor = paleta_vol["valor"]
            bg_grad = paleta_vol["bg"]
        else:
            # Azul por defecto para todas las demás
            color_borde = "#1f77b4"
            color_valor = "#1f77b4"
            bg_grad = "rgba(31, 119, 180, 0.08)"
        
        # Indicador de tendencia: color verde si sube, rojo si baja, gris si neutro
        if "🟢" in indicador:
            tend_color = "#28a745"
            tend_weight = "700"
        elif "🔴" in indicador:
            tend_color = "#dc3545"
            tend_weight = "700"
        else:
            tend_color = "#999"
            tend_weight = "500"
        
        if indicador or comparativa:
            tend_html = (
                f'<span style="font-size:12px;color:{tend_color};font-weight:{tend_weight};white-space:nowrap;">'
                f'{indicador} {comparativa}</span>'
            )
        else:
            tend_html = ''
        
        # Badge de riesgo solo para la tarjeta de volatilidad (cuando hay valor parseable)
        riesgo_badge = ''
        if es_volatilidad:
            paleta_vol = color_volatilidad(valor)
            if paleta_vol["riesgo_label"]:
                riesgo_badge = (
                    f'<span style="font-size:10px;color:{paleta_vol["riesgo_texto"]};'
                    f'background:{paleta_vol["riesgo_bg"]};padding:2px 8px;border-radius:10px;'
                    f'font-weight:700;letter-spacing:0.3px;margin-left:6px;white-space:nowrap;">'
                    f'{paleta_vol["riesgo_label"]}</span>'
                )
        
        # Renderizado de la tarjeta destacada (Puntuación Global) — ocupa toda la fila
        if es_featured:
            cards_html += (
                f'<div style="grid-column:1 / -1;'
                f'background:linear-gradient(135deg,{bg_grad} 0%,rgba(255,255,255,0.01) 100%);'
                f'border:2px solid {color_borde};border-radius:10px;padding:18px 22px;'
                f'box-shadow:0 2px 8px rgba(245,158,11,0.12);">'
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;">'
                f'<span style="font-size:22px;">{icono}</span>'
                f'<span style="font-size:13px;color:#666;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">{etiqueta}</span>'
                f'<span style="font-size:10px;color:#92400e;font-weight:600;'
                f'background:rgba(245,158,11,0.18);padding:2px 8px;border-radius:10px;">⭐ MÉTRICA CLAVE</span>'
                f'</div>'
                f'<div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;">'
                f'<span style="font-size:34px;font-weight:bold;color:{color_valor};line-height:1;">{valor}</span>'
                f'{tend_html}'
                f'</div>'
                f'</div>'
            )
        else:
            # Tarjeta estándar
            cards_html += (
                f'<div style="background:linear-gradient(135deg,{bg_grad} 0%,rgba(255,255,255,0.01) 100%);'
                f'border-left:3px solid {color_borde};border-radius:8px;padding:12px 15px;">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                f'<span style="font-size:18px;">{icono}</span>'
                f'<span style="font-size:12px;color:#888;font-weight:600;">{etiqueta}</span>'
                f'</div>'
                f'<div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;flex-wrap:wrap;">'
                f'<span style="font-size:22px;font-weight:bold;color:{color_valor};">{valor}</span>'
                f'{tend_html}{riesgo_badge}'
                f'</div>'
                f'</div>'
            )
    
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)

def selector_jornada(key_prefix, incluir_resumen=True):
    """Selector de jornada por grupos con botones.

    Layout:
        Fila 1: [Grupo A] [Grupo B] [Grupo C]
        Fila 2: [🏆 Final] [📊 Resumen Semanal]   (Resumen opcional)
        Fila 3 (solo si grupo activo): [Día 1] [Día 2] [Día 3]

    Devuelve el nombre de la jornada seleccionada (clave de URLS).
    El parámetro key_prefix evita colisiones cuando se usa en varias secciones.
    """
    grupos = {
        "Grupo A": ["Grupo A Lunes", "Grupo A Martes", "Grupo A Miércoles"],
        "Grupo B": ["Grupo B Jueves", "Grupo B Viernes"],
        "Grupo C": ["Grupo C Jueves", "Grupo C Viernes"],
    }

    grupo_key = f"{key_prefix}_grupo_sel"
    jornada_key = f"{key_prefix}_jornada_sel"

    if grupo_key not in st.session_state:
        st.session_state[grupo_key] = "Grupo A"
    if jornada_key not in st.session_state:
        st.session_state[jornada_key] = "Grupo A Lunes"

    # Fila 1: grupos principales
    cols1 = st.columns(3)
    for i, g in enumerate(["Grupo A", "Grupo B", "Grupo C"]):
        with cols1[i]:
            tipo = "primary" if st.session_state[grupo_key] == g else "secondary"
            if st.button(g, key=f"{key_prefix}_btn_{g}", use_container_width=True, type=tipo):
                st.session_state[grupo_key] = g
                st.session_state[jornada_key] = grupos[g][0]
                st.rerun()

    # Fila 2: Final y opcionalmente Resumen Semanal
    extras = ["Final"]
    if incluir_resumen:
        extras.append("Resumen Semanal")
    cols2 = st.columns(len(extras))
    for i, b in enumerate(extras):
        with cols2[i]:
            tipo = "primary" if st.session_state[grupo_key] == b else "secondary"
            etiqueta = "🏆 Final" if b == "Final" else "📊 Resumen Semanal"
            if st.button(etiqueta, key=f"{key_prefix}_btn_{b}", use_container_width=True, type=tipo):
                st.session_state[grupo_key] = b
                st.session_state[jornada_key] = "Final Sábado" if b == "Final" else "Resumen Semanal"
                st.rerun()

    # Fila 3: días del grupo activo (solo si es Grupo A/B/C)
    grupo_actual = st.session_state[grupo_key]
    if grupo_actual in grupos:
        dias = grupos[grupo_actual]
        sub_cols = st.columns(len(dias))
        for i, dia in enumerate(dias):
            with sub_cols[i]:
                etiqueta = dia.replace(grupo_actual + " ", "")
                tipo = "primary" if st.session_state[jornada_key] == dia else "secondary"
                if st.button(etiqueta, key=f"{key_prefix}_btn_dia_{dia}", use_container_width=True, type=tipo):
                    st.session_state[jornada_key] = dia
                    st.rerun()

    return st.session_state[jornada_key]

def render_value_bets():
    st.title("💰 Value Bets")
    value_bets_list = []
    with st.expander("⚙️ Configuración", expanded=True):
        st.markdown("**📂 Fuente de datos**")
        fuente = selector_jornada("vb", incluir_resumen=True)
        st.session_state.vb_fuente = fuente
    with st.spinner(f"Cargando datos de '{fuente}'..."):
        db_jugadores = cargar_jugadores_desde(fuente)
    if not db_jugadores:
        st.warning(f"⚠️ No se encontraron jugadores en '{fuente}'.")
        return

    # Además de la fuente seleccionada, cargamos la base GLOBAL de jugadores
    # desde el Resumen Semanal, que contiene a TODOS los jugadores de la
    # semana (Grupo A, B y C). Esto permite que el desplegable de próximos
    # partidos y los selectores de J1/J2 funcionen con cualquier jugador,
    # independientemente del día/grupo seleccionado arriba.
    #
    # Para los cálculos seguimos prefiriendo los datos de la fuente elegida;
    # solo si un jugador no está en esa fuente usamos su ficha del Resumen
    # Semanal como respaldo (db_jugadores_completa).
    db_global = {}
    if fuente != "Resumen Semanal":
        try:
            db_global = cargar_jugadores_desde("Resumen Semanal") or {}
        except Exception:
            db_global = {}
    # db_jugadores_completa = fuente seleccionada con prioridad, completada
    # con los jugadores del Resumen Semanal que falten.
    db_jugadores_completa = dict(db_global)
    db_jugadores_completa.update(db_jugadores)  # la fuente elegida tiene prioridad

    # La lista de nombres del selector usa la base COMPLETA, así puedes
    # elegir (o autocompletar) cualquier jugador de cualquier grupo.
    nombres_disponibles = sorted(
        v["nombre_original"] for v in db_jugadores_completa.values()
    )
    if fuente in st.session_state.last_update:
        tiempo_transcurrido = (datetime.now() - st.session_state.last_update[fuente]).seconds
        st.info(f"📊 {len(nombres_disponibles)} jugadores | ⏱️ Actualizado hace {tiempo_transcurrido}s")
    st.markdown("### 🥊 Seleccionar Enfrentamiento")

    # ── Desplegable de próximos partidos ──────────────────────────────────────
    # Lista los 3 próximos partidos que aún no han empezado (vía API de MODUS).
    # Al elegir uno, autocompleta los selectores manuales de J1 y J2 de abajo.
    # Si la API no responde, se muestra un mensaje explicando el motivo en
    # lugar de ocultar el desplegable silenciosamente.
    resultado_api = obtener_proximos_partidos_api(limite=3)
    # Compatibilidad: la función ahora devuelve un dict; si por lo que sea
    # llegara una lista (versión antigua en caché), la adaptamos.
    if isinstance(resultado_api, dict):
        proximos = resultado_api.get("partidos", [])
        diagnostico = resultado_api.get("diagnostico", "")
    else:
        proximos = resultado_api or []
        diagnostico = ""

    def _emparejar_nombre(nombre_api, candidatos):
        """Empareja un nombre de la API con uno de la lista del desplegable.
        Hace match exacto primero y, si falla, match difuso por subcadena
        (útil cuando la API y el spreadsheet escriben el nombre distinto).
        Devuelve el nombre del candidato o None si no hay coincidencia.
        """
        if not nombre_api:
            return None
        na = nombre_api.lower().strip()
        # Match exacto (ignorando mayúsculas)
        for c in candidatos:
            if c.lower().strip() == na:
                return c
        # Match por subcadena en ambos sentidos
        for c in candidatos:
            cl = c.lower().strip()
            if na in cl or cl in na:
                return c
        # Match por apellido (última palabra)
        ape = na.split()[-1] if na.split() else na
        for c in candidatos:
            if ape and ape in c.lower():
                return c
        return None

    if proximos:
        OPCION_MANUAL = "— Selección manual —"

        # Reconstruimos la etiqueta de cada partido SOLO con los nombres de
        # los dos jugadores ("J1 vs J2"), ignorando cualquier campo 'etiqueta'
        # que venga de la API (que podría incluir fecha/hora u otra info
        # extra). Así el desplegable siempre muestra únicamente nombres.
        for p in proximos:
            p["etiqueta_limpia"] = f"{p['j1']} vs {p['j2']}"

        opciones_prox = [OPCION_MANUAL] + [p["etiqueta_limpia"] for p in proximos]

        seleccion_prox = st.selectbox(
            "📅 Próximos partidos",
            opciones_prox,
            index=0,
            key="vb_proximo_partido",
            help="Elige un partido para autocompletar automáticamente "
                 "Jugador 1 y Jugador 2. Se muestran los 3 próximos partidos "
                 "que aún no han empezado."
        )

        # Si el usuario eligió un partido concreto, autocompletar J1 y J2.
        #
        # Importante: NO se hace st.rerun() aquí. Un rerun reinicia toda la
        # app y haría que la barra lateral volviese a la sección por defecto
        # (LIVE), sacando al usuario de Value Bets. En su lugar, escribimos
        # directamente en st.session_state.vb_j1 / vb_j2 ANTES de que los
        # selectbox de abajo se creen: como esos selectbox usan esas mismas
        # claves, se renderizan ya con los jugadores correctos en este mismo
        # run, sin recargar la página.
        #
        # 'vb_ultimo_prox' recuerda qué partido se aplicó por última vez, para
        # no machacar las selecciones manuales del usuario en cada rerun
        # natural de Streamlit (al pulsar otros widgets de la página).
        if seleccion_prox != OPCION_MANUAL:
            partido = next((p for p in proximos
                            if p["etiqueta_limpia"] == seleccion_prox), None)
            if partido and st.session_state.get("vb_ultimo_prox") != seleccion_prox:
                j1_match = _emparejar_nombre(partido["j1"], nombres_disponibles)
                j2_match = _emparejar_nombre(partido["j2"], nombres_disponibles)
                if j1_match and j2_match and j1_match != j2_match:
                    # Escritura directa en las claves de los widgets J1/J2.
                    # Es seguro porque los widgets aún no se han instanciado.
                    st.session_state.vb_j1 = j1_match
                    st.session_state.vb_j2 = j2_match
                    st.session_state.vb_ultimo_prox = seleccion_prox
                    st.success(
                        f"✅ Enfrentamiento cargado: **{j1_match}** vs **{j2_match}**"
                    )
                else:
                    # No se pudo emparejar alguno de los dos jugadores
                    faltan = []
                    if not j1_match:
                        faltan.append(partido["j1"])
                    if not j2_match:
                        faltan.append(partido["j2"])
                    if faltan:
                        st.warning(
                            "⚠️ No encontré en esta fuente de datos a: "
                            + ", ".join(faltan)
                            + ". Selecciónalos manualmente abajo."
                        )
        else:
            # Volvió a "Selección manual": limpiar el marcador para permitir
            # que un partido se pueda volver a aplicar más adelante.
            st.session_state.vb_ultimo_prox = None
    else:
        # No hay próximos partidos: mostrar el motivo en vez de ocultar todo.
        st.caption(
            "📅 Próximos partidos: " +
            (diagnostico or "no hay partidos pendientes ahora mismo.") +
            " Selecciona los jugadores manualmente abajo."
        )


    if st.session_state.vb_j1 is None or st.session_state.vb_j1 not in nombres_disponibles:
        st.session_state.vb_j1 = nombres_disponibles[0]
    if st.session_state.vb_j2 is None or st.session_state.vb_j2 not in nombres_disponibles:
        opciones_j2 = [n for n in nombres_disponibles if n != st.session_state.vb_j1]
        st.session_state.vb_j2 = opciones_j2[0] if opciones_j2 else nombres_disponibles[0]
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        # El selectbox usa 'vb_j1' como key directamente: el widget y el
        # estado de sesión son la MISMA variable. Esto permite que el
        # desplegable de próximos partidos autocomplete el valor sin recargar.
        #
        # Solo pasamos 'index' la primera vez (cuando la key aún no existe en
        # session_state). Si ya existe, Streamlit usa el valor de la key, así
        # que pasar 'index' además sería redundante y podría dar un warning.
        kwargs_j1 = {"key": "vb_j1"}
        if "vb_j1" not in st.session_state or st.session_state.vb_j1 not in nombres_disponibles:
            valor_inicial = st.session_state.get("vb_j1")
            if valor_inicial not in nombres_disponibles:
                valor_inicial = nombres_disponibles[0]
            kwargs_j1["index"] = nombres_disponibles.index(valor_inicial)
        j1_sel = st.selectbox("Jugador 1", nombres_disponibles, **kwargs_j1)
    with col2:
        opciones_j2 = [n for n in nombres_disponibles if n != j1_sel]
        if not opciones_j2:
            opciones_j2 = nombres_disponibles
        # Si el J2 actual ya no es válido (coincide con J1 o no está en la
        # lista), ajustarlo ANTES de crear el widget — no se puede tocar la
        # key una vez instanciado el selectbox.
        if st.session_state.get("vb_j2") not in opciones_j2:
            st.session_state.vb_j2 = opciones_j2[0]
        kwargs_j2 = {"key": "vb_j2"}
        # Pasamos index solo si la key todavía no existe (primer render).
        if "vb_j2" not in st.session_state:
            kwargs_j2["index"] = 0
        j2_sel = st.selectbox("Jugador 2", opciones_j2, **kwargs_j2)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔢 Calcular", type="primary", use_container_width=True, help="Calcular probabilidades"):
            st.session_state.vb_calcular = True
    if not st.session_state.vb_calcular:
        st.info("👆 Selecciona los jugadores y pulsa **Calcular**")
        return
    # Buscar los datos de cada jugador: primero en la fuente seleccionada
    # (datos del día/grupo concreto) y, si no está ahí, en la base completa
    # (Resumen Semanal). Así se puede analizar un enfrentamiento aunque uno
    # de los jugadores sea de otro grupo distinto al seleccionado arriba.
    j1 = buscar_jugador(j1_sel, db_jugadores) or buscar_jugador(j1_sel, db_jugadores_completa)
    j2 = buscar_jugador(j2_sel, db_jugadores) or buscar_jugador(j2_sel, db_jugadores_completa)
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
        
        # Card de Índice Volatilidad — separada, full-width, con semáforo
        vol_j1 = j1.get("volatilidad", 0.0)
        paleta_vol_j1 = color_volatilidad(vol_j1)
        vol_label_j1 = paleta_vol_j1["riesgo_label"].capitalize() if paleta_vol_j1["riesgo_label"] else "Sin datos"
        vol_str_j1 = f"{vol_j1:.2f}".replace(".", ",")
        st.markdown(
            f"<div style='margin-top: 12px; text-align: center; padding: 14px 18px; "
            f"background: {paleta_vol_j1['bg']}; border-radius: 8px; "
            f"border: 1px solid {paleta_vol_j1['borde']};'>"
            f"<p style='margin: 0; font-size: 12px; color: #666; font-weight: 600;'>📉 Índice Volatilidad</p>"
            f"<div style='margin-top: 8px; display: flex; align-items: baseline; justify-content: center; gap: 12px; flex-wrap: wrap;'>"
            f"<span style='font-size: 26px; font-weight: bold; color: {paleta_vol_j1['valor']};'>{vol_str_j1}</span>"
            f"<span style='font-size: 13px; font-weight: 600; color: {paleta_vol_j1['riesgo_texto']};'>● {vol_label_j1}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    
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
        
        # Card de Índice Volatilidad — separada, full-width, con semáforo
        vol_j2 = j2.get("volatilidad", 0.0)
        paleta_vol_j2 = color_volatilidad(vol_j2)
        vol_label_j2 = paleta_vol_j2["riesgo_label"].capitalize() if paleta_vol_j2["riesgo_label"] else "Sin datos"
        vol_str_j2 = f"{vol_j2:.2f}".replace(".", ",")
        st.markdown(
            f"<div style='margin-top: 12px; text-align: center; padding: 14px 18px; "
            f"background: {paleta_vol_j2['bg']}; border-radius: 8px; "
            f"border: 1px solid {paleta_vol_j2['borde']};'>"
            f"<p style='margin: 0; font-size: 12px; color: #666; font-weight: 600;'>📉 Índice Volatilidad</p>"
            f"<div style='margin-top: 8px; display: flex; align-items: baseline; justify-content: center; gap: 12px; flex-wrap: wrap;'>"
            f"<span style='font-size: 26px; font-weight: bold; color: {paleta_vol_j2['valor']};'>{vol_str_j2}</span>"
            f"<span style='font-size: 13px; font-weight: 600; color: {paleta_vol_j2['riesgo_texto']};'>● {vol_label_j2}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    
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

    # ─── Últimos 3 partidos por jugador ───────────────────────────────────────
    # Dos desplegables (uno por jugador) con sus 3 últimos partidos jugados en
    # la semana, en orden cronológico inverso. Muestra rival, marcador y todas
    # las stats de la fila del jugador en cada partido.
    st.markdown("---")
    st.markdown("### 📅 Últimos partidos jugados")
    col_u1, col_u2 = st.columns(2)
    
    def _render_ultimos_partidos(col, jugador_dict, color_jug, color_rival):
        nombre = jugador_dict['nombre_original']
        with col:
            with st.expander(f"📂 Últimos 3 partidos de **{nombre}**", expanded=False):
                with st.spinner(f"Buscando partidos de {nombre}..."):
                    ultimos = obtener_ultimos_partidos(nombre, n=3)
                
                if not ultimos:
                    st.info(f"ℹ️ No se encontraron partidos terminados de {nombre} esta semana")
                    return
                
                for idx, p in enumerate(ultimos, start=1):
                    # Cabecera del partido: resultado con marcador
                    icono = "🏆" if p["ganador"] else "❌"
                    color_resultado = "#22c55e" if p["ganador"] else "#dc3545"
                    texto_resultado = "Victoria" if p["ganador"] else "Derrota"
                    
                    # Preservar el orden original del partido: si nuestro jugador
                    # era el de arriba en el spreadsheet, va a la izquierda; si
                    # era el de abajo, va a la derecha. Así no parece que siempre
                    # haya jugado de "local".
                    if p.get("jugador_primero", True):
                        izq_nombre, izq_color = nombre, color_jug
                        der_nombre, der_color = p['rival'], color_rival
                    else:
                        izq_nombre, izq_color = p['rival'], color_rival
                        der_nombre, der_color = nombre, color_jug
                    
                    st.markdown(
                        f"<div style='margin-top: {16 if idx > 1 else 6}px; padding: 10px 14px; "
                        f"background: rgba(150,150,150,0.10); border-left: 4px solid {color_jug}; "
                        f"border-radius: 6px;'>"
                        f"<div style='display: flex; justify-content: space-between; align-items: center; "
                        f"gap: 10px; flex-wrap: wrap;'>"
                        f"<span style='font-weight: 600; color: #444; font-size: 13px;'>"
                        f"#{idx} · <span style='color: #888;'>{p['dia']}</span></span>"
                        f"<span style='font-size: 14px;'>"
                        f"<span style='color: {izq_color}; font-weight: 700;'>{izq_nombre}</span> "
                        f"<span style='color: #888;'>vs</span> "
                        f"<span style='color: {der_color}; font-weight: 700;'>{der_nombre}</span>"
                        f"</span>"
                        f"<span style='font-weight: 700; font-size: 16px; color: {color_resultado};'>"
                        f"{icono} {p['marcador']} · {texto_resultado}</span>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    
                    # Stats del jugador en ese partido: tabla compacta
                    stats = p["stats"]
                    if stats:
                        # Saltar columna del nombre (primera) y otras vacías;
                        # mostrar resto como pares etiqueta-valor en mini-grid.
                        # También se omite la columna "Resultado" (legs del partido)
                        # porque ya se muestra como marcador en la cabecera.
                        items = []
                        for k, v in stats.items():
                            k_str = str(k).strip()
                            k_lower = k_str.lower()
                            v_str = str(v).strip()
                            if not k_str or k_lower.startswith("unnamed"):
                                continue
                            if v_str.lower() in ('', 'nan'):
                                continue
                            # Saltar la celda que contiene el propio nombre del jugador
                            if v_str.lower() == nombre.lower():
                                continue
                            # Saltar la columna "Resultado" — info redundante con
                            # el marcador que ya aparece en la cabecera del partido
                            if "resultado" in k_lower:
                                continue
                            items.append((k_str, v_str))
                        
                        if items:
                            # Grid responsivo: ~4 columnas en desktop, se adapta
                            cells_html = ""
                            for k, v in items:
                                cells_html += (
                                    f"<div style='background: rgba(255,255,255,0.03); "
                                    f"padding: 8px 10px; border-radius: 5px; "
                                    f"border: 1px solid rgba(150,150,150,0.2);'>"
                                    f"<div style='font-size: 10px; color: #888; "
                                    f"text-transform: uppercase; letter-spacing: 0.3px; "
                                    f"margin-bottom: 3px;'>{k}</div>"
                                    f"<div style='font-size: 15px; font-weight: 600; "
                                    f"color: {color_jug};'>{v}</div>"
                                    f"</div>"
                                )
                            st.markdown(
                                f"<div style='display: grid; "
                                f"grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); "
                                f"gap: 8px; margin-top: 8px; margin-bottom: 4px;'>"
                                f"{cells_html}</div>",
                                unsafe_allow_html=True
                            )
    
    _render_ultimos_partidos(col_u1, j1, "#1f77b4", "#ff7f0e")
    _render_ultimos_partidos(col_u2, j2, "#ff7f0e", "#1f77b4")

    # J1 siempre saca primero (la ventaja de saque va al jugador 1 seleccionado).
    # Las funciones tienen `j1_saca_primero=True` como default, así que basta con
    # llamarlas sin pasar el parámetro.
    v1, v2 = prob_victoria(pr1, pr2)
    m180 = prob_180s(lam1, lam2, pr1=pr1, pr2=pr2)
    p_j1_mas, p_emp, p_j2_mas = quien_hace_mas_180s(lam1, lam2, pr1=pr1, pr2=pr2)
    hcaps = handicaps_legs(pr1, pr2)
    legs_total_dict = legs_totales(pr1, pr2)
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
        st.markdown("#### 🎯 Hándicaps de Legs")
        
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

    # ── Registrar este partido en el seguimiento ─────────────────────────────
    # Como el enfrentamiento (j1, j2) ya esta calculado aqui, ofrecemos
    # registrarlo directamente, sin tener que volver a elegir los jugadores
    # en otra seccion. Es el flujo natural: calculas un partido y, si quieres
    # hacerle seguimiento, lo registras con un clic.
    if _PREDICCIONES_OK and registrar_predicciones is not None:
        st.markdown("---")
        st.markdown("#### 📝 Seguimiento del modelo")
        st.caption(
            "Registra este enfrentamiento para comparar despues lo que el "
            "modelo predijo con el resultado real. Hazlo justo antes de que "
            "el partido se juegue."
        )
        semana_vb = st.text_input(
            "Identificador de la jornada/semana",
            value=datetime.now().strftime("Semana %Y-%m-%d"),
            key="vb_semana_track",
            help="Etiqueta para agrupar las predicciones de esta jornada."
        )
        if st.button(f"📝 Registrar {j1_sel} vs {j2_sel}",
                     key="vb_btn_registrar_partido"):
            with st.spinner(f"Registrando {j1_sel} vs {j2_sel}..."):
                url_sheet = URLS.get(fuente, "")
                resultado = registrar_predicciones(
                    url_sheet, [(j1, j2)], semana_vb, fuente
                )
            if resultado["ok"]:
                st.success(
                    f"✅ Partido registrado: **{j1_sel}** vs **{j2_sel}** — "
                    f"{resultado['nuevas']} predicciones nuevas, "
                    f"{resultado['duplicadas']} ya existian "
                    f"({resultado['total']} mercados)."
                )
                if cargar_predicciones is not None:
                    cargar_predicciones.clear()
            else:
                st.error(f"❌ {resultado['error']}")

def render_heatmap_estadisticas(stats_dict, titulo="📊 Comparativa de Estadísticas"):
    """Renderiza un heatmap (tabla coloreada) con las 5 métricas clave por jugador.

    Cada columna se colorea independientemente con gradiente rojo→amarillo→verde
    según el valor relativo del jugador en esa métrica. Esto evita que escalas distintas
    (ej. λ180s en 0-3 vs. % victoria en 0-100) se aplasten entre sí.
    """
    if not stats_dict:
        return

    df, cols_metricas = _extraer_metricas_jugadores(stats_dict)
    if df.empty:
        return

    st.subheader(titulo)
    st.caption("🟢 Mejor en cada métrica · 🔴 Peor · El gradiente es relativo al rango de cada columna")

    def color_celda(val, vmin, vmax):
        """Mapea un valor a un color de fondo rojo→amarillo→verde.
        Reemplaza Styler.background_gradient (que requiere matplotlib)."""
        if pd.isna(val) or vmin == vmax:
            return ''
        norm = (val - vmin) / (vmax - vmin)
        norm = max(0.0, min(1.0, norm))
        if norm < 0.5:
            r = 235
            g = int(80 + norm * 2 * 175)
            b = 80
        else:
            r = int(235 - (norm - 0.5) * 2 * 175)
            g = 200
            b = 80
        return f'background-color: rgba({r}, {g}, {b}, 0.55); color: #111; font-weight: 600;'

    def gradiente_columna(col):
        valores_validos = col.dropna()
        if len(valores_validos) == 0:
            return ['' for _ in col]
        vmin = valores_validos.min()
        vmax = valores_validos.max()
        return [color_celda(v, vmin, vmax) for v in col]

    styled = df.style.apply(
        gradiente_columna,
        subset=cols_metricas,
        axis=0
    ).format({
        "Media 180": lambda x: f"{x:.2f}" if pd.notna(x) else "—",
        "Promedio Puntos": lambda x: f"{x:.1f}" if pd.notna(x) else "—",
        "Checkout %": lambda x: f"{x:.1f}%" if pd.notna(x) else "—",
        "% Victoria": lambda x: f"{x:.1f}%" if pd.notna(x) else "—",
        "Puntuación Global": lambda x: f"{x:.1f}" if pd.notna(x) else "—",
    }).set_properties(**{
        'text-align': 'center',
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
        {'selector': 'th.col_heading', 'props': [('background-color', '#1f2937'), ('color', 'white')]},
    ])

    st.dataframe(styled, use_container_width=True, hide_index=True)

def render_radar_multiple(stats_dict, titulo="🕸️ Perfil Comparativo (Pentágono)", key_prefix="radar"):
    """Pentágono múltiple superpuesto: 1 polígono por jugador, 5 vértices = 5 métricas.

    Permite filtrar jugadores con un multiselect (por defecto los 5 primeros, para
    no saturar visualmente cuando hay 8+ jugadores).

    Normalización fija por métrica:
        - Media 180: 0-3
        - Promedio Puntos: 0-100
        - Checkout %, % Victoria, Puntuación Global: 0-100
    """
    if not stats_dict:
        return

    df, cols_metricas = _extraer_metricas_jugadores(stats_dict)
    if df.empty:
        return

    # Rangos máximos para normalizar cada eje a 0-100% del radio
    rangos_max = {
        "Media 180": 3.0,
        "Promedio Puntos": 100.0,
        "Checkout %": 100.0,
        "% Victoria": 100.0,
        "Puntuación Global": 100.0,
    }

    st.subheader(titulo)

    # Multiselect: por defecto los 5 primeros para evitar saturar
    jugadores_disponibles = df["Jugador"].tolist()
    default_n = min(5, len(jugadores_disponibles))
    seleccionados = st.multiselect(
        "Jugadores a comparar (puedes añadir o quitar):",
        jugadores_disponibles,
        default=jugadores_disponibles[:default_n],
        key=f"{key_prefix}_multi_select"
    )

    if not seleccionados:
        st.info("Selecciona al menos un jugador para visualizar el pentágono.")
        return

    # Paleta D3/Tableau (10 colores que se distinguen bien entre sí)
    paleta = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"
    ]

    # Geometría del SVG
    svg_size = 480
    center_x = center_y = svg_size / 2
    radius = 150
    angle_offset = -90

    # Vértices del pentágono base + posiciones de etiquetas
    base_points = []
    label_pos = []
    for i in range(5):
        angle = angle_offset + i * 72
        rad = np.radians(angle)
        x = center_x + radius * np.cos(rad)
        y = center_y + radius * np.sin(rad)
        base_points.append((x, y))
        # Las etiquetas a un radio mayor para que no se solapen con el pentágono
        label_radius = radius + 38
        lx = center_x + label_radius * np.cos(rad)
        ly = center_y + label_radius * np.sin(rad)
        label_pos.append((lx, ly))

    svg = []
    svg.append(f'<svg width="{svg_size}" height="{svg_size}" xmlns="http://www.w3.org/2000/svg" style="background:white;">')

    # Círculos concéntricos de referencia (25%, 50%, 75%, 100%)
    for r_pct in [25, 50, 75, 100]:
        r = (r_pct / 100) * radius
        svg.append(f'<circle cx="{center_x}" cy="{center_y}" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="0.8"/>')

    # Líneas radiales hacia los vértices
    for p in base_points:
        svg.append(f'<line x1="{center_x}" y1="{center_y}" x2="{p[0]}" y2="{p[1]}" stroke="#e5e7eb" stroke-width="0.8"/>')

    # Pentágono base
    pent_path = "M " + " L ".join([f"{p[0]},{p[1]}" for p in base_points]) + " Z"
    svg.append(f'<path d="{pent_path}" fill="none" stroke="#9ca3af" stroke-width="1"/>')

    # Polígono por cada jugador seleccionado
    for idx, jugador in enumerate(seleccionados):
        fila = df[df["Jugador"] == jugador].iloc[0]
        color = paleta[idx % len(paleta)]
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))

        puntos_jugador = []
        for i, nombre_metrica in enumerate(cols_metricas):
            val = fila[nombre_metrica]
            if pd.isna(val):
                val = 0
            max_val = rangos_max[nombre_metrica]
            norm = min(1.0, max(0.0, val / max_val))
            angle = angle_offset + i * 72
            rad = np.radians(angle)
            r = norm * radius
            x = center_x + r * np.cos(rad)
            y = center_y + r * np.sin(rad)
            puntos_jugador.append((x, y))

        path = "M " + " L ".join([f"{p[0]},{p[1]}" for p in puntos_jugador]) + " Z"
        svg.append(f'<path d="{path}" fill="rgba({rgb[0]},{rgb[1]},{rgb[2]},0.18)" stroke="{color}" stroke-width="2.2"/>')

        # Puntos en cada vértice del polígono del jugador
        for p in puntos_jugador:
            svg.append(f'<circle cx="{p[0]}" cy="{p[1]}" r="3.2" fill="{color}" stroke="white" stroke-width="1.2"/>')

    # Etiquetas de las métricas en cada vértice
    for i, (lx, ly) in enumerate(label_pos):
        svg.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="11" font-family="Arial, sans-serif" fill="#374151" font-weight="600">'
            f'{cols_metricas[i]}</text>'
        )

    svg.append('</svg>')
    svg_html = "".join(svg)

    # Layout: pentágono a la izquierda, leyenda a la derecha
    col_svg, col_leyenda = st.columns([2, 1])

    with col_svg:
        st.markdown(
            f'<div style="text-align:center;">{svg_html}</div>',
            unsafe_allow_html=True
        )

    with col_leyenda:
        st.markdown("**Leyenda**")
        for idx, jugador in enumerate(seleccionados):
            color = paleta[idx % len(paleta)]
            fila = df[df["Jugador"] == jugador].iloc[0]
            # Mostrar puntuación global como referencia rápida
            pg = fila["Puntuación Global"]
            pg_str = f"{pg:.1f}" if pd.notna(pg) else "—"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin:6px 0;padding:6px;'
                f'background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08);'
                f'border-left:3px solid {color};border-radius:4px;">'
                f'<div style="width:14px;height:14px;background:{color};border-radius:3px;flex-shrink:0;"></div>'
                f'<div style="flex:1;">'
                f'<div style="font-size:13px;font-weight:600;color:#111;">{jugador}</div>'
                f'<div style="font-size:11px;color:#666;">PG: {pg_str}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.caption(
        "💡 Cuanto más grande es el polígono, mejor perfil global. "
        "La forma indica el estilo del jugador (puntudo en 180s, equilibrado, etc.)."
    )

def render_small_multiples(stats_dict, titulo="📊 Ranking por Métrica"):
    """Small multiples con layout simétrico:
        - Puntuación Global destacada arriba ocupando toda la fila (más grande,
          con acento dorado para subrayar su importancia).
        - Las 4 métricas restantes en rejilla 2×2 simétrica debajo.
        - En móvil todo se apila a 1 columna.

    Cada mini-gráfico ordena los jugadores de mejor a peor en su métrica y los
    pinta con barras horizontales. El color va de verde (top del ranking) a rojo
    (último), no por valor absoluto, así el ranking se lee de un vistazo aunque
    los valores estén muy juntos.
    """
    if not stats_dict:
        return

    df, cols_metricas = _extraer_metricas_jugadores(stats_dict)
    if df.empty:
        return

    st.subheader(titulo)
    st.caption("Cada gráfico ordena a los jugadores de mejor a peor en esa métrica concreta. 🟢 mejor del ranking · 🔴 peor")

    # Formato del valor que se muestra al final de cada barra
    formatos = {
        "Media 180": lambda x: f"{x:.2f}",
        "Promedio Puntos": lambda x: f"{x:.1f}",
        "Checkout %": lambda x: f"{x:.1f}%",
        "% Victoria": lambda x: f"{x:.1f}%",
        "Puntuación Global": lambda x: f"{x:.1f}",
    }

    def _color_ranking(idx, n):
        """Gradiente verde→rojo según posición en el ranking (no según valor)."""
        norm = 1.0 if n == 1 else 1 - (idx / (n - 1))
        if norm >= 0.5:
            r = int(235 - (norm - 0.5) * 2 * 175)
            g = 200
            b = 80
        else:
            r = 235
            g = int(80 + norm * 2 * 175)
            b = 80
        return f"rgb({r},{g},{b})"

    def _render_card(metrica, destacada=False):
        """Construye el HTML de una tarjeta (mini-gráfico de una métrica)."""
        sub = df[["Jugador", metrica]].dropna(subset=[metrica]).copy()
        if sub.empty:
            return ""
        sub = sub.sort_values(by=metrica, ascending=False).reset_index(drop=True)
        max_val = sub[metrica].max()
        n = len(sub)

        # Dimensiones distintas si la tarjeta está destacada
        bar_height = 30 if destacada else 22
        font_size_value = 13 if destacada else 11
        font_size_name = 13 if destacada else 11
        name_width = 110 if destacada else 95
        title_size = 17 if destacada else 14
        margin_row = 7 if destacada else 5

        rows_html = ""
        for idx, row in sub.iterrows():
            jugador = row["Jugador"]
            valor = row[metrica]
            valor_str = formatos.get(metrica, lambda x: f"{x:.1f}")(valor)
            ancho_pct = max(6.0, (valor / max_val) * 100) if (max_val and max_val > 0) else 6.0
            color = _color_ranking(idx, n)

            rows_html += (
                f'<div style="display:flex;align-items:center;gap:10px;margin:{margin_row}px 0;">'
                f'<span style="font-size:{font_size_name}px;width:{name_width}px;flex-shrink:0;'
                f'color:#374151;font-weight:500;overflow:hidden;text-overflow:ellipsis;'
                f'white-space:nowrap;" title="{jugador}">{jugador}</span>'
                f'<div style="flex:1;background:rgba(0,0,0,0.05);border-radius:4px;height:{bar_height}px;">'
                f'<div style="width:{ancho_pct:.1f}%;background:{color};height:100%;border-radius:4px;'
                f'display:flex;align-items:center;justify-content:flex-end;padding-right:8px;'
                f'box-shadow:inset 0 0 0 1px rgba(0,0,0,0.04);">'
                f'<span style="color:white;font-size:{font_size_value}px;font-weight:700;'
                f'text-shadow:0 1px 1px rgba(0,0,0,0.25);">{valor_str}</span>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

        # Estilo distinto para la tarjeta destacada (Puntuación Global)
        if destacada:
            card_style = (
                'grid-column: 1 / -1;'
                'background: linear-gradient(135deg, rgba(245,158,11,0.06) 0%, rgba(255,255,255,0.01) 100%);'
                'border: 2px solid #f59e0b;'
                'border-radius: 10px;'
                'padding: 18px 22px;'
                'box-shadow: 0 2px 8px rgba(245,158,11,0.08);'
            )
            title_color = "#b45309"
            title_extra = '<span style="font-size:11px;color:#92400e;font-weight:600;margin-left:8px;background:rgba(245,158,11,0.15);padding:2px 8px;border-radius:10px;">⭐ MÉTRICA CLAVE</span>'
        else:
            card_style = (
                'background: white;'
                'border: 1px solid #e5e7eb;'
                'border-radius: 8px;'
                'padding: 14px 16px;'
            )
            title_color = "#1f2937"
            title_extra = ""

        return (
            f'<div style="{card_style}">'
            f'<h5 style="margin:0 0 12px 0;color:{title_color};font-size:{title_size}px;'
            f'font-weight:700;border-bottom:2px solid #e5e7eb;padding-bottom:8px;'
            f'display:flex;align-items:center;">{metrica}{title_extra}</h5>'
            f'{rows_html}'
            f'</div>'
        )

    # Orden: Puntuación Global primero (destacada), luego las demás en orden fijo
    metrica_destacada = "Puntuación Global"
    orden_resto = ["Media 180", "Promedio Puntos", "Checkout %", "% Victoria"]
    metricas_resto = [m for m in orden_resto if m in cols_metricas]

    cards_html = '<div class="small-multiples-grid">'
    if metrica_destacada in cols_metricas:
        cards_html += _render_card(metrica_destacada, destacada=True)
    for metrica in metricas_resto:
        cards_html += _render_card(metrica, destacada=False)
    cards_html += '</div>'

    # CSS de rejilla: 2 columnas en desktop, 1 en móvil. Puntuación Global usa
    # `grid-column: 1 / -1` para ocupar toda la fila.
    st.markdown("""
    <style>
    .small-multiples-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 14px;
        margin: 10px 0 20px 0;
    }
    @media (max-width: 768px) {
        .small-multiples-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(cards_html, unsafe_allow_html=True)

def render_comparativa_completa(stats_dict, key_prefix="comp", tipo="radar"):
    """Heatmap + visualización extra. El parámetro `tipo` decide qué se añade debajo:
        - "radar":  pentágono múltiple superpuesto (varios jugadores a la vez)
        - "barras": small multiples (5 mini-gráficos de barras horizontales)
    """
    if not stats_dict:
        return

    render_heatmap_estadisticas(stats_dict, titulo="📊 Comparativa Visual de Estadísticas")
    st.markdown("")
    if tipo == "radar":
        render_radar_multiple(stats_dict, titulo="🕸️ Perfil Comparativo (Pentágono)", key_prefix=key_prefix)
    elif tipo == "barras":
        render_small_multiples(stats_dict, titulo="📊 Ranking por Métrica")


def render_tracking_predicciones():
    """Renderiza la seccion de seguimiento de predicciones del modelo.

    Tiene dos partes:
      1) Boton para registrar todas las predicciones de una jornada en la
         hoja 'Predicciones' del Google Sheet.
      2) Panel de metricas: tasa de acierto, Brier score y tabla de
         calibracion, calculadas sobre las predicciones ya verificadas.

    Pensada para colocarse al final de la pestana Value Bets.
    """
    st.markdown("---")
    st.markdown("## 📈 Seguimiento del modelo")
    st.caption(
        "Registra las predicciones de una jornada y compara, con el tiempo, "
        "lo que el modelo predijo frente a lo que realmente ocurrio."
    )

    # Si el modulo de predicciones no se pudo cargar (falta el archivo o sus
    # dependencias gspread/google-auth), mostramos el motivo y salimos sin
    # tumbar el resto de la app.
    if not _PREDICCIONES_OK:
        st.warning(
            "⚠️ La seccion de seguimiento no esta disponible: el modulo "
            "`predicciones.py` no se pudo cargar.\n\n"
            f"Detalle tecnico: `{_PREDICCIONES_ERROR}`\n\n"
            "Comprueba que el archivo **predicciones.py** esta subido al "
            "repositorio y que **gspread** y **google-auth** figuran en el "
            "archivo `requirements.txt`."
        )
        return

    # Segunda comprobacion: el modulo cargo, pero ¿estan las librerias de
    # Google y el secreto? Si falta algo, lo explicamos y salimos.
    if tracking_disponible is not None:
        disponible, motivo = tracking_disponible()
        if not disponible:
            st.warning(f"⚠️ Seguimiento no disponible: {motivo}")
            return

    # ── Parte 1: como registrar (el registro se hace desde Value Bets) ───────
    st.info(
        "📝 **Para registrar un partido**: arriba, en Value Bets, selecciona "
        "los dos jugadores, pulsa **Calcular** y al final del analisis "
        "encontraras el boton **Registrar este partido**. Asi registras el "
        "enfrentamiento con los mismos jugadores que acabas de analizar."
    )

    # Boton de diagnostico de la conexion con Google Sheets.
    if st.button("🔧 Probar conexion con Google Sheets", key="trk_btn_diag"):
        with st.spinner("Probando conexion..."):
            if diagnostico_conexion is not None:
                informe = diagnostico_conexion("")
            else:
                informe = "El modulo de predicciones no se cargo."
        st.code(informe, language="text")

    # ── Parte 2: verificacion automatica de resultados ───────────────────────
    with st.expander("✅ Verificar resultados de los partidos", expanded=False):
        st.markdown(
            "Comprueba automaticamente las predicciones pendientes contra los "
            "resultados reales de las pestanas de jornada. Cada prediccion se "
            "marca como **acierto (1)**, **fallo (0)** o **no jugado** (si ese "
            "enfrentamiento concreto no llego a disputarse)."
        )
        if st.button("✅ Verificar resultados ahora", type="primary",
                     key="trk_btn_verificar"):
            with st.spinner("Comparando predicciones con los resultados "
                            "reales de las jornadas..."):
                res_ver = verificar_resultados()
            if res_ver["ok"]:
                st.success(
                    f"✅ Verificacion completada: "
                    f"**{res_ver['aciertos']}** aciertos, "
                    f"**{res_ver['fallos']}** fallos, "
                    f"{res_ver['no_jugado']} no jugados, "
                    f"{res_ver['sin_cambios']} ya estaban verificadas."
                )
                # Limpiar cache para que el panel de abajo se actualice
                cargar_predicciones.clear()
            else:
                st.error(f"❌ {res_ver['error']}")

    # ── Parte 3: panel de metricas de calibracion ────────────────────────────
    st.markdown("### 🎯 Calidad del modelo")

    # Leemos las predicciones de la fuente que el usuario tenga seleccionada
    # arriba en Value Bets (vb_fuente); si no, del primer URL disponible.
    fuente_metricas = st.session_state.get("vb_fuente", "")
    url_metricas = URLS.get(fuente_metricas, "")
    if not url_metricas and URLS:
        url_metricas = list(URLS.values())[0]

    with st.spinner("Leyendo predicciones registradas..."):
        df_pred = cargar_predicciones(url_metricas)

    if df_pred is None or df_pred.empty:
        st.info(
            "ℹ️ Aun no hay predicciones registradas (o no se pudo leer la "
            "hoja). Registra una jornada con el boton de arriba para empezar."
        )
        return

    metricas = calcular_metricas(df_pred)

    total_reg = len(df_pred)
    evaluadas = metricas["evaluadas"]
    pendientes = metricas["pendientes"]
    no_jugado = metricas.get("no_jugado", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registradas", total_reg)
    c2.metric("Verificadas", evaluadas)
    c3.metric("Pendientes", pendientes,
              help="Predicciones de partidos que aun no se han verificado.")
    c4.metric("No jugados", no_jugado,
              help="Enfrentamientos que nunca llegaron a disputarse. No "
                   "cuentan para las metricas.")

    if evaluadas == 0:
        st.info(
            "Hay predicciones registradas pero ninguna verificada todavia. "
            "Cuando los partidos terminen, rellena la columna **Acierto** "
            "de la hoja *Predicciones* (1 = acerto, 0 = fallo) y las "
            "metricas apareceran aqui."
        )
        return

    # Metricas principales
    m1, m2 = st.columns(2)
    m1.metric("Tasa de acierto", f"{metricas['tasa_acierto']:.1f}%",
              help="% de predicciones acertadas sobre las verificadas.")
    if metricas["brier"] is not None:
        m2.metric("Brier score", f"{metricas['brier']:.3f}",
                  help="Calidad de las probabilidades. 0 = perfecto, "
                       "0.25 = azar. Cuanto menor, mejor.")

    # Aviso de muestra pequena
    if evaluadas < 30:
        st.warning(
            f"⚠️ Solo hay {evaluadas} predicciones verificadas. Con tan pocas, "
            f"estas cifras son muy ruidosas: tomalas como orientativas hasta "
            f"acumular bastantes mas."
        )

    # Tabla de acierto por tipo de mercado: en que mercados acierta mas el
    # modelo y en cuales menos. Es lo mas accionable para saber que
    # predicciones del modelo son fiables.
    if metricas.get("por_mercado"):
        st.markdown("#### 🎯 Acierto por tipo de mercado")
        st.caption(
            "Tasa de acierto del modelo en cada tipo de mercado. Te dice "
            "que predicciones son fiables y cuales no: una tasa cercana al "
            "50% significa que ese mercado no se predice mejor que el azar."
        )
        df_merc = pd.DataFrame(metricas["por_mercado"])
        df_merc = df_merc.rename(columns={
            "mercado": "Mercado",
            "verificadas": "Verificadas",
            "aciertos": "Aciertos",
            "tasa": "Tasa de acierto",
        })
        df_merc["Tasa de acierto"] = df_merc["Tasa de acierto"].map(
            lambda v: f"{v:.1f}%")
        st.dataframe(df_merc, use_container_width=True, hide_index=True)

    # Tabla de calibracion
    if metricas["calibracion"]:
        st.markdown("#### 📊 Calibracion del modelo")
        st.caption(
            "Para cada tramo de probabilidad: lo que el modelo predijo de "
            "media frente a lo que realmente paso. Si ambas columnas se "
            "parecen, el modelo esta bien calibrado."
        )
        df_calib = pd.DataFrame(metricas["calibracion"])
        df_calib = df_calib.rename(columns={
            "rango": "Rango de probabilidad",
            "n": "Nº predicciones",
            "prob_media": "Modelo predijo (media)",
            "real": "Ocurrio realmente",
        })
        df_calib["Modelo predijo (media)"] = df_calib["Modelo predijo (media)"].map(
            lambda v: f"{v:.1f}%")
        df_calib["Ocurrio realmente"] = df_calib["Ocurrio realmente"].map(
            lambda v: f"{v:.1f}%")
        st.dataframe(df_calib, use_container_width=True, hide_index=True)
