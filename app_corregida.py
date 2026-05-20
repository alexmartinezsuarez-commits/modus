import streamlit as st
import pandas as pd
import numpy as np
import requests
from scipy.stats import poisson
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
import time

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

# Paleta de colores para asignar a cada jugador en la tabla de detalles.
# Colores vibrantes pero suaves, todos con suficiente contraste con texto oscuro.
# La asignación es secuencial por orden de aparición y se guarda en
# st.session_state para que un jugador conserve su color durante la sesión.
PALETA_JUGADORES = [
    "#fbbf24",  # ámbar
    "#fb923c",  # naranja
    "#f87171",  # rojo coral
    "#e879f9",  # fucsia
    "#a78bfa",  # violeta
    "#818cf8",  # índigo
    "#60a5fa",  # azul
    "#22d3ee",  # cian
    "#2dd4bf",  # turquesa
    "#34d399",  # esmeralda
    "#a3e635",  # lima
    "#facc15",  # amarillo
    "#fb7185",  # rosa
    "#c084fc",  # púrpura
    "#38bdf8",  # cielo
    "#4ade80",  # verde
    "#f472b6",  # rosa fuerte
    "#fcd34d",  # mostaza
]


def obtener_color_jugador(nombre):
    """Devuelve un color de fondo único para un jugador.
    
    Estrategia: asignación secuencial sin colisiones. La primera vez que se
    ve un jugador se le asigna el siguiente color libre de la paleta y se
    guarda en st.session_state['colores_jugadores']. En llamadas posteriores
    devuelve el color ya asignado.
    
    Los nombres se normalizan (lowercase + strip) para que pequeñas variaciones
    como espacios extra o capitalización no rompan la asignación.
    
    Si se agota la paleta (más de 18 jugadores únicos), cae a un esquema cíclico.
    Devuelve None para nombres vacíos / inválidos.
    """
    if not nombre:
        return None
    nombre_str = str(nombre).strip()
    if not nombre_str or nombre_str.lower() in ('nan', ''):
        return None
    nombre_norm = nombre_str.lower()
    
    # Inicializar el mapa en session_state si no existe
    if 'colores_jugadores' not in st.session_state:
        st.session_state['colores_jugadores'] = {}
    
    mapa = st.session_state['colores_jugadores']
    
    if nombre_norm in mapa:
        return mapa[nombre_norm]
    
    # Asignar siguiente color libre
    idx = len(mapa) % len(PALETA_JUGADORES)
    color = PALETA_JUGADORES[idx]
    mapa[nombre_norm] = color
    return color


