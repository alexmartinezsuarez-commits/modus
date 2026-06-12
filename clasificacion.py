"""
clasificacion.py - Clasificaciones de grupo y de la fase final.

Calcula las tablas de clasificacion semanal por grupo (A/B/C) y la
clasificacion de la fase final del sabado, con su renderizado coloreado.

Depende de: config, data_loading.
"""

import streamlit as st
import pandas as pd
import numpy as np

from config import URLS, CORTES, GRUPOS_DIAS, COLORES_CLASIFICACION
from data_loading import cargar_todo

def detectar_grupo(jornada):
    """Mapea el nombre de jornada a su grupo. Devuelve None para Final/Resumen."""
    if not jornada:
        return None
    if "Grupo A" in jornada:
        return "Grupo A"
    if "Grupo B" in jornada:
        return "Grupo B"
    if "Grupo C" in jornada:
        return "Grupo C"
    return None

def calcular_clasificacion_grupo(grupo, dias_excluidos=None):
    """Calcula la clasificación de un grupo sumando todos los partidos terminados
    de los días que lo componen.

    dias_excluidos: lista opcional de nombres de jornada a NO contar
    (se usa para calcular la clasificación "previa" y sacar tendencias).

    Estructura asumida del DataFrame de partidos (idéntica a la usada en h2h):
        - iloc[0] = nombre del jugador
        - iloc[1] = legs ganados (4 = ganador en formato first-to-4)
        - filas pares (i, i+1) son cada partido

    Reglas:
        - PJ: partidos jugados
        - V/D: victorias/derrotas
        - LF/LC: legs a favor / en contra
        - DIF: LF - LC
        - PTS: 2 × V (sistema estándar de round-robin)

    Orden: PTS desc → DIF desc → LF desc.
    Solo se cuentan partidos terminados (alguien llegó a 4 legs).
    """
    if grupo not in GRUPOS_DIAS:
        return None

    excluidos = set(dias_excluidos or [])

    stats = {}  # key: nombre_lower → dict con stats
    for dia in GRUPOS_DIAS[grupo]:
        if dia in excluidos:
            continue
        try:
            df, _ = cargar_todo(URLS[dia], dia, CORTES[dia])
            if df is None or len(df) < 2:
                continue
            for i in range(0, len(df) - 1, 2):
                fila1 = df.iloc[i]
                fila2 = df.iloc[i + 1]
                nombre1 = str(fila1.iloc[0]).strip()
                nombre2 = str(fila2.iloc[0]).strip()
                # Saltar filas vacías o 'nan'
                if (not nombre1 or not nombre2 or
                        nombre1.lower() in ('nan', '') or
                        nombre2.lower() in ('nan', '')):
                    continue

                # Parsear legs (robusto contra strings vacíos, comas decimales o 'nan')
                def _parse_legs(val):
                    try:
                        return int(float(str(val).replace(',', '.').strip()))
                    except:
                        return -1

                legs1 = _parse_legs(fila1.iloc[1]) if len(fila1) > 1 else -1
                legs2 = _parse_legs(fila2.iloc[1]) if len(fila2) > 1 else -1

                if legs1 < 0 or legs2 < 0:
                    continue
                # Solo cuentan partidos terminados (alguien llegó a 4 legs)
                if legs1 < 4 and legs2 < 4:
                    continue

                # Inicializar entrada si no existe (.title() para nombre legible)
                for n in (nombre1, nombre2):
                    k = n.lower()
                    if k not in stats:
                        stats[k] = {
                            "Jugador": n.title(),
                            "PJ": 0, "V": 0, "D": 0,
                            "LF": 0, "LC": 0,
                        }

                k1, k2 = nombre1.lower(), nombre2.lower()
                stats[k1]["PJ"] += 1
                stats[k2]["PJ"] += 1
                stats[k1]["LF"] += legs1
                stats[k1]["LC"] += legs2
                stats[k2]["LF"] += legs2
                stats[k2]["LC"] += legs1
                if legs1 > legs2:
                    stats[k1]["V"] += 1
                    stats[k2]["D"] += 1
                else:
                    stats[k2]["V"] += 1
                    stats[k1]["D"] += 1
        except Exception:
            continue

    if not stats:
        return None

    # Construir DataFrame y aplicar criterios de desempate
    rows = []
    for v in stats.values():
        v["DIF"] = v["LF"] - v["LC"]
        v["PTS"] = v["V"] * 2
        rows.append(v)

    df = pd.DataFrame(rows)
    if df.empty:
        return None

    # Filtrar jugadores sin partidos jugados (residuos de semanas pasadas o nombres
    # cargados sin haber disputado encuentros válidos esta semana).
    df = df[df["PJ"] > 0].copy()
    if df.empty:
        return None

    df = df.sort_values(
        by=["PTS", "DIF", "LF"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    # Posición con medalla para el podio
    def _pos_emoji(idx):
        if idx == 0:
            return "🥇 1"
        if idx == 1:
            return "🥈 2"
        if idx == 2:
            return "🥉 3"
        return str(idx + 1)

    df.insert(0, "Pos", [_pos_emoji(i) for i in range(len(df))])
    return df[["Pos", "Jugador", "PJ", "V", "D", "LF", "LC", "DIF", "PTS"]]

def _ultimo_dia_con_datos(grupo):
    """Devuelve el nombre del ultimo dia del grupo que tiene partidos
    terminados, o None si ninguno tiene."""
    if grupo not in GRUPOS_DIAS:
        return None
    ultimo = None
    for dia in GRUPOS_DIAS[grupo]:
        try:
            df, _ = cargar_todo(URLS[dia], dia, CORTES[dia])
            if df is None or len(df) < 2:
                continue
            for i in range(0, len(df) - 1, 2):
                f1, f2 = df.iloc[i], df.iloc[i + 1]
                def _pl(v):
                    try:
                        return int(float(str(v).replace(',', '.').strip()))
                    except Exception:
                        return -1
                l1 = _pl(f1.iloc[1]) if len(f1) > 1 else -1
                l2 = _pl(f2.iloc[1]) if len(f2) > 1 else -1
                if l1 >= 4 or l2 >= 4:
                    ultimo = dia
                    break
        except Exception:
            continue
    return ultimo


def calcular_tendencias_grupo(grupo, df_actual):
    """Compara la clasificacion actual con la previa (sin el ultimo dia con
    datos) y devuelve un dict {jugador: '↑'|'↓'|'='}.

    Si solo hay un dia con datos (no hay 'previa'), devuelve dict vacio
    (sin flechas).
    """
    ultimo = _ultimo_dia_con_datos(grupo)
    if not ultimo:
        return {}
    # Si el ultimo dia es el primero del grupo, no hay clasificacion previa
    dias = GRUPOS_DIAS.get(grupo, [])
    if not dias or dias[0] == ultimo:
        return {}

    df_previa = calcular_clasificacion_grupo(grupo, dias_excluidos=[ultimo])
    if df_previa is None or df_previa.empty:
        return {}

    pos_previa = {row["Jugador"]: i for i, (_, row) in enumerate(df_previa.iterrows())}
    tendencias = {}
    for i, (_, row) in enumerate(df_actual.iterrows()):
        nombre = row["Jugador"]
        if nombre not in pos_previa:
            tendencias[nombre] = "🆕"
            continue
        prev = pos_previa[nombre]
        if i < prev:
            tendencias[nombre] = "↑"
        elif i > prev:
            tendencias[nombre] = "↓"
        else:
            tendencias[nombre] = "="
    return tendencias


def render_clasificacion_grupo(grupo):
    """Renderiza la tabla de clasificación de un grupo aplicando los colores
    configurados en COLORES_CLASIFICACION (verdes desde arriba, rojos desde abajo),
    con flechas de tendencia y barra de progreso visual en PTS.

    Si verdes + rojos > nº de jugadores, el verde tiene prioridad para evitar
    pintar la misma fila dos veces.
    """
    df = calcular_clasificacion_grupo(grupo)
    if df is None or df.empty:
        st.info(f"ℹ️ Aún no hay partidos terminados en {grupo}")
        return

    st.subheader(f"🏆 Clasificación {grupo}")

    # ── Flechas de tendencia (vs clasificacion sin el ultimo dia) ─────────
    tendencias = calcular_tendencias_grupo(grupo, df)
    if tendencias:
        df = df.copy()
        df.insert(1, "Tend", [tendencias.get(j, "") for j in df["Jugador"]])

    n = len(df)
    config = COLORES_CLASIFICACION.get(grupo, {"verdes": 1, "rojos": 0})
    n_verdes = config["verdes"]
    n_rojos = config["rojos"]
    umbral_rojo = n - n_rojos  # filas con idx >= umbral_rojo van en rojo

    pts_max = df["PTS"].max() if "PTS" in df.columns and n > 0 else 0

    def estilo_fila(fila):
        idx = fila.name
        if idx < n_verdes:
            base = 'background-color: rgba(40,167,69,0.18); font-weight: 600;'
        elif n_rojos > 0 and idx >= umbral_rojo:
            base = 'background-color: rgba(220,53,69,0.12);'
        else:
            base = ''
        estilos = [base] * len(fila)
        # Barra de progreso visual en la celda PTS (proporcional al lider)
        if pts_max > 0 and "PTS" in fila.index:
            try:
                pct = max(0, min(100, round(100 * fila["PTS"] / pts_max)))
                col_idx = list(fila.index).index("PTS")
                estilos[col_idx] = (
                    f'background: linear-gradient(90deg, '
                    f'rgba(59,130,246,0.35) {pct}%, transparent {pct}%); '
                    f'font-weight: 700;'
                )
            except Exception:
                pass
        # Colorear la flecha de tendencia
        if "Tend" in fila.index:
            try:
                t_idx = list(fila.index).index("Tend")
                t = fila["Tend"]
                if t == "↑":
                    estilos[t_idx] = base + 'color: #16a34a; font-weight: 900;'
                elif t == "↓":
                    estilos[t_idx] = base + 'color: #dc2626; font-weight: 900;'
                else:
                    estilos[t_idx] = base + 'color: #94a3b8;'
            except Exception:
                pass
        return estilos

    styled = df.style.apply(estilo_fila, axis=1).set_properties(**{
        'text-align': 'center',
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
        {'selector': 'th.col_heading', 'props': [('background-color', '#1f2937'), ('color', 'white')]},
    ])

    st.dataframe(styled, use_container_width=True, hide_index=True)
    leyenda = ("💡 Orden: **PTS** (2 por victoria) → **DIF** (legs a favor − en contra) → **LF** (legs a favor)")
    if tendencias:
        leyenda += " · **Tend**: posición vs día anterior (↑ sube, ↓ baja, = igual)"
    st.caption(leyenda)

def _ranking_grupo_semana(grupo):
    """Devuelve la clasificación ordenada de un grupo semanal (lista de nombres
    en orden 1º, 2º, 3º...). Si no hay datos, devuelve []."""
    df = calcular_clasificacion_grupo(grupo)
    if df is None or df.empty:
        return []
    return df["Jugador"].tolist()

def construir_grupos_final():
    """Construye los dos grupos de la Final Sábado a partir de los resultados
    de la fase de grupos semanal.

    Composición:
        Final Grupo A:
            - 1º del Grupo A (Lun-Mar-Mié)
            - 2º del Grupo B (Jue-Vie)
            - 2º del Grupo C (Jue-Vie)
        Final Grupo B:
            - 1º del Grupo B (Jue-Vie)
            - 1º del Grupo C (Jue-Vie)
            - 3º del Grupo B (Jue-Vie)

    Devuelve dict {"Grupo A Final": [...], "Grupo B Final": [...]}, con cada
    valor siendo lista de dicts {jugador, procedencia}. Si falta algún rango
    en algún grupo, se omite ese hueco (la lista será más corta).
    """
    rank_a = _ranking_grupo_semana("Grupo A")
    rank_b = _ranking_grupo_semana("Grupo B")
    rank_c = _ranking_grupo_semana("Grupo C")

    def _get(rank, idx):
        return rank[idx] if idx < len(rank) else None

    grupo_a_final = []
    for nombre, proc in [
        (_get(rank_a, 0), "1º Grupo A"),
        (_get(rank_b, 1), "2º Grupo B"),
        (_get(rank_c, 1), "2º Grupo C"),
    ]:
        if nombre:
            grupo_a_final.append({"jugador": nombre, "procedencia": proc})

    grupo_b_final = []
    for nombre, proc in [
        (_get(rank_b, 0), "1º Grupo B"),
        (_get(rank_c, 0), "1º Grupo C"),
        (_get(rank_b, 2), "3º Grupo B"),
    ]:
        if nombre:
            grupo_b_final.append({"jugador": nombre, "procedencia": proc})

    return {"Grupo A Final": grupo_a_final, "Grupo B Final": grupo_b_final}

def calcular_clasificacion_final(jugadores_del_grupo):
    """Calcula la clasificación del grupo de Final Sábado a partir de los
    partidos disputados ESE día. Recibe la lista de jugadores que conforman
    el grupo (los que debe filtrar de Final Sábado) y devuelve un DataFrame
    con las mismas columnas que `calcular_clasificacion_grupo`.

    A diferencia de la clasificación semanal (que suma 3 o 2 días), esta solo
    lee la pestaña 'Final Sábado' y filtra para que el grupo solo refleje los
    partidos entre los 3 jugadores que componen ese grupo de la final.
    """
    if not jugadores_del_grupo:
        return None

    # `jugadores_del_grupo` puede llegar como lista de dicts {"jugador":..., "procedencia":...}
    # (caso normal desde construir_grupos_final) o, defensivamente, como lista de strings.
    # Normalizamos a lista de nombres (str) descartando vacíos / NaN.
    def _nombre_de(item):
        if isinstance(item, dict):
            return str(item.get("jugador", "")).strip()
        if item is None:
            return ""
        return str(item).strip()

    nombres_jugadores = [
        n for n in (_nombre_de(j) for j in jugadores_del_grupo)
        if n and n.lower() != 'nan'
    ]
    if not nombres_jugadores:
        return None

    nombres_grupo = {n.lower() for n in nombres_jugadores}

    stats = {}
    try:
        df, _ = cargar_todo(URLS["Final Sábado"], "Final Sábado", CORTES["Final Sábado"])
    except Exception:
        df = None
    if df is None or len(df) < 2:
        # Pre-rellenar para que aparezcan los 3 jugadores aunque aún no haya partidos
        for jugador in nombres_jugadores:
            k = jugador.lower()
            stats[k] = {"Jugador": jugador, "PJ": 0, "V": 0, "D": 0, "LF": 0, "LC": 0}
    else:
        # Pre-rellenar entradas de los jugadores del grupo para que aparezcan
        # aunque aún no hayan jugado ningún partido
        for jugador in nombres_jugadores:
            k = jugador.lower()
            stats[k] = {"Jugador": jugador, "PJ": 0, "V": 0, "D": 0, "LF": 0, "LC": 0}

        for i in range(0, len(df) - 1, 2):
            fila1 = df.iloc[i]
            fila2 = df.iloc[i + 1]
            nombre1 = str(fila1.iloc[0]).strip()
            nombre2 = str(fila2.iloc[0]).strip()
            if (not nombre1 or not nombre2 or
                    nombre1.lower() in ('nan', '') or
                    nombre2.lower() in ('nan', '')):
                continue

            # Filtro clave: el partido solo cuenta si AMBOS jugadores están en el grupo
            if nombre1.lower() not in nombres_grupo or nombre2.lower() not in nombres_grupo:
                continue

            def _parse_legs(val):
                try:
                    return int(float(str(val).replace(',', '.').strip()))
                except:
                    return -1

            legs1 = _parse_legs(fila1.iloc[1]) if len(fila1) > 1 else -1
            legs2 = _parse_legs(fila2.iloc[1]) if len(fila2) > 1 else -1
            if legs1 < 0 or legs2 < 0:
                continue
            if legs1 < 4 and legs2 < 4:
                continue

            k1, k2 = nombre1.lower(), nombre2.lower()
            stats[k1]["PJ"] += 1
            stats[k2]["PJ"] += 1
            stats[k1]["LF"] += legs1
            stats[k1]["LC"] += legs2
            stats[k2]["LF"] += legs2
            stats[k2]["LC"] += legs1
            if legs1 > legs2:
                stats[k1]["V"] += 1
                stats[k2]["D"] += 1
            else:
                stats[k2]["V"] += 1
                stats[k1]["D"] += 1

    rows = []
    for v in stats.values():
        v["DIF"] = v["LF"] - v["LC"]
        v["PTS"] = v["V"] * 2
        rows.append(v)

    df_out = pd.DataFrame(rows)
    if df_out.empty:
        return None

    df_out = df_out.sort_values(
        by=["PTS", "DIF", "LF"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    def _pos_emoji(idx):
        if idx == 0:
            return "🥇 1"
        if idx == 1:
            return "🥈 2"
        if idx == 2:
            return "🥉 3"
        return str(idx + 1)

    df_out.insert(0, "Pos", [_pos_emoji(i) for i in range(len(df_out))])
    return df_out[["Pos", "Jugador", "PJ", "V", "D", "LF", "LC", "DIF", "PTS"]]

def render_clasificacion_final(nombre_grupo, jugadores_del_grupo):
    """Renderiza la clasificación de uno de los grupos de la Final Sábado.

    Reglas de pintado (igual que pediste):
        - 2 primeros en verde (pasan a semifinales)
        - último (tercero) en rojo
    """
    df = calcular_clasificacion_final(jugadores_del_grupo)
    if df is None or df.empty:
        st.info(f"ℹ️ Aún no hay datos para {nombre_grupo}")
        return

    st.subheader(f"🏆 {nombre_grupo}")
    # Composición: tolerante a items dict o a strings sueltos.
    _trozos = []
    for j in jugadores_del_grupo:
        if isinstance(j, dict):
            nom = str(j.get("jugador", "")).strip()
            proc = str(j.get("procedencia", "")).strip()
            if nom:
                _trozos.append(f"**{nom}** ({proc})" if proc else f"**{nom}**")
        elif j:
            nom = str(j).strip()
            if nom and nom.lower() != 'nan':
                _trozos.append(f"**{nom}**")
    if _trozos:
        st.caption("Composición: " + " · ".join(_trozos))

    n = len(df)

    def estilo_fila(fila):
        idx = fila.name
        if idx < 2:
            return ['background-color: rgba(40,167,69,0.18); font-weight: 600;'] * len(fila)
        if idx == n - 1 and n >= 3:
            return ['background-color: rgba(220,53,69,0.12);'] * len(fila)
        return [''] * len(fila)

    styled = df.style.apply(estilo_fila, axis=1).set_properties(**{
        'text-align': 'center',
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
        {'selector': 'th.col_heading', 'props': [('background-color', '#1f2937'), ('color', 'white')]},
    ])

    st.dataframe(styled, use_container_width=True, hide_index=True)
