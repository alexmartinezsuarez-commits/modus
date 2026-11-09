"""Partido terminado a 4 legs (lo normal) o a 3 (algunas semanas)."""

import modelo.datos as md
from config import partido_terminado


def test_terminado_a_4_y_a_3():
    assert partido_terminado(4, 2) and partido_terminado(1, 4)
    assert partido_terminado(3, 2) and partido_terminado(0, 3)
    assert not partido_terminado(0, 0)
    assert not partido_terminado(2, 1)
    assert not partido_terminado("", "")
    assert not partido_terminado(None, 3)


def test_jornada_a_3_legs():
    filas = [[""]] * 6 + [
        ["Steve West", "3", "1", "90", "40"], ["Conan Whitehead", "2", "0", "85", "30"],
        ["Neil Duff", "0", "0", "80", "0"], ["Archie Self", "3", "1", "92", "50"],
        ["Robert Thornton", "", "", "", "", "EN JUEGO"], ["Derek Coulson", "", "", "", ""],
        ["Conan Whitehead", "", "", "", ""], ["Neil Duff", "", "", "", ""]]
    estados = [p["estado"] for p in md.partidos_de_jornada(filas)]
    assert estados == ["terminado", "terminado", "en_juego", "pendiente"]