def pintar_partidos(fila):
    """Aplica dos capas de estilo a la tabla de detalles de partidos:
    
    - Cada par de filas (un partido) alterna fondo gris suave/transparente
      para hacer visualmente bloque.
    - La PRIMERA celda (nombre del jugador) se pinta con el color único que
      le corresponde por nombre, en negrita y con texto oscuro para contraste.
    
    Si la primera celda no tiene un nombre válido, se pinta como el resto.
    """
    nombre_jugador = str(fila.iloc[0]).strip() if len(fila) > 0 else ""
    color_jugador = obtener_color_jugador(nombre_jugador)
    
    # Fondo alternado por partido (cada par de filas)
    es_par = (fila.name // 2) % 2 == 0
    fondo_fila = 'rgba(150, 150, 150, 0.15)' if es_par else 'transparent'
    
    estilos = []
    for i in range(len(fila)):
        if i == 0 and color_jugador:
            # Celda del nombre: color del jugador con texto oscuro y negrita
            estilos.append(
                f'background-color: {color_jugador}; '
                f'color: #1a1a1a; font-weight: 700;'
            )
        else:
            estilos.append(f'background-color: {fondo_fila};')
    return estilos

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
    """Calcula tendencia con reglas específicas: 5% general, 3% para Puntuación Global.
    
    Soporta valores con coma decimal (formato europeo: 5,6 → 5.6) y porcentaje.
    Excluye Número de Victorias/Derrotas (contadores absolutos), pero SÍ aplica
    a Porcentaje Victoria (valor relativo).
    """
    try:
        # Limpiar formato europeo (coma decimal) y símbolo de porcentaje
        val_act = float(str(valor_actual).replace('%', '').replace(',', '.').strip())
        val_sem = float(str(valor_semanal).replace('%', '').replace(',', '.').strip())
    except:
        return "", valor_actual, ""
    
    # Excluir solo los conteos absolutos de Victorias/Derrotas
    # (Porcentaje Victoria sí debe mostrar tendencia)
    etiqueta_lower = etiqueta.lower()
    es_conteo_vic_der = (
        ("victoria" in etiqueta_lower or "derrota" in etiqueta_lower)
        and "porcentaje" not in etiqueta_lower
        and "%" not in etiqueta_lower
    )
    if es_conteo_vic_der:
        return "", valor_actual, ""
    
    # Calcular porcentaje de cambio
    if val_sem == 0:
        porcentaje_cambio = 0
    else:
        porcentaje_cambio = ((val_act - val_sem) / abs(val_sem)) * 100
    
    # Umbral diferente para Puntuación Global
    umbral = 3 if "puntiación" in etiqueta_lower else 5
    
    # Formato del valor de referencia con coma decimal (estilo español)
    comparativa = f"({val_sem:.1f})".replace(".", ",")
    
    # Mostrar indicador solo si supera el umbral
    if abs(porcentaje_cambio) >= umbral:
        if porcentaje_cambio > 0:
            indicador = "🟢 ↑"
        else:
            indicador = "🔴 ↓"
        return indicador, valor_actual, comparativa
    else:
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


@st.cache_data(ttl=30, show_spinner=False)
def obtener_ultimos_partidos(jugador_nombre, n=3):
    """Devuelve los últimos n partidos jugados por un jugador a lo largo de la
    semana, en orden cronológico INVERSO (el más reciente primero).
    
    Recorre las pestañas en orden: Final Sábado → Viernes → Jueves → Mié → Mar → Lun
    y dentro de cada pestaña recorre los partidos también en orden inverso.
    
    Filtra partidos no terminados (ningún jugador llegó a 4 legs) y filas con
    datos corruptos / vacíos.
    
    Devuelve lista de dicts con:
        - dia:       nombre de la jornada (ej. "Grupo A Lunes")
        - rival:     nombre del oponente
        - marcador:  "X-Y" desde la perspectiva del jugador
        - ganador:   True si el jugador ganó
        - stats:     dict {nombre_columna: valor} con todas las stats del
                     jugador en ese partido (180s, promedio, checkout %, etc.)
    """
    dias_semana = [
        "Final Sábado",
        "Grupo B Viernes", "Grupo C Viernes",
        "Grupo B Jueves",  "Grupo C Jueves",
        "Grupo A Miércoles", "Grupo A Martes", "Grupo A Lunes",
    ]
    jug_lower = str(jugador_nombre).lower().strip().replace("_", " ")
    if not jug_lower:
        return []
    
    partidos = []
    
    def _parse_legs(val):
        try:
            return int(float(str(val).replace(',', '.').strip()))
        except:
            return -1
    
    for dia in dias_semana:
        if len(partidos) >= n:
            break
        try:
            df_partidos, _ = cargar_todo(URLS[dia], dia, CORTES[dia])
        except Exception:
            continue
        if df_partidos is None or len(df_partidos) < 2:
            continue
        
        # Iterar pares de filas (cada par = 1 partido) en orden INVERSO
        i = (len(df_partidos) - 1) // 2 * 2  # último índice par válido
        while i >= 0:
            if len(partidos) >= n:
                break
            if i + 1 >= len(df_partidos):
                i -= 2
                continue
            
            fila1 = df_partidos.iloc[i]
            fila2 = df_partidos.iloc[i + 1]
            nombre1 = str(fila1.iloc[0]).strip() if len(fila1) > 0 else ""
            nombre2 = str(fila2.iloc[0]).strip() if len(fila2) > 0 else ""
            
            if (not nombre1 or not nombre2 or
                    nombre1.lower() in ('nan', '') or
                    nombre2.lower() in ('nan', '')):
                i -= 2
                continue
            
            n1_lower = nombre1.lower().replace("_", " ")
            n2_lower = nombre2.lower().replace("_", " ")
            
            # Match difuso del nombre (igual que en H2H)
            if jug_lower in n1_lower or n1_lower in jug_lower:
                fila_jug, fila_riv = fila1, fila2
                rival = nombre2
            elif jug_lower in n2_lower or n2_lower in jug_lower:
                fila_jug, fila_riv = fila2, fila1
                rival = nombre1
            else:
                i -= 2
                continue
            
            # Parsear legs y filtrar partidos no terminados
            legs_jug = _parse_legs(fila_jug.iloc[1]) if len(fila_jug) > 1 else -1
            legs_riv = _parse_legs(fila_riv.iloc[1]) if len(fila_riv) > 1 else -1
            if legs_jug < 0 or legs_riv < 0:
                i -= 2
                continue
            # Al menos uno debe haber llegado a 4 legs para que el partido cuente
            if legs_jug < 4 and legs_riv < 4:
                i -= 2
                continue
            
            # Construir dict de stats del jugador en ese partido
            stats = {}
            for col in df_partidos.columns:
                val = fila_jug[col]
                if pd.notna(val) and str(val).strip() not in ('', 'nan'):
                    stats[str(col)] = val
            
            partidos.append({
                "dia": dia,
                "rival": rival,
                "marcador": f"{legs_jug}-{legs_riv}",
                "ganador": legs_jug > legs_riv,
                "stats": stats,
            })
            i -= 2
    
    return partidos[:n]

def safe_float(val, default=0.0):
    try:
        v = float(str(val).replace(',', '.').strip())
        if not np.isfinite(v):
            return default
        return v
    except:
        return default


def color_volatilidad(valor):
    """Devuelve la paleta de colores (borde, valor, fondo, texto_riesgo, etiqueta_riesgo)
    según el índice de volatilidad, midiendo la irregularidad/riesgo del rendimiento:

        - Verde   si valor < 8    → RIESGO BAJO (rendimiento estable)
        - Amarillo si 8 ≤ v ≤ 12  → RIESGO MEDIO (rendimiento algo irregular)
        - Rojo    si valor > 12   → RIESGO ALTO (rendimiento muy irregular)

    Umbrales alineados con el formato condicional de la hoja de cálculo.

    Acepta tanto strings con coma decimal española ("18,02") como números.
    Si el valor no es parseable, es NaN o es 0 (jugador sin datos), devuelve
    una paleta neutra en gris sin etiqueta de riesgo.
    """
    paleta_neutra = {
        "borde": "#9ca3af", "valor": "#6b7280",
        "bg": "rgba(156, 163, 175, 0.08)",
        "riesgo_texto": "#6b7280", "riesgo_bg": "rgba(156, 163, 175, 0.15)",
        "riesgo_label": ""
    }
    try:
        v = float(str(valor).replace('%', '').replace(',', '.').strip())
    except:
        return paleta_neutra
    # NaN o jugador sin datos (valor 0 exacto): paleta neutra sin etiqueta
    if not np.isfinite(v) or v == 0:
        return paleta_neutra
    if v < 8:
        return {
            "borde": "#22c55e", "valor": "#16a34a",
            "bg": "rgba(34, 197, 94, 0.10)",
            "riesgo_texto": "#15803d", "riesgo_bg": "rgba(34, 197, 94, 0.18)",
            "riesgo_label": "RIESGO BAJO"
        }
    elif v <= 12:
        return {
            "borde": "#eab308", "valor": "#ca8a04",
            "bg": "rgba(234, 179, 8, 0.12)",
            "riesgo_texto": "#854d0e", "riesgo_bg": "rgba(234, 179, 8, 0.22)",
            "riesgo_label": "RIESGO MEDIO"
        }
    else:
        return {
            "borde": "#dc2626", "valor": "#dc2626",
            "bg": "rgba(220, 38, 38, 0.10)",
            "riesgo_texto": "#991b1b", "riesgo_bg": "rgba(220, 38, 38, 0.18)",
            "riesgo_label": "RIESGO ALTO"
        }

def sanitize_prob(p):
    if not np.isfinite(p) or p <= 0:
        return 0.0001
    if p >= 1:
        return 0.9999
    return max(0.0001, min(0.9999, p))

def prob_victoria(pr1, pr2, j1_saca_primero=True):
    if pr1 <= 0 and pr2 <= 0:
        return 0.5, 0.5
    finales = simular_match(pr1, pr2, j1_saca_primero)
    p1 = sum(p for (l1, _l2), p in finales.items() if l1 >= 4)
    return sanitize_prob(p1), sanitize_prob(1.0 - p1)

def prob_180s(lam1, lam2, pr1=None, pr2=None, j1_saca_primero=True):
    """Mercados de 180s con Poisson. Si se pasan pr1, pr2 (PG de los jugadores),
    ajusta lambda multiplicando por (E[legs del partido] / LEGS_PROMEDIO_REFERENCIA)
    para que partidos más reñidos generen proporcionalmente más 180s.

    Si solo se pasan lam1, lam2, no aplica ajuste (lambda = T directamente).
    """
    factor = 1.0
    if pr1 is not None and pr2 is not None and pr1 > 0 and pr2 > 0:
        finales = simular_match(pr1, pr2, j1_saca_primero)
        E_legs = legs_esperados_desde_finales(finales)
        if E_legs > 0:
            factor = E_legs / LEGS_PROMEDIO_REFERENCIA

    lam1_aj = lam1 * factor
    lam2_aj = lam2 * factor
    lam_total = lam1_aj + lam2_aj
    ambos_05 = sanitize_prob((1 - poisson.cdf(0, lam1_aj)) * (1 - poisson.cdf(0, lam2_aj)))
    return {
        "J1 +0.5": sanitize_prob(1 - poisson.cdf(0, lam1_aj)),
        "J1 +1.5": sanitize_prob(1 - poisson.cdf(1, lam1_aj)),
        "J2 +0.5": sanitize_prob(1 - poisson.cdf(0, lam2_aj)),
        "J2 +1.5": sanitize_prob(1 - poisson.cdf(1, lam2_aj)),
        "Ambos +0.5": ambos_05,
        "Ambos +1.5": sanitize_prob(1 - poisson.cdf(1, lam_total)),
        "Ambos +2.5": sanitize_prob(1 - poisson.cdf(2, lam_total)),
    }

def quien_hace_mas_180s(lam1, lam2, pr1=None, pr2=None, j1_saca_primero=True, k_max=15):
    """Match 180s (H2H) usando bivariada de Poisson independientes.
    Si se pasan pr1, pr2, ajusta lambdas con el factor de legs esperados.

    Suma sobre la matriz P(i, j) = P(N1=i) * P(N2=j) las celdas donde:
        - i > j  → J1 hace más 180s
        - i < j  → J2 hace más 180s
        - i == j → empate

    k_max=15 cubre cómodamente los rangos típicos (lam ≈ 1-3, P(>15) < 1e-8).
    """
    factor = 1.0
    if pr1 is not None and pr2 is not None and pr1 > 0 and pr2 > 0:
        finales = simular_match(pr1, pr2, j1_saca_primero)
        E_legs = legs_esperados_desde_finales(finales)
        if E_legs > 0:
            factor = E_legs / LEGS_PROMEDIO_REFERENCIA
    lam1_aj = lam1 * factor
    lam2_aj = lam2 * factor

    if lam1_aj <= 0 and lam2_aj <= 0:
        return 1/3, 1/3, 1/3

    p_j1 = 0.0
    p_j2 = 0.0
    p_emp = 0.0
    pmf1 = [poisson.pmf(i, lam1_aj) for i in range(k_max + 1)]
    pmf2 = [poisson.pmf(j, lam2_aj) for j in range(k_max + 1)]
    for i in range(k_max + 1):
        for j in range(k_max + 1):
            p_ij = pmf1[i] * pmf2[j]
            if i > j:
                p_j1 += p_ij
            elif j > i:
                p_j2 += p_ij
            else:
                p_emp += p_ij
    return sanitize_prob(p_j1), sanitize_prob(p_emp), sanitize_prob(p_j2)

def handicaps_legs(pr1, pr2, j1_saca_primero=True):
    """Hándicaps de legs derivados de las probabilidades de marcador exacto del
    modelo ELO leg-a-leg. Mucho más fiel que la aproximación heurística previa.

    Marcadores favorables a J1: (4,0), (4,1), (4,2), (4,3).
    - J1 -1.5 (gana por ≥2 legs)  = P(4-0) + P(4-1) + P(4-2)
    - J1 -2.5 (gana por ≥3 legs)  = P(4-0) + P(4-1)
    - J1 +1.5 (no pierde por ≥2)  = 1 - [P(0-4) + P(1-4) + P(2-4)]
    - J1 +2.5 (no pierde por ≥3)  = 1 - [P(0-4) + P(1-4)]
    """
    if pr1 <= 0 and pr2 <= 0:
        return {k: 0.5 for k in ["J1 -1.5 Legs", "J1 -2.5 Legs", "J1 +1.5 Legs",
                                  "J1 +2.5 Legs", "J2 -1.5 Legs", "J2 -2.5 Legs",
                                  "J2 +1.5 Legs", "J2 +2.5 Legs"]}
    finales = simular_match(pr1, pr2, j1_saca_primero)
    p_4_0 = finales.get((4, 0), 0.0)
    p_4_1 = finales.get((4, 1), 0.0)
    p_4_2 = finales.get((4, 2), 0.0)
    p_0_4 = finales.get((0, 4), 0.0)
    p_1_4 = finales.get((1, 4), 0.0)
    p_2_4 = finales.get((2, 4), 0.0)
    return {
        "J1 -1.5 Legs": sanitize_prob(p_4_0 + p_4_1 + p_4_2),
        "J1 -2.5 Legs": sanitize_prob(p_4_0 + p_4_1),
        "J1 +1.5 Legs": sanitize_prob(1.0 - (p_0_4 + p_1_4 + p_2_4)),
        "J1 +2.5 Legs": sanitize_prob(1.0 - (p_0_4 + p_1_4)),
        "J2 -1.5 Legs": sanitize_prob(p_0_4 + p_1_4 + p_2_4),
        "J2 -2.5 Legs": sanitize_prob(p_0_4 + p_1_4),
        "J2 +1.5 Legs": sanitize_prob(1.0 - (p_4_0 + p_4_1 + p_4_2)),
        "J2 +2.5 Legs": sanitize_prob(1.0 - (p_4_0 + p_4_1)),
    }

def legs_totales(pr1, pr2, j1_saca_primero=True):
    """Total de legs (over/under 5.5) derivado del modelo ELO leg-a-leg.
    Bo7 → posibles totales: 4 (4-0/0-4), 5 (4-1/1-4), 6 (4-2/2-4), 7 (4-3/3-4).
    """
    if pr1 <= 0 and pr2 <= 0:
        return {"Más de 5.5": 0.5, "Menos de 5.5": 0.5}
    finales = simular_match(pr1, pr2, j1_saca_primero)
    p_4 = finales.get((4, 0), 0.0) + finales.get((0, 4), 0.0)  # 4 legs totales
    p_5 = finales.get((4, 1), 0.0) + finales.get((1, 4), 0.0)
    p_6 = finales.get((4, 2), 0.0) + finales.get((2, 4), 0.0)
    p_7 = finales.get((4, 3), 0.0) + finales.get((3, 4), 0.0)
    p_under = p_4 + p_5
    p_over = p_6 + p_7
    return {
        "Más de 5.5": sanitize_prob(p_over),
        "Menos de 5.5": sanitize_prob(p_under),
    }

def prob_a_cuota(p):
    p_safe = sanitize_prob(p)
    cuota = 1.0 / p_safe
    return max(1.01, min(999.0, cuota))


# =====================================================================
# Modelo predictivo ELO leg-a-leg (Modus Super Series, Bo7 first-to-4)
# =====================================================================
# Constantes calibradas según la especificación matemática.
# Cambiar estos valores recalibra TODO el modelo de victoria, hándicaps y legs.

ELO_S = 60.0     # Sensibilidad: a menor S, el favorito tiene más peso
ELO_B = 10.0      # Bonus de saque (Throw First Advantage), en puntos de PG

# Referencia para escalar lambda de 180s. Si E[legs] del partido > 5.7,
# se esperan más 180s; si E[legs] < 5.7, menos. Calibrado a partidos equilibrados.
LEGS_PROMEDIO_REFERENCIA = 5.7


def prob_leg(pg1, pg2, j1_saca, S=ELO_S, B=ELO_B):
    """Probabilidad de que J1 gane UN leg, según quién saca.

    Modelo logístico tipo ELO: P = 1 / (1 + 10^((PG_oponente_efectivo - PG_propio_efectivo) / S))
    donde el saque añade B puntos al PG del que tiene el dardo.
    """
    if j1_saca:
        diff = pg2 - (pg1 + B)
    else:
        diff = (pg2 + B) - pg1
    return 1.0 / (1.0 + 10 ** (diff / S))


def _simular_bo7_un_inicio(pg1, pg2, j1_saca_primero, S, B):
    """Matriz de estados del Bo7. Estado = (legs_j1, legs_j2). Al inicio (0,0).
    En cada paso, el leg actual = l1+l2+1 (1-indexed):
        - leg impar  → saca el jugador inicial
        - leg par    → saca el otro
    El bucle ramifica las probabilidades hasta que cada estado llega a 4 legs.
    Devuelve dict {(l1, l2): prob} con TODOS los marcadores finales.
    """
    estados = {(0, 0): 1.0}
    finales = {}
    while estados:
        nuevos = {}
        for (l1, l2), p in estados.items():
            if l1 >= 4 or l2 >= 4:
                finales[(l1, l2)] = finales.get((l1, l2), 0.0) + p
                continue
            leg_actual = l1 + l2 + 1
            # Leg impar → saca el inicial; leg par → saca el otro
            j1_saca_este_leg = ((leg_actual % 2) == 1) == j1_saca_primero
            p_j1_gana = prob_leg(pg1, pg2, j1_saca_este_leg, S, B)
            nuevos[(l1 + 1, l2)] = nuevos.get((l1 + 1, l2), 0.0) + p * p_j1_gana
            nuevos[(l1, l2 + 1)] = nuevos.get((l1, l2 + 1), 0.0) + p * (1.0 - p_j1_gana)
        estados = nuevos
    return finales


@lru_cache(maxsize=512)
def _simular_match_cached(pg1, pg2, j1_saca_primero, S, B):
    """Simula el Bo7 sabiendo quién saca primero. La ventaja del TFA se aplica
    íntegramente al jugador que empieza (no se promedia con el escenario contrario).

    @lru_cache evita re-simular cuando la misma combinación se consulta varias
    veces dentro de un mismo render. Devuelve tupla ordenada (hashable).
    """
    finales = _simular_bo7_un_inicio(pg1, pg2, j1_saca_primero, S, B)
    return tuple(sorted(finales.items()))


def simular_match(pg1, pg2, j1_saca_primero=True, S=ELO_S, B=ELO_B):
    """Devuelve dict {(legs_j1, legs_j2): probabilidad} para el Bo7. El parámetro
    `j1_saca_primero` indica quién tiene el dardo en el leg 1; los siguientes
    legs alternan automáticamente (par/impar)."""
    return dict(_simular_match_cached(
        float(pg1), float(pg2), bool(j1_saca_primero), float(S), float(B)
    ))


def legs_esperados_desde_finales(finales):
    """E[legs totales] = Σ legs * P(legs). Útil para ajustar lambda en 180s."""
    return sum((l1 + l2) * p for (l1, l2), p in finales.items())

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
                    
                    st.markdown(
                        f"<div style='margin-top: {16 if idx > 1 else 6}px; padding: 10px 14px; "
                        f"background: rgba(150,150,150,0.10); border-left: 4px solid {color_jug}; "
                        f"border-radius: 6px;'>"
                        f"<div style='display: flex; justify-content: space-between; align-items: center; "
                        f"gap: 10px; flex-wrap: wrap;'>"
                        f"<span style='font-weight: 600; color: #444; font-size: 13px;'>"
                        f"#{idx} · <span style='color: #888;'>{p['dia']}</span></span>"
                        f"<span style='font-size: 14px;'>"
                        f"<span style='color: {color_jug}; font-weight: 700;'>{nombre}</span> "
                        f"<span style='color: #888;'>vs</span> "
                        f"<span style='color: {color_rival}; font-weight: 700;'>{p['rival']}</span>"
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
                        # mostrar resto como pares etiqueta-valor en mini-grid
                        items = []
                        for k, v in stats.items():
                            k_str = str(k).strip()
                            v_str = str(v).strip()
                            if not k_str or k_str.lower().startswith("unnamed"):
                                continue
                            if v_str.lower() in ('', 'nan'):
                                continue
                            # Saltar la celda que contiene el propio nombre del jugador
                            if v_str.lower() == nombre.lower():
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

def _extraer_metricas_jugadores(stats_dict):
    """Helper común para heatmap y radar: extrae las 5 métricas clave de cada
    jugador y las devuelve como DataFrame ya saneado.

    Devuelve un DataFrame con columnas:
        Jugador | Media 180 | Promedio Puntos | Checkout % | % Victoria | Puntuación Global

    Maneja los sinónimos típicos de las jornadas diarias y del Resumen Semanal,
    y aplica la conversión defensiva 0-1 → 0-100 para Checkout y % Victoria.
    Filas con todas las métricas a None se eliminan.
    """
    metricas = [
        ("Media 180", ["media 180 por partida", "180 por partida", "180 por partido", "media 180"]),
        ("Promedio Puntos", ["promedio puntos total", "promedio puntos", "media puntos", "promedio dardos", "average"]),
        ("Checkout %", ["promedio checkouts", "promedio checkout", "checkouts", "checkout"]),
        ("% Victoria", ["porcentaje victoria", "porcentaje de victoria", "% victoria", "%victoria"]),
        ("Puntuación Global", ["puntiación global", "puntuación global", "puntacion global", "puntiación", "puntuación", "puntacion"]),
    ]

    def buscar_valor(stats, sinonimos, nombre_metrica):
        for syn in sinonimos:
            syn_lower = syn.lower()
            for k, v in stats.items():
                if syn_lower in str(k).lower():
                    try:
                        num = float(str(v).replace('%', '').replace(',', '.').strip())
                        if 0 < num <= 1 and ("checkout" in nombre_metrica.lower() or "victoria" in nombre_metrica.lower()):
                            num *= 100
                        return num
                    except:
                        continue
        return None

    rows = []
    for jugador, stats in stats_dict.items():
        fila = {"Jugador": str(jugador).title()}
        for nombre_metrica, sinonimos in metricas:
            fila[nombre_metrica] = buscar_valor(stats, sinonimos, nombre_metrica)
        rows.append(fila)

    df = pd.DataFrame(rows)
    if df.empty:
        return df, [m[0] for m in metricas]

    cols_metricas = [m[0] for m in metricas]
    df = df.dropna(how='all', subset=cols_metricas).reset_index(drop=True)
    return df, cols_metricas


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


GRUPOS_DIAS = {
    "Grupo A": ["Grupo A Lunes", "Grupo A Martes", "Grupo A Miércoles"],
    "Grupo B": ["Grupo B Jueves", "Grupo B Viernes"],
    "Grupo C": ["Grupo C Jueves", "Grupo C Viernes"],
}

# Configuración del coloreado de la clasificación por grupo:
# 'verdes' = nº de filas desde arriba que se pintan en verde (clasifican / mejor posición)
# 'rojos'  = nº de filas desde abajo que se pintan en rojo (eliminados / peor posición)
# En Grupo A solo se pinta el líder, sin rojos. Grupo B: 2 arriba, 3 abajo. Grupo C: 3 y 3.
COLORES_CLASIFICACION = {
    "Grupo A": {"verdes": 1, "rojos": 0},
    "Grupo B": {"verdes": 3, "rojos": 2},
    "Grupo C": {"verdes": 2, "rojos": 4},
}


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


def calcular_clasificacion_grupo(grupo):
    """Calcula la clasificación de un grupo sumando todos los partidos terminados
    de los días que lo componen.

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

    stats = {}  # key: nombre_lower → dict con stats
    for dia in GRUPOS_DIAS[grupo]:
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


def render_clasificacion_grupo(grupo):
    """Renderiza la tabla de clasificación de un grupo aplicando los colores
    configurados en COLORES_CLASIFICACION (verdes desde arriba, rojos desde abajo).

    Si verdes + rojos > nº de jugadores, el verde tiene prioridad para evitar
    pintar la misma fila dos veces.
    """
    df = calcular_clasificacion_grupo(grupo)
    if df is None or df.empty:
        st.info(f"ℹ️ Aún no hay partidos terminados en {grupo}")
        return

    st.subheader(f"🏆 Clasificación {grupo}")

    n = len(df)
    config = COLORES_CLASIFICACION.get(grupo, {"verdes": 1, "rojos": 0})
    n_verdes = config["verdes"]
    n_rojos = config["rojos"]
    umbral_rojo = n - n_rojos  # filas con idx >= umbral_rojo van en rojo

    def estilo_fila(fila):
        idx = fila.name
        if idx < n_verdes:
            return ['background-color: rgba(40,167,69,0.18); font-weight: 600;'] * len(fila)
        if n_rojos > 0 and idx >= umbral_rojo:
            return ['background-color: rgba(220,53,69,0.12);'] * len(fila)
        return [''] * len(fila)

    styled = df.style.apply(estilo_fila, axis=1).set_properties(**{
        'text-align': 'center',
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
        {'selector': 'th.col_heading', 'props': [('background-color', '#1f2937'), ('color', 'white')]},
    ])

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("💡 Orden: **PTS** (2 por victoria) → **DIF** (legs a favor − en contra) → **LF** (legs a favor)")


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
        selected = selector_jornada("res", incluir_resumen=True)
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
