"""
rendering.py - Funciones de renderizado visual de la interfaz Streamlit.




Pentagonos de habilidades, tarjetas de estadisticas de jugador, barras
comparativas, heatmaps, radares y la vista completa de Value Bets.




Depende de: config, helpers, data_loading, stats_engine.
"""




import streamlit como st
import pandas como pd
import numpy, por ejemplo
de fecha y hora importar fecha y hora




desde config importar URL, CORTES, PESTANAS_CON_ESTADÍSTICAS
desde helpers importar (
safe_float, color_volatilidad, calcular_tendencia, sanitize_prob,
buscar_jugador, calcular_rendimiento, pct, insignia_rendimiento, obtener_bandera,
)
desde data_loading importar (
cargar_todo, cargar_jugadores_desde, obtener_proximos_partidos_api,
)
de stats_engine importar (
prob_victoria, prob_180s, quién_hace_más_180s, handicaps_legs,
legs_totales, prob_a_cuota, extraer_h2h_semanal, obtener_ultimos_partidos,
_extraer_metricas_jugadores,
)




# El modulo de seguimiento de predicciones es OPCIONAL: si falta el archivo
# o alguna de sus dependencias (gspread, google-auth), la app debe seguir
# funcionando con normalidad y solo se desactiva la seccion de tracking.SyntaxError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/modus/app_corregida.py", line 51, in <module>
    from rendering import (
    ...<2 lines>...
    
