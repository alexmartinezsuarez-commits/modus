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
import re
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
                
                # Numero de partidos jugados = victorias + derrotas.
                # Se usa para ponderar la fuente "Forma reciente".
                n_vic = safe_float(_buscar_stat(s, ["número victorias", "numero victorias", "victorias"]))
                n_der = safe_float(_buscar_stat(s, ["número derrotas", "numero derrotas", "derrotas"]))
                n_partidos = int(n_vic) + int(n_der)

                jugadores[nombre_lower] = {
                    "nombre_original": nombre_lower.title(),
                    "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                    "promedio_dardos": promedio_dardos,
                    "checkouts": checkouts, "pct_victorias": pct_vic,
                    "volatilidad": volatilidad,
                    "n_partidos": n_partidos,
                    "victorias": int(n_vic),
                    "derrotas": int(n_der),
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
                    
                    # Numero de partidos jugados = victorias + derrotas.
                    n_vic = safe_float(_buscar_stat(s, ["número victorias", "numero victorias", "victorias"]))
                    n_der = safe_float(_buscar_stat(s, ["número derrotas", "numero derrotas", "derrotas"]))
                    n_partidos = int(n_vic) + int(n_der)

                    jugadores[nombre.lower()] = {
                        "nombre_original": nombre,
                        "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                        "promedio_dardos": promedio_dardos,
                        "checkouts": checkouts, "pct_victorias": pct_vic,
                        "volatilidad": volatilidad,
                        "n_partidos": n_partidos,
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

            # Numero de partidos jugados = victorias + derrotas.
            col_vic = buscar_col(["número victorias", "numero victorias", "victorias"])
            col_der = buscar_col(["número derrotas", "numero derrotas", "derrotas"])
            n_vic = safe_float(fila.get(col_vic, 0)) if col_vic else 0.0
            n_der = safe_float(fila.get(col_der, 0)) if col_der else 0.0
            n_partidos = int(n_vic) + int(n_der)

            jugadores[nombre.lower()] = {
                "nombre_original": nombre,
                "PR": pr, "lam_180": lam_180, "lam_legs": lam_legs,
                "promedio_dardos": promedio_dardos,
                "checkouts": checkouts, "pct_victorias": pct_vic,
                "volatilidad": volatilidad,
                "n_partidos": n_partidos,
            }
        return jugadores
    except Exception as e:
        st.error(f"Error cargando {pestana}: {e}")
        return {}


# Pestanas de jornada candidatas a ser "la jornada de hoy", en orden
# cronologico del torneo (lunes -> sabado).
# Pestanas de jornada candidatas a ser "la jornada de hoy", en orden
# cronologico del torneo. IMPORTANTE: jueves y viernes el Grupo C juega
# por la manana y el Grupo B por la noche, asi que C va ANTES que B.
_JORNADAS_ORDEN = [
    "Grupo A Lunes", "Grupo A Martes", "Grupo A Miércoles",
    "Grupo C Jueves", "Grupo B Jueves",
    "Grupo C Viernes", "Grupo B Viernes",
    "Final Sábado",
]


def detectar_jornada_de_hoy():
    """Detecta cual es la jornada activa AHORA segun el dia de la semana y
    la hora del dia. Reglas del torneo MODUS:

      Lun/Mar/Mie 10:00 - 23:59  -> Grupo A de ese dia
      Jue/Vie     14:00 - 22:59  -> Grupo C de ese dia
      Jue/Vie     23:00 - 23:59  -> Grupo B de ese dia
      Vie/Sab     00:00 - 03:00  -> Grupo B del dia ANTERIOR
                                    (la sesion de la noche se prolonga)
      Sab         14:00 - 23:59  -> Final Sabado

    Fuera de esos rangos -> None ("sin jornada activa").

    Despues de aplicar la regla horaria, comprueba que la pestana
    correspondiente tenga datos cargados. Si no los tiene, devuelve None
    (la app la considera no disponible todavia).
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        # Si zoneinfo no esta disponible, caemos a hora local (peor pero
        # no rompe la app)
        ahora = datetime.now()
    wd = ahora.weekday()  # 0=lunes, 1=martes ... 5=sabado, 6=domingo
    h = ahora.hour

    DIAS_A = {0: "Grupo A Lunes", 1: "Grupo A Martes", 2: "Grupo A Miércoles"}
    DIAS_C = {3: "Grupo C Jueves", 4: "Grupo C Viernes"}
    DIAS_B = {3: "Grupo B Jueves", 4: "Grupo B Viernes"}

    jornada = None
    minuto = ahora.minute
    mnow = h * 60 + minuto  # minutos desde medianoche, para comparar facil

    # Reglas (todas en hora Madrid):
    #   Lun/Mar/Mie 10:30 - 16:00  -> Grupo A de ese dia
    #   Jue/Vie     14:00 - 19:00  -> Grupo C
    #   Jue/Vie     21:00 - 23:59  -> Grupo B
    #   Vie/Sab     00:00 - 03:00  -> Grupo B del dia anterior (prolongacion)
    #   Sab         20:40 - 23:59  -> Final Sabado
    #   Dom         00:00 - 03:00  -> Final Sabado (prolongacion, cierra)
    #
    # Madrugada (00:00 - 03:00) -> prolongacion del dia anterior:
    if mnow <= 3 * 60:   # 00:00 - 03:00
        if wd == 4:        # viernes madrugada -> B Jueves
            jornada = DIAS_B[3]
        elif wd == 5:      # sabado madrugada -> B Viernes
            jornada = DIAS_B[4]
        elif wd == 6:      # domingo madrugada -> cierre Final
            jornada = "Final Sábado"
    else:
        if wd in DIAS_A:
            # Lun/Mar/Mie: 10:30 - 16:00
            if 10 * 60 + 30 <= mnow <= 16 * 60:
                jornada = DIAS_A[wd]
        elif wd in DIAS_C:  # jue/vie
            if 14 * 60 <= mnow <= 19 * 60:
                jornada = DIAS_C[wd]   # Grupo C 14:00 - 19:00
            elif 21 * 60 <= mnow:
                jornada = DIAS_B[wd]   # Grupo B 21:00 - 23:59
        elif wd == 5:  # sabado: Final 20:40 - 23:59
            if mnow >= 20 * 60 + 40:
                jornada = "Final Sábado"

    if jornada is None:
        return None

    # Comprobar que la pestana tenga datos cargados. Si todavia no, la
    # consideramos no disponible.
    try:
        jug = cargar_jugadores_desde(jornada)
    except Exception:
        jug = {}
    if not jug:
        return None
    return jornada


def proxima_jornada():
    """Devuelve (nombre_jornada, hora_inicio_str) de la PROXIMA jornada
    que va a empezar, desde el momento actual. Util para mostrar 'Sin
    jornada activa - proxima: Grupo A Lunes a las 10:00'.

    Si ya estamos en horario de jornada, devuelve None (significa que no
    procede mostrar 'proxima', porque ya hay una activa).

    Devuelve (None, None) si no hay proxima identificable.
    """
    from datetime import datetime, timedelta
    try:
        from zoneinfo import ZoneInfo
        ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        ahora = datetime.now()

    # Inicios de cada jornada (wd, hora, minuto, nombre) en orden
    # cronologico de la semana.
    INICIOS = [
        (0, 10, 30, "Grupo A Lunes"),
        (1, 10, 30, "Grupo A Martes"),
        (2, 10, 30, "Grupo A Miércoles"),
        (3, 14, 0, "Grupo C Jueves"),
        (3, 21, 0, "Grupo B Jueves"),
        (4, 14, 0, "Grupo C Viernes"),
        (4, 21, 0, "Grupo B Viernes"),
        (5, 20, 40, "Final Sábado"),
    ]
    DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves",
               "Viernes", "Sábado", "Domingo"]

    wd_hoy = ahora.weekday()
    h_hoy = ahora.hour
    m_hoy = ahora.minute

    # Buscar el proximo inicio que aun no ha llegado esta semana
    for wd, h, mi, nombre in INICIOS:
        # Comparar (wd, h, mi) vs (wd_hoy, h_hoy, m_hoy)
        if (wd, h, mi) > (wd_hoy, h_hoy, m_hoy):
            dias_falta = wd - wd_hoy
            dia_inicio = ahora + timedelta(days=dias_falta)
            etiqueta_dia = ("Hoy" if dias_falta == 0
                            else "Mañana" if dias_falta == 1
                            else f"{DIAS_ES[wd]} {dia_inicio.strftime('%d/%m')}")
            return nombre, f"{h:02d}:{mi:02d}", etiqueta_dia

    # No hay mas inicios esta semana -> el proximo es el lunes que viene
    dias_falta = (7 - wd_hoy) + 0
    dia_inicio = ahora + timedelta(days=dias_falta)
    etiqueta_dia = f"Lunes {dia_inicio.strftime('%d/%m')}"
    return "Grupo A Lunes", "10:00", etiqueta_dia


def estado_jornada_sidebar():
    """Estado de la jornada para mostrar en el sidebar.

    A diferencia de detectar_jornada_de_hoy(), distingue tres casos:
      - ACTIVA: la jornada que toca por hora YA tiene datos cargados.
      - PENDIENTE: estamos en horario de jornada pero la pestana del Sheet
        aun no tiene jugadores cargados (suele pasar al principio del
        horario, antes de que el Sheet recoja los datos del partido).
      - SIN_JORNADA: estamos fuera del horario de cualquier jornada.

    Devuelve un dict con:
      estado: "ACTIVA" | "PENDIENTE" | "SIN_JORNADA"
      jornada: nombre de la jornada (None si SIN_JORNADA)
      proxima_nombre, proxima_hora, proxima_dia: solo si SIN_JORNADA
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        ahora = datetime.now()
    wd = ahora.weekday()
    h = ahora.hour

    DIAS_A = {0: "Grupo A Lunes", 1: "Grupo A Martes",
              2: "Grupo A Miércoles"}
    DIAS_C = {3: "Grupo C Jueves", 4: "Grupo C Viernes"}
    DIAS_B = {3: "Grupo B Jueves", 4: "Grupo B Viernes"}

    # Aplicar la regla horaria SIN comprobar datos (al contrario que
    # detectar_jornada_de_hoy, que devuelve None si la pestana esta vacia).
    jornada_horaria = None
    minuto = ahora.minute
    mnow = h * 60 + minuto
    if mnow <= 3 * 60:
        if wd == 4:
            jornada_horaria = DIAS_B[3]
        elif wd == 5:
            jornada_horaria = DIAS_B[4]
        elif wd == 6:
            jornada_horaria = "Final Sábado"
    else:
        if wd in DIAS_A:
            if 10 * 60 + 30 <= mnow <= 16 * 60:
                jornada_horaria = DIAS_A[wd]
        elif wd in DIAS_C:
            if 14 * 60 <= mnow <= 19 * 60:
                jornada_horaria = DIAS_C[wd]
            elif 21 * 60 <= mnow:
                jornada_horaria = DIAS_B[wd]
        elif wd == 5:
            if mnow >= 20 * 60 + 40:
                jornada_horaria = "Final Sábado"

    if jornada_horaria is None:
        # Fuera de horario: SIN_JORNADA + proxima
        nom, hora, dia = proxima_jornada()
        return {
            "estado": "SIN_JORNADA",
            "jornada": None,
            "proxima_nombre": nom,
            "proxima_hora": hora,
            "proxima_dia": dia,
        }

    # En horario: comprobar si la pestana tiene datos
    try:
        jug = cargar_jugadores_desde(jornada_horaria)
    except Exception:
        jug = {}
    if jug:
        return {"estado": "ACTIVA", "jornada": jornada_horaria}
    else:
        return {"estado": "PENDIENTE", "jornada": jornada_horaria}


def cargar_forma_reciente():
    """Construye la fuente de datos 'Forma reciente'.

    Combina, para cada jugador, sus estadisticas de DOS fuentes:
      - La jornada de hoy (lo mas reciente).
      - El Resumen Semanal (el acumulado de toda la semana).

    El peso de 'hoy' es DINAMICO segun cuantos partidos lleve hoy ese
    jugador: con pocos partidos pesa poco (un solo partido no debe
    distorsionar la valoracion), y con la jornada avanzada lo reciente
    domina. Pesos: 1 partido -> 30%, 2 -> 45%, 3 -> 60%, 4 -> 65%,
    5 -> 70%, y a partir de ahi sube suave hasta un tope del 85%.

    Para cada estadistica numerica:
        valor_final = peso_hoy * valor_hoy + (1 - peso_hoy) * valor_resumen

    Si un jugador no aparece en la jornada de hoy (aun no ha jugado),
    se usan directamente sus datos del Resumen Semanal.

    Devuelve un dict {nombre_lower: {...stats...}} con la misma forma que
    cargar_jugadores_desde, para que el resto de la app no note diferencia.
    """
    # Estadisticas numericas que se combinan
    CAMPOS = ["PR", "lam_180", "lam_legs", "promedio_dardos",
              "checkouts", "pct_victorias", "volatilidad"]

    # Peso de "hoy" segun cuantos partidos lleve hoy el jugador.
    # Tabla a medida: con pocos partidos pesa poco (un solo partido no debe
    # distorsionar la valoracion); con la jornada avanzada, lo reciente
    # domina. A partir de 5 partidos sigue subiendo suave, con tope del 85%.
    _PESOS_HOY = {0: 0.0, 1: 0.30, 2: 0.45, 3: 0.60, 4: 0.65, 5: 0.70}

    def _peso_hoy(n):
        if n in _PESOS_HOY:
            return _PESOS_HOY[n]
        if n > 5:
            return min(0.70 + 0.03 * (n - 5), 0.85)
        return 0.0

    resumen = cargar_jugadores_desde("Resumen Semanal")
    if not resumen:
        # Sin Resumen no hay base: devolvemos lo que haya de hoy, o vacio.
        jornada_hoy = detectar_jornada_de_hoy()
        return cargar_jugadores_desde(jornada_hoy) if jornada_hoy else {}

    jornada_hoy = detectar_jornada_de_hoy()
    if not jornada_hoy:
        # No hay jornada con datos: la forma reciente es solo el Resumen.
        return resumen
    datos_hoy = cargar_jugadores_desde(jornada_hoy)

    combinado = {}
    for nombre_lower, jug_resumen in resumen.items():
        jug_hoy = datos_hoy.get(nombre_lower)

        if not jug_hoy:
            # El jugador no ha jugado hoy: usamos su acumulado tal cual.
            combinado[nombre_lower] = dict(jug_resumen)
            continue

        # Peso dinamico segun partidos jugados hoy
        n_hoy = jug_hoy.get("n_partidos", 0)
        peso_hoy = _peso_hoy(n_hoy)

        nuevo = dict(jug_resumen)  # parte de la base del Resumen
        for campo in CAMPOS:
            v_hoy = jug_hoy.get(campo, 0.0)
            v_res = jug_resumen.get(campo, 0.0)
            # Si el valor de hoy es 0 (dato ausente), no lo mezclamos
            if v_hoy == 0.0:
                nuevo[campo] = v_res
            else:
                nuevo[campo] = peso_hoy * v_hoy + (1.0 - peso_hoy) * v_res
        nuevo["nombre_original"] = jug_resumen.get(
            "nombre_original", nombre_lower.title())
        combinado[nombre_lower] = nuevo

    return combinado


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


def _limpiar_nombre_jugador(nombre):
    """Limpia el nombre de un jugador devuelto por la API.

    La API puede añadir información extra al nombre: códigos de país entre
    paréntesis "(ENG)", rankings numéricos "1. ", siglas entre corchetes,
    espacios sobrantes, etc. Esta función deja únicamente el nombre limpio.

    Ejemplos:
        "George Killington (ENG)" -> "George Killington"
        "1. Richie Howson"        -> "Richie Howson"
        "  Arne  Spee  "          -> "Arne Spee"
    """
    if not nombre:
        return ""
    texto = str(nombre)
    # Quitar lo que vaya entre paréntesis o corchetes (país, ranking, etc.)
    texto = re.sub(r"\([^)]*\)", "", texto)
    texto = re.sub(r"\[[^\]]*\]", "", texto)
    # Quitar un prefijo de ranking tipo "12. " o "3) " al principio
    texto = re.sub(r"^\s*\d+\s*[.)\-]\s*", "", texto)
    # Colapsar espacios múltiples y recortar
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


@st.cache_data(ttl=60)
def obtener_proximos_partidos_api(limite=3):
    """Devuelve los próximos partidos que aún NO han empezado.

    CRITERIO DE "NO EMPEZADO" (importante):
    No nos fiamos del campo 'status' de la API porque resulta poco fiable.
    En su lugar aplicamos la regla observada en la pestaña Live: un partido
    NO ha empezado cuando en sus datos SOLO aparecen los nombres de los dos
    jugadores y NINGÚN dato de juego. Si el fixture tiene marcador, legs,
    estadísticas, ganador, o cualquier otro dato de actividad, significa que
    el partido ya ha comenzado (o terminado) y se descarta.

    Solo interesan los nombres de los dos jugadores, para autocompletar el
    selector de Value Bets.

    DEVUELVE UN DICT con dos claves:
        - "partidos": lista de dicts {id, j1, j2, fecha, etiqueta}
        - "diagnostico": string explicando qué pasó si la lista sale vacía.
    """
    base_url = "https://api-igamedc.igamemedia.com/api/mss-web"

    # Campos del fixture que, si tienen un valor "real", indican que el
    # partido YA tiene actividad (ha empezado o terminado).
    CAMPOS_DE_JUEGO = (
        "scorePlayerHome", "scorePlayerAway", "scoreHome", "scoreAway",
        "legsPlayerHome", "legsPlayerAway", "legsHome", "legsAway",
        "winner", "winnerId", "result", "playersStatistics", "statistics",
        "average", "averageHome", "averageAway",
        "turns180", "turns180Home", "turns180Away",
        "checkoutPercentage", "currentLeg", "currentSet", "sets",
    )

    def _tiene_dato_de_juego(fixture):
        """True si el fixture contiene algún dato que indique que el partido
        ya tiene actividad. Un valor cuenta como "real" si no está vacío,
        no es None, y no es un cero/cero-string (un 0-0 inicial no cuenta
        como partido empezado)."""
        for campo in CAMPOS_DE_JUEGO:
            if campo not in fixture:
                continue
            val = fixture.get(campo)
            if val is None:
                continue
            # Listas/dicts no vacíos = hay estadísticas → partido con actividad
            if isinstance(val, (list, dict)):
                if len(val) > 0:
                    return True
                continue
            # Valores escalares: vacío o cero no cuentan como actividad
            texto = str(val).strip().lower()
            if texto in ("", "none", "null", "-", "0", "0.0", "0,0",
                         "0-0", "00:00"):
                continue
            return True
        return False

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
    vistos = set()        # evita duplicados si un fixture aparece en varios grupos
    total_fixtures = 0    # cuántos fixtures vimos en total
    ya_empezados = 0      # cuántos descartamos por tener datos de juego

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
                j1 = _limpiar_nombre_jugador(fixture.get("playerHome", ""))
                j2 = _limpiar_nombre_jugador(fixture.get("playerAway", ""))
                # Sin los dos nombres no es un enfrentamiento utilizable
                if not j1 or not j2:
                    continue
                # CRITERIO CLAVE: si tiene datos de juego, ya empezó → descartar
                if _tiene_dato_de_juego(fixture):
                    ya_empezados += 1
                    continue
                fixture_id = (fixture.get("gameId") or fixture.get("Id")
                              or fixture.get("id") or f"{j1}-{j2}")
                if fixture_id in vistos:
                    continue
                vistos.add(fixture_id)
                # La fecha se usa SOLO para ordenar cronológicamente; no se
                # muestra al usuario. Probamos varios nombres de campo.
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

    # Ordenar segun el ORDEN DE JUEGO REAL del CSV de la jornada activa.
    # La API devuelve los fixtures desordenados y a menudo sin fecha fiable,
    # asi que cruzamos con el CSV (que respeta el orden real de juego).
    orden_csv = cargar_orden_partidos_jornada_activa()
    if orden_csv:
        proximos.sort(key=lambda p: _indice_orden_partido(
            p["j1"], p["j2"], orden_csv))
    else:
        # Fallback: si no hay CSV, ordenar por fecha como antes.
        proximos.sort(key=lambda p: p["_sort"])

    # Construir resultado: etiqueta SOLO con nombres "J1 vs J2"
    resultado = []
    for p in proximos[:limite]:
        resultado.append({
            "id": p["id"],
            "j1": p["j1"],
            "j2": p["j2"],
            "fecha": p["fecha"],
            "etiqueta": f"{p['j1']} vs {p['j2']}",
        })

    # Diagnóstico para el caso de lista vacía
    if resultado:
        diag = ""
    elif total_fixtures == 0:
        diag = "La API de MODUS respondió pero no devolvió ningún partido."
    elif ya_empezados == total_fixtures:
        diag = ("Todos los partidos de esta semana ya han empezado o "
                "terminado. Aún no hay próximos enfrentamientos publicados.")
    else:
        diag = ("No se encontraron próximos partidos pendientes. "
                "Es posible que los enfrentamientos aún no estén publicados.")

    return {"partidos": resultado, "diagnostico": diag}


def get_jornada_actual():
    """Devuelve (nombre, url, es_activa) de la jornada activa AHORA.

    Delega en detectar_jornada_de_hoy() (que ya usa zona horaria Madrid
    y las reglas horarias actualizadas) en lugar de duplicar la logica.
    Es_activa es True solo si la jornada esta activa por hora Y la
    pestana del Sheet tiene datos cargados.
    """
    jornada = detectar_jornada_de_hoy()
    if jornada is None:
        return None, None, False
    url = URLS.get(jornada, "")
    return jornada, url, True


def get_proxima_jornada():
    """Devuelve (nombre, url) de la proxima jornada que va a empezar.

    Delega en proxima_jornada() (que usa zona horaria Madrid y las reglas
    horarias actualizadas).
    """
    try:
        nombre, _hora, _dia = proxima_jornada()
    except Exception:
        nombre = "Grupo A Lunes"
    url = URLS.get(nombre, "")
    return nombre, url


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL W/L Y RACHA SEMANAL
# ─────────────────────────────────────────────────────────────────────────────

# Orden cronologico de las jornadas durante la semana
JORNADAS_SEMANA_ORDEN = [
    "Grupo A Lunes",
    "Grupo A Martes",
    "Grupo A Miércoles",
    "Grupo C Jueves",
    "Grupo B Jueves",
    "Grupo C Viernes",
    "Grupo B Viernes",
    "Final Sábado",
]

FILA_INICIO_PARTIDOS = 7   # fila 1-indexed donde empiezan los partidos


def _normalizar_nombre_hist(n):
    """Quita tildes, pasa a minusculas y colapsa espacios."""
    import unicodedata
    n = unicodedata.normalize("NFD", str(n))
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return " ".join(n.lower().split())


@st.cache_data(ttl=120, show_spinner=False)
def cargar_historial_semana(nombre_jugador: str) -> list:
    """Devuelve la lista de resultados del jugador en la semana actual,
    en orden cronologico, como booleans: True = victoria, False = derrota.

    Recorre TODAS las jornadas (A, B, C y Final) y extrae los partidos
    donde aparece el jugador. Para cada partido de 2 filas, el ganador
    es el que tiene 4 legs. Si ambas filas estan vacias, el partido no
    se ha jugado y se ignora.

    Devuelve una lista con hasta 15 elementos (max partidos por semana).
    Lista vacia si no se encuentra el jugador en ninguna jornada.
    """
    nombre_norm = _normalizar_nombre_hist(nombre_jugador)
    resultados = []

    for jornada in JORNADAS_SEMANA_ORDEN:
        lineas = _descargar_csv_jornada(jornada)
        if not lineas:
            continue

        idx_inicio = FILA_INICIO_PARTIDOS - 1  # 0-indexed
        filas_partidos = lineas[idx_inicio:]

        # Recorrer en pares: fila_j1 + fila_j2 = un partido
        i = 0
        while i + 1 < len(filas_partidos):
            fila1 = filas_partidos[i]
            fila2 = filas_partidos[i + 1]
            i += 2

            nombre1 = fila1[0].strip() if len(fila1) > 0 else ""
            nombre2 = fila2[0].strip() if len(fila2) > 0 else ""
            if not nombre1 or not nombre2:
                break  # no hay mas partidos

            # ¿Aparece nuestro jugador en alguna de las dos filas?
            norm1 = _normalizar_nombre_hist(nombre1)
            norm2 = _normalizar_nombre_hist(nombre2)
            es_j1 = (nombre_norm in norm1 or norm1 in nombre_norm)
            es_j2 = (nombre_norm in norm2 or norm2 in nombre_norm)
            if not es_j1 and not es_j2:
                continue  # este partido no le involucra

            # Legs de cada jugador (columna B, indice 1)
            def _legs(fila):
                try:
                    v = str(fila[1]).strip().replace(",", ".")
                    return int(float(v)) if v else 0
                except Exception:
                    return 0

            legs1 = _legs(fila1)
            legs2 = _legs(fila2)

            # Si ninguno tiene legs, el partido no se ha jugado todavia
            if legs1 == 0 and legs2 == 0:
                # Comprobar si hay algun dato en otras columnas
                datos1 = any(
                    str(fila1[c]).strip() not in ("", "0", "0,00%", "0%")
                    for c in range(1, min(5, len(fila1)))
                )
                datos2 = any(
                    str(fila2[c]).strip() not in ("", "0", "0,00%", "0%")
                    for c in range(1, min(5, len(fila2)))
                )
                if not datos1 and not datos2:
                    continue  # partido no jugado aun

            # Determinar ganador (quien llego a 4)
            if legs1 >= 4:
                gano_j1 = True
            elif legs2 >= 4:
                gano_j1 = False
            else:
                continue  # partido en curso o datos incompletos

            victoria = (es_j1 and gano_j1) or (es_j2 and not gano_j1)
            resultados.append(victoria)

    return resultados


def calcular_racha(resultados: list) -> tuple:
    """A partir de la lista de resultados (True=W, False=L) calcula
    la racha actual del jugador.

    Devuelve (longitud, tipo) donde tipo es 'W', 'L' o None (sin datos).
    Ejemplo: (3, 'W') significa que lleva 3 victorias seguidas.
    """
    if not resultados:
        return 0, None
    ultimo = resultados[-1]
    racha = 1
    for r in reversed(resultados[:-1]):
        if r == ultimo:
            racha += 1
        else:
            break
    return racha, ("W" if ultimo else "L")


@st.cache_data(ttl=60, show_spinner=False)
def cargar_orden_partidos_jornada_activa() -> list:
    """Devuelve el orden de juego de los partidos de la jornada activa AHORA,
    leido del CSV (que respeta el orden real de juego).

    Cada elemento es una tupla de nombres normalizados de los 2 jugadores:
        [(norm_j1, norm_j2), (norm_j1, norm_j2), ...]

    El indice en la lista = orden de juego. Sirve para ordenar los partidos
    que la API devuelve desordenados.

    Lista vacia si no hay jornada activa o el CSV no se puede leer.
    """
    jornada = detectar_jornada_de_hoy()
    if not jornada:
        return []

    lineas = _descargar_csv_jornada(jornada)
    if not lineas:
        return []
    idx_inicio = FILA_INICIO_PARTIDOS - 1
    filas = lineas[idx_inicio:]

    orden = []
    i = 0
    while i + 1 < len(filas):
        fila1 = filas[i]
        fila2 = filas[i + 1]
        i += 2
        n1 = fila1[0].strip() if len(fila1) > 0 else ""
        n2 = fila2[0].strip() if len(fila2) > 0 else ""
        if not n1 or not n2:
            continue  # hueco (nombres no cargados aun), saltar
        orden.append((_normalizar_nombre_hist(n1),
                      _normalizar_nombre_hist(n2)))
    return orden


def _indice_orden_partido(j1, j2, orden_csv):
    """Dado un partido (j1, j2) y la lista de orden del CSV, devuelve su
    posicion de juego. Si no se encuentra, devuelve un numero grande para
    que quede al final. Compara por nombres normalizados en cualquier orden.
    """
    nj1 = _normalizar_nombre_hist(j1)
    nj2 = _normalizar_nombre_hist(j2)

    def _coincide(a, b):
        return (a in b or b in a) if a and b else False

    for idx, (c1, c2) in enumerate(orden_csv):
        # El partido puede venir como (j1,j2) o (j2,j1)
        if ((_coincide(nj1, c1) and _coincide(nj2, c2)) or
                (_coincide(nj1, c2) and _coincide(nj2, c1))):
            return idx
    return 9999


@st.cache_data(ttl=60, show_spinner=False)
def obtener_proximos_partidos_csv(limite=3) -> dict:
    """Devuelve los proximos partidos NO empezados leyendo el CSV de la
    jornada que toca (activa o, si no hay activa, la proxima), en ORDEN
    DE JUEGO REAL.

    A diferencia de obtener_proximos_partidos_api(), NO usa la API de MODUS
    (que devuelve fixtures de jornadas viejas ya finalizadas). Se basa solo
    en el CSV de la jornada correcta.

    Reglas:
      - Jornada activa con datos -> sus partidos no empezados.
      - Sin jornada activa pero proxima con datos -> los de la proxima.
      - Ningun CSV con datos -> lista vacia (no se muestra nada).

    Un partido esta "no empezado" si ninguna de sus 2 filas tiene datos
    de juego en las columnas B-E (legs, 180s, promedio, checkout).

    DEVUELVE dict:
      {"partidos": [{id, j1, j2, etiqueta}], "diagnostico": str}
    """
    # 1) Elegir la jornada: activa primero, luego proxima
    jornada = detectar_jornada_de_hoy()
    origen = "activa"
    if not jornada:
        try:
            nombre_prox, _h, _d = proxima_jornada()
        except Exception:
            nombre_prox = None
        jornada = nombre_prox
        origen = "proxima"

    if not jornada:
        return {"partidos": [],
                "diagnostico": "No hay jornada activa ni proxima identificable."}

    # 2) Leer el CSV (descarga centralizada y cacheada)
    lineas = _descargar_csv_jornada(jornada)
    if not lineas:
        return {"partidos": [],
                "diagnostico": f"No se pudo leer el CSV de {jornada}."}
    idx_inicio = FILA_INICIO_PARTIDOS - 1
    filas = lineas[idx_inicio:]

    def _celda_dato(v):
        t = str(v).strip().lower()
        return t not in ("", "none", "null", "-", "0", "0.0", "0,0",
                          "0-0", "0,00%", "0%", "00:00")

    def _legs(v):
        try:
            return int(float(str(v).strip().replace(",", ".")))
        except Exception:
            return 0

    proximos = []
    i = 0
    while i + 1 < len(filas):
        fila1 = filas[i]
        fila2 = filas[i + 1]
        i += 2
        j1 = fila1[0].strip() if len(fila1) > 0 else ""
        j2 = fila2[0].strip() if len(fila2) > 0 else ""
        if not j1 or not j2:
            continue  # hueco

        celdas1 = fila1[1:5] if len(fila1) >= 5 else fila1[1:]
        celdas2 = fila2[1:5] if len(fila2) >= 5 else fila2[1:]
        legs1 = _legs(fila1[1] if len(fila1) > 1 else "")
        legs2 = _legs(fila2[1] if len(fila2) > 1 else "")

        terminado = (legs1 >= 4 or legs2 >= 4)
        algun_dato = (any(_celda_dato(c) for c in celdas1) or
                      any(_celda_dato(c) for c in celdas2))

        if terminado or algun_dato:
            continue  # ya empezado o terminado -> no es "proximo"

        proximos.append({
            "id": f"{j1}-{j2}",
            "j1": j1,
            "j2": j2,
            "etiqueta": f"{j1} vs {j2}",
        })

    if not proximos:
        return {"partidos": [],
                "diagnostico": f"La jornada {jornada} aun no tiene partidos "
                               f"pendientes con datos."}

    return {"partidos": proximos[:limite], "diagnostico": ""}


@st.cache_data(ttl=120, show_spinner=False)
def cargar_historial_jornada(nombre_jugador: str, jornada: str) -> list:
    """Como cargar_historial_semana pero SOLO de una jornada concreta.

    Devuelve lista de booleans (True=victoria, False=derrota) de los
    partidos del jugador en esa jornada, en orden de juego. Lista vacia
    si el jugador no aparece o la jornada no tiene datos.
    """
    nombre_norm = _normalizar_nombre_hist(nombre_jugador)
    resultados = []

    lineas = _descargar_csv_jornada(jornada)
    if not lineas:
        return []
    idx_inicio = FILA_INICIO_PARTIDOS - 1
    filas = lineas[idx_inicio:]

    i = 0
    while i + 1 < len(filas):
        fila1 = filas[i]
        fila2 = filas[i + 1]
        i += 2
        n1 = fila1[0].strip() if len(fila1) > 0 else ""
        n2 = fila2[0].strip() if len(fila2) > 0 else ""
        if not n1 or not n2:
            continue
        norm1 = _normalizar_nombre_hist(n1)
        norm2 = _normalizar_nombre_hist(n2)
        es_j1 = (nombre_norm in norm1 or norm1 in nombre_norm)
        es_j2 = (nombre_norm in norm2 or norm2 in nombre_norm)
        if not es_j1 and not es_j2:
            continue

        def _legs(fila):
            try:
                v = str(fila[1]).strip().replace(",", ".")
                return int(float(v)) if v else 0
            except Exception:
                return 0

        legs1 = _legs(fila1)
        legs2 = _legs(fila2)
        if legs1 >= 4:
            gano_j1 = True
        elif legs2 >= 4:
            gano_j1 = False
        else:
            continue  # en curso / no jugado

        victoria = (es_j1 and gano_j1) or (es_j2 and not gano_j1)
        resultados.append(victoria)

    return resultados


@st.cache_data(ttl=60, show_spinner=False)
def _descargar_csv_jornada(jornada: str) -> list:
    """Descarga el CSV de una jornada UNA SOLA VEZ (cacheado 60s) y devuelve
    las filas parseadas como lista de listas.

    Todas las funciones de historial/racha/orden/proximos usan esta funcion
    para evitar descargar el mismo CSV varias veces (antes, cada jugador
    descargaba su propia copia: 6 jugadores x 8 jornadas = 48 peticiones;
    ahora maximo 8, una por jornada).
    """
    import io
    import csv as csv_mod
    import urllib.request

    url = URLS.get(jornada)
    if not url:
        return []
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            texto = r.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    return list(csv_mod.reader(io.StringIO(texto)))
