"""
data_loading.py - Carga y parsing de las hojas de calculo de Google Sheets.

Funciones para leer cada pestana del spreadsheet (jornadas diarias, Resumen
Semanal, Value Bets), extraer las estadisticas de cada jugador y consultar
la API de partidos en vivo.

Depende de: config (URLS, CORTES) y helpers (safe_float, _buscar_stat).
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

from config import URLS, CORTES
from helpers import safe_float, _buscar_stat

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

def extraer_stats_diarias(df, fila_n, col_rango):
    """Extrae estadísticas por jugador desde la sección derecha de cada pestaña diaria.
    
    Estructura del spreadsheet:
        col_rango[0] (ej. col G): contiene TANTO los títulos de stats (filas pares)
                                  COMO los valores del PRIMER jugador (filas impares).
        col_rango[0]+1, +2, ... : valores de los jugadores 2, 3, ...
    
    Por esa razón, al construir el set de títulos para evitar capturar un título
    como falso valor, hay que filtrar usando una heurística que distinga:
        - Títulos:  texto con varias letras (ej. "Media 180 por partida")
        - Valores:  números o porcentajes (ej. "2,0", "89,88", "42%", "#DIV/0!")
    
    Robustez añadida vs. versión original:
    - Rango ampliado de 35 → 60 filas (Grupo C Jueves tiene más separadores).
    - Set de títulos para anular el fallback `val_fila2` cuando captura erróneamente
      otro título (bug que mostraba "Legs por partido" como valor de Puntuación Global).
    - Fallback con secuencia canónica de títulos: si una pestaña tiene celdas
      combinadas/vacías que ocultan los títulos en CSV (caso Grupo B Jueves donde
      sólo se leen los 3-4 primeros), se completa con los títulos esperados en orden
      basándose en filas de valores numéricos huérfanas.
    """
    
    # Secuencia canónica de títulos (orden FIJO del spreadsheet, según se ve en
    # la captura del sheet real de Grupo C/B Jueves):
    #   Media 180 → Promedio puntos → Diferencia de legs → Promedio Checkouts →
    #   Número victorias → Número derrotas → Porcentaje victoria →
    #   PUNTIACIÓN GLOBAL → Legs por partido (al final, no al principio)
    SECUENCIA_TITULOS = [
        "Media 180 por partida",
        "Promedio puntos total",
        "Diferencia de legs",
        "Promedio Checkouts",
        "Número victorias",
        "Número derrotas",
        "Porcentaje victoria",
        "PUNTIACIÓN GLOBAL (0-100)",
        "Legs por partido",
        "Índice Volatilidad",
    ]
    
    def parece_titulo(s):
        """Distingue títulos vs valores numéricos.
        
        Un título debe:
        - Tener al menos 5 caracteres
        - Contener al menos 3 letras alfabéticas
        - No empezar con '#' (descarta errores tipo #DIV/0!)
        """
        s = s.strip()
        if len(s) < 5:
            return False
        if s.startswith('#'):
            return False
        letras = sum(1 for c in s if c.isalpha())
        return letras >= 3
    
    def parece_valor(s):
        """Detecta si la cadena parece un valor numérico (no un título).
        Acepta números con coma/punto decimal, porcentajes, enteros y errores #DIV/0!.
        """
        s = s.strip()
        if not s or s.lower() == 'nan':
            return False
        if s.startswith('#'):  # #DIV/0!, #N/A, etc.
            return True
        # Limpiar % y convertir coma a punto para intentar parsear como float
        try:
            float(s.replace('%', '').replace(',', '.').strip())
            return True
        except:
            return False
    
    try:
        nombres = df.iloc[fila_n, col_rango[0]:col_rango[1]].values
        jugadores = [str(n).strip() for n in nombres if str(n).strip() not in ['nan', '']]
        
        # Rango ampliado para cubrir pestañas con más separadores
        limite = min(len(df), fila_n + 60)
        
        # Pre-recolectar SOLO strings que parezcan títulos reales en col_rango[0]
        # (la columna donde van los títulos de stats en el sheet).
        titulos_set = set()
        for f in range(fila_n + 1, limite):
            t = str(df.iloc[f, col_rango[0]]).strip()
            if t and t.lower() != 'nan' and parece_titulo(t):
                titulos_set.add(t.lower())
        
        # PRIMER PASE: identificar la estructura real del bloque
        # Recorremos filas y clasificamos cada una como TÍTULO, VALORES o VACÍA.
        estructura = []  # lista de (fila_idx, tipo, dato)
        for f in range(fila_n + 1, limite):
            t = str(df.iloc[f, col_rango[0]]).strip()
            es_titulo_explicito = t and t.lower() != 'nan' and parece_titulo(t)
            
            # ¿Hay valores en las columnas de los jugadores 2..N?
            hay_valores_otros_jugadores = False
            for i in range(1, len(jugadores)):
                col = col_rango[0] + i
                if col < df.shape[1]:
                    v = str(df.iloc[f, col]).strip()
                    if parece_valor(v):
                        hay_valores_otros_jugadores = True
                        break
            
            # ¿La col_rango[0] tiene un valor numérico (valor del primer jugador)?
            col0_es_valor = parece_valor(t)
            
            if es_titulo_explicito:
                estructura.append((f, 'titulo', t))
            elif hay_valores_otros_jugadores or col0_es_valor:
                estructura.append((f, 'valores', None))
            # filas completamente vacías se ignoran
        
        # SEGUNDO PASE: emparejar títulos con sus valores.
        # Buscamos patrones (titulo) + (valores) y, cuando falte un título antes
        # de unos valores huérfanos, deducimos el título por la posición canónica.
        idx_secuencia = 0  # qué título canónico nos toca esperar
        pares = []  # lista de (titulo_resuelto, fila_de_valores)
        i = 0
        while i < len(estructura):
            f, tipo, dato = estructura[i]
            if tipo == 'titulo':
                # Sincronizar la secuencia canónica con este título explícito
                titulo_lower = dato.lower()
                for k, esp in enumerate(SECUENCIA_TITULOS):
                    if esp.lower() in titulo_lower or titulo_lower in esp.lower():
                        idx_secuencia = k + 1
                        break
                else:
                    idx_secuencia += 1
                # Buscar la siguiente fila de valores
                if i + 1 < len(estructura) and estructura[i + 1][1] == 'valores':
                    pares.append((dato, estructura[i + 1][0]))
                    i += 2
                    continue
                i += 1
            elif tipo == 'valores':
                # Valores huérfanos: usar el siguiente título canónico
                if idx_secuencia < len(SECUENCIA_TITULOS):
                    titulo_deducido = SECUENCIA_TITULOS[idx_secuencia]
                    pares.append((titulo_deducido, f))
                    idx_secuencia += 1
                i += 1
            else:
                i += 1
        
        # TERCER PASE: extraer los valores de cada par para cada jugador.
        # Para el PRIMER jugador (i=0), si su celda principal en la fila de valores
        # está vacía pero los demás jugadores SÍ tienen valor en esa fila, asumimos
        # que el primer jugador tiene 0 (la stat existe pero no la ha logrado).
        # Esto cubre el caso de Grupo B Jueves donde celdas combinadas dejan vacía
        # la columna del primer jugador en algunas filas (Número victorias, etc.).
        data_final = {}
        for i, j in enumerate(jugadores):
            stats = {}
            for titulo, fila_valores in pares:
                col = col_rango[0] + i
                v = ''
                if col < df.shape[1]:
                    v = str(df.iloc[fila_valores, col]).strip()
                    if v.lower() in titulos_set:
                        v = ''
                
                # Fallback solo para el primer jugador: si su celda está vacía pero
                # los demás jugadores tienen valor, asumir 0.
                if i == 0 and (not v or v.lower() == 'nan'):
                    otros_tienen_valor = False
                    for k in range(1, len(jugadores)):
                        col_otro = col_rango[0] + k
                        if col_otro < df.shape[1]:
                            v_otro = str(df.iloc[fila_valores, col_otro]).strip()
                            if v_otro and v_otro.lower() != 'nan' and parece_valor(v_otro):
                                otros_tienen_valor = True
                                break
                    if otros_tienen_valor:
                        # Detectar si la stat es porcentaje para mantener formato
                        ejemplo_val = str(df.iloc[fila_valores, col_rango[0] + 1]).strip()
                        v = '0%' if '%' in ejemplo_val else '0'
                
                if v and v.lower() != 'nan':
                    stats[titulo] = v
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
        
        # Caso especial: Resumen Semanal tiene formato tabla horizontal
        # (jugadores en filas, stats en columnas), distinto del resto.
        if pestana == "Resumen Semanal":
            stats_dict = extraer_stats_resumen_semanal(df)
            jugadores = {}
            for nombre_lower, s in stats_dict.items():
                pr       = safe_float(_buscar_stat(s, ["puntiación global", "puntuación global", "puntacion global", "puntuación", "puntiación"]))
                lam_180  = safe_float(_buscar_stat(s, ["media 180", "180 por partida", "180 por partido"]))
                lam_legs = safe_float(_buscar_stat(s, ["legs totales", "total legs", "legs por partido", "promedio legs", "leg por partido"]))
                promedio_dardos = safe_float(_buscar_stat(s, ["promedio puntos", "average", "promedio dardos", "ppd", "media puntos"]))
                
                # Checkout: en Resumen Semanal puede venir como decimal (0,3077) o como porcentaje (30,77%).
                # Si está entre 0 y 1, asumimos que es ratio decimal y convertimos a porcentaje.
                raw_checkout = str(_buscar_stat(s, ["checkout"])).replace("%", "").replace(",", ".").strip()
                checkouts = safe_float(raw_checkout)
                if 0 < checkouts <= 1:
                    checkouts *= 100
                
                # Porcentaje victoria: misma lógica defensiva
                raw_pct = str(_buscar_stat(s, ["porcentaje victoria", "% victoria"])).replace("%", "").replace(",", ".").strip()
                pct_vic = safe_float(raw_pct)
                if 0 < pct_vic <= 1:
                    pct_vic *= 100
                
                # Índice de volatilidad (irregularidad del rendimiento)
                volatilidad = safe_float(_buscar_stat(s, ["índice volatilidad", "indice volatilidad", "índice de volatilidad", "volatilidad"]))
                
                jugadores[nombre_lower] = {
                    "nombre_original": nombre_lower.title(),
                    "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                    "promedio_dardos": promedio_dardos,
                    "checkouts": checkouts, "pct_victorias": pct_vic,
                    "volatilidad": volatilidad
                }
            return jugadores
        
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
                    lam_180  = safe_float(_buscar_stat(s, ["media 180", "180 por partida", "180 por partido"]))
                    lam_legs = safe_float(_buscar_stat(s, ["legs totales", "total legs", "legs por partido", "promedio legs", "leg por partido"]))
                    promedio_dardos = safe_float(_buscar_stat(s, ["promedio puntos", "average", "promedio dardos", "ppd", "media puntos"]))
                    
                    # Checkout: defensivo contra ratio decimal (0,46 → 46%)
                    raw_ck = str(_buscar_stat(s, ["checkout"])).replace("%", "").replace(",", ".").strip()
                    checkouts = safe_float(raw_ck)
                    if 0 < checkouts <= 1:
                        checkouts *= 100
                    
                    # Porcentaje victoria: misma lógica
                    raw_pv = str(_buscar_stat(s, ["porcentaje victoria", "% victoria"])).replace("%", "").replace(",", ".").strip()
                    pct_vic = safe_float(raw_pv)
                    if 0 < pct_vic <= 1:
                        pct_vic *= 100
                    
                    # Índice de volatilidad (irregularidad del rendimiento)
                    volatilidad = safe_float(_buscar_stat(s, ["índice volatilidad", "indice volatilidad", "índice de volatilidad", "volatilidad"]))
                    
                    jugadores[nombre.lower()] = {
                        "nombre_original": nombre,
                        "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                        "promedio_dardos": promedio_dardos,
                        "checkouts": checkouts, "pct_victorias": pct_vic,
                        "volatilidad": volatilidad
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
        col_180     = buscar_col(["media 180", "180 por partida", "180 por partido"])
        col_legs    = buscar_col(["legs totales", "total legs", "legs por partido", "leg por partido"])
        col_promedio_dardos = buscar_col(["promedio puntos", "average", "promedio dardos", "ppd", "media puntos"])
        col_checkouts = buscar_col(["checkout"])
        col_pct_vic = buscar_col(["porcentaje victoria", "% victoria", "% victoria", "%victoria"])
        col_volatilidad = buscar_col(["índice volatilidad", "indice volatilidad", "volatilidad"])
        jugadores = {}
        for _, fila in data.iterrows():
            nombre = str(fila.get(col_jugador, "")).strip() if col_jugador else ""
            if not nombre or nombre.lower() in ["nan", "jugador", ""]:
                continue
            pr       = safe_float(fila.get(col_pr,    0)) if col_pr    else 0.0
            lam_180  = safe_float(fila.get(col_180,   0)) if col_180   else 0.0
            lam_legs = safe_float(fila.get(col_legs,  0)) if col_legs  else 0.0
            promedio_dardos = safe_float(fila.get(col_promedio_dardos, 0)) if col_promedio_dardos else 0.0
            
            # Checkout y % victoria con conversión defensiva 0-1 → 0-100
            raw_ck = str(fila.get(col_checkouts, 0)).replace("%", "").replace(",", ".").strip() if col_checkouts else "0"
            checkouts = safe_float(raw_ck)
            if 0 < checkouts <= 1:
                checkouts *= 100
            
            raw_pv = str(fila.get(col_pct_vic, 0)).replace("%", "").replace(",", ".").strip() if col_pct_vic else "0"
            pct_vic = safe_float(raw_pv)
            if 0 < pct_vic <= 1:
                pct_vic *= 100
            
            # Índice de volatilidad (irregularidad del rendimiento)
            volatilidad = safe_float(fila.get(col_volatilidad, 0)) if col_volatilidad else 0.0
            
            jugadores[nombre.lower()] = {
                "nombre_original": nombre,
                "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                "promedio_dardos": promedio_dardos,
                "checkouts": checkouts, "pct_victorias": pct_vic,
                "volatilidad": volatilidad
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
                # Añadir el índice de volatilidad al final
                for k, v in stat_dict.items():
                    if "volatilidad" in k.lower():
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


@st.cache_data(ttl=60)
def obtener_proximos_partidos_api(limite=3):
    """Devuelve los próximos partidos que aún NO han empezado.

    A diferencia de obtener_partidos_vivos_api (que filtra los partidos en
    curso o terminados), esta función se queda con los que tienen estado
    "not started" y devuelve los `limite` primeros, ordenados por fecha/hora.

    No pide el detalle de cada fixture porque las estadísticas solo existen
    una vez el partido ha comenzado; aquí solo interesan los nombres de los
    dos jugadores para autocompletar el selector de Value Bets.

    DEVUELVE UN DICT con dos claves:
        - "partidos": lista de dicts {id, j1, j2, fecha, etiqueta}
        - "diagnostico": string explicando qué pasó (para mostrar al usuario
          si la lista sale vacía). Cadena vacía si todo fue bien.

    De esta forma el frontend puede distinguir entre "la API falló",
    "la API respondió pero no hay próximos partidos" y "todo OK".
    """
    base_url = "https://api-igamedc.igamemedia.com/api/mss-web"

    # Paso 1: petición raíz para saber semana y grupos activos
    try:
        response = requests.get(f"{base_url}/results-fixtures", timeout=8)
    except Exception as e:
        return {"partidos": [],
                "diagnostico": f"No se pudo conectar con la API de MODUS ({type(e).__name__})."}

    if response.status_code != 200:
        return {"partidos": [],
                "diagnostico": f"La API de MODUS respondió con código {response.status_code}."}

    try:
        data = response.json()
    except Exception:
        return {"partidos": [],
                "diagnostico": "La API de MODUS no devolvió un JSON válido."}

    week_activa = data.get("selected", {}).get("week", "")
    grupos = data.get("selected", {}).get("groups",
                                          [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 8}])

    proximos = []
    vistos = set()       # evita duplicados si un fixture aparece en varios grupos
    total_fixtures = 0   # cuántos fixtures vimos en total
    estados_vistos = {}  # recuento de estados, para diagnóstico

    for grupo in grupos:
        url = f"{base_url}/results-fixtures?group={grupo.get('id')}"
        if week_activa:
            url += f"&week={week_activa}"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            cuerpo = resp.json()
            fixtures = cuerpo.get("Fixtures", cuerpo.get("fixtures", []))
            for fixture in fixtures:
                total_fixtures += 1
                estado = (fixture.get("status", "") or "").lower().strip()
                estados_vistos[estado] = estados_vistos.get(estado, 0) + 1
                # Solo partidos que no han empezado.
                # Aceptamos varias formas de escribirlo por si la API cambia.
                if estado not in ("not started", "notstarted", "scheduled",
                                  "upcoming", "pending", ""):
                    continue
                j1 = (fixture.get("playerHome", "") or "").strip()
                j2 = (fixture.get("playerAway", "") or "").strip()
                if not j1 or not j2:
                    continue
                fixture_id = (fixture.get("gameId") or fixture.get("Id")
                              or fixture.get("id") or f"{j1}-{j2}")
                if fixture_id in vistos:
                    continue
                vistos.add(fixture_id)
                # La API puede nombrar la fecha de varias formas; probamos
                # las más habituales y nos quedamos con la primera no vacía.
                fecha = ""
                for campo in ("fixture", "date", "startDate", "startTime",
                              "scheduledTime", "kickoff", "Date", "dateTime"):
                    val = fixture.get(campo, "")
                    if val:
                        fecha = str(val)
                        break
                proximos.append({
                    "id": fixture_id,
                    "j1": j1,
                    "j2": j2,
                    "fecha": fecha,
                    "_sort": fecha or "zzzz",
                })
        except Exception:
            continue

    # Ordenar cronológicamente (la API suele dar fechas ISO ordenables)
    proximos.sort(key=lambda p: p["_sort"])

    # Construir etiqueta legible para el desplegable
    resultado = []
    for p in proximos[:limite]:
        if p["fecha"]:
            etiqueta = f"{p['j1']} vs {p['j2']}  ·  {p['fecha']}"
        else:
            etiqueta = f"{p['j1']} vs {p['j2']}"
        resultado.append({
            "id": p["id"],
            "j1": p["j1"],
            "j2": p["j2"],
            "fecha": p["fecha"],
            "etiqueta": etiqueta,
        })

    # Diagnóstico para el caso de lista vacía
    if resultado:
        diag = ""
    elif total_fixtures == 0:
        diag = "La API de MODUS respondió pero no devolvió ningún partido."
    else:
        resumen_estados = ", ".join(f"{k or 'sin estado'}: {v}"
                                    for k, v in estados_vistos.items())
        diag = (f"La API devolvió {total_fixtures} partido(s), pero ninguno "
                f"está pendiente de empezar. Estados encontrados → {resumen_estados}.")

    return {"partidos": resultado, "diagnostico": diag}


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
