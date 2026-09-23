"""
Las capas que van encima del clip: el gancho y la placa de nombre.

Van como overlay y no como placas concatenadas: un clip de 60 s no puede
regalar segundos a una cortina, y el enganche se juega en los primeros dos.
Eso también significa que **no alargan el clip**, así que nada de esto toca la
duración ni obliga a volver a cortar — solo al render.

Las instrucciones son parámetros, no texto libre para un modelo: el usuario
elige un estilo y escribe el texto. Es predecible y no cuesta tokens.
"""

import re

HOOK_STYLES = ("pop", "slide", "type")
HOOK_POSITIONS = ("top", "center", "bottom")
LOWER_SIDES = ("left", "right")

# El gancho arranca casi enseguida y dura poco: es para el que está decidiendo
# si se queda, no para el que ya se quedó.
DEFAULT_HOOK = {
    "on": False,
    "text": "",          # vacío = el título del clip
    "style": "pop",
    "position": "top",
    "start": 0.2,
    "dur": 2.6,
}

# Las placas NO tapan el video por default: `dim` es cuánto se oscurece el
# fondo, y 0,55 deja ver el movimiento de atrás, que es lo que sostiene la
# atención mientras se lee. Con 1 se consigue la placa opaca de toda la vida.
DEFAULT_CARD = {
    "on": False,
    "title": "",
    "subtitle": "",
    "dur": 2.0,
    "dim": 0.55,
}

# La placa entra después del gancho para no pisarlo.
DEFAULT_LOWER = {
    "on": False,
    "name": "",
    "role": "",
    "start": 3.2,
    "dur": 4.0,
    "side": "left",
}


def _num(val, default: float) -> float:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    return f if f == f and abs(f) != float("inf") else default   # descarta NaN/inf


def _opcion(val, validas: tuple, default: str) -> str:
    return val if val in validas else default


def hook_defaults() -> dict:
    return dict(DEFAULT_HOOK)


def lower_defaults() -> dict:
    return dict(DEFAULT_LOWER)


def parse_hosts(texto: str) -> list:
    """
    "Nombre: Rol" por línea → [{"name", "role"}].

    Es el mismo texto que el usuario ya cargó en Ajustes para que el modelo
    sepa quién habla; sirve igual para ofrecer los nombres de la placa sin
    hacérselos escribir de nuevo.
    """
    salida = []
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        nombre, _, rol = linea.partition(":")
        nombre = nombre.strip()
        if nombre:
            salida.append({"name": nombre, "role": rol.strip()})
    return salida


def normalize(overlays: dict | None, clip_duration: float | None = None) -> dict:
    """
    Deja las capas en un estado que el render puede dibujar sin sorpresas.

    Completa lo que falte, descarta valores inválidos y recorta los tiempos a la
    duración del clip: un gancho que arranca en el segundo 80 de un clip de 60
    no se ve nunca, y encontrar eso mirando un render es carísimo.
    """
    overlays = overlays if isinstance(overlays, dict) else {}
    dur_max = _num(clip_duration, 0.0)

    hook = {**DEFAULT_HOOK, **(overlays.get("hook") or {})}
    hook["on"] = bool(hook["on"])
    hook["text"] = str(hook.get("text") or "")
    hook["style"] = _opcion(hook.get("style"), HOOK_STYLES, DEFAULT_HOOK["style"])
    hook["position"] = _opcion(hook.get("position"), HOOK_POSITIONS, DEFAULT_HOOK["position"])
    hook["start"] = max(0.0, _num(hook.get("start"), DEFAULT_HOOK["start"]))
    hook["dur"] = max(0.3, _num(hook.get("dur"), DEFAULT_HOOK["dur"]))

    lower = {**DEFAULT_LOWER, **(overlays.get("lower") or {})}
    lower["on"] = bool(lower["on"])
    lower["name"] = str(lower.get("name") or "")
    lower["role"] = str(lower.get("role") or "")
    lower["side"] = _opcion(lower.get("side"), LOWER_SIDES, DEFAULT_LOWER["side"])
    lower["start"] = max(0.0, _num(lower.get("start"), DEFAULT_LOWER["start"]))
    lower["dur"] = max(0.3, _num(lower.get("dur"), DEFAULT_LOWER["dur"]))

    if dur_max > 0:
        for capa in (hook, lower):
            capa["start"] = min(capa["start"], max(0.0, dur_max - 0.3))
            capa["dur"] = min(capa["dur"], dur_max - capa["start"])

    cards = {}
    for clave in ("intro", "outro"):
        c = {**DEFAULT_CARD, **(overlays.get(clave) or {})}
        c["on"] = bool(c["on"])
        c["title"] = str(c.get("title") or "")
        c["subtitle"] = str(c.get("subtitle") or "")
        c["dur"] = max(0.3, _num(c.get("dur"), DEFAULT_CARD["dur"]))
        c["dim"] = min(1.0, max(0.0, _num(c.get("dim"), DEFAULT_CARD["dim"])))
        if dur_max > 0:
            # Una placa más larga que el clip taparía el clip entero.
            c["dur"] = min(c["dur"], dur_max)
        cards[clave] = c

    return {"hook": hook, "lower": lower, **cards}


def for_render(clip: dict) -> dict | None:
    """
    Lo que se le manda a Remotion, o None si el clip no tiene ninguna capa.

    Devolver None y no un dict con todo apagado es a propósito: así el prop no
    viaja, `OverlayLayer` corta enseguida, y un clip sin capas renderiza
    exactamente como antes de que esto existiera.
    """
    dur = clip.get("clip_duration") or (clip.get("end", 0) - clip.get("start", 0))
    capas = normalize(clip.get("overlays"), dur)

    # Una capa prendida sin nada que mostrar no se dibuja: el gancho cae al
    # título del clip, pero la placa sin nombre no tiene con qué.
    hook_util = capas["hook"]["on"] and bool(
        capas["hook"]["text"].strip() or str(clip.get("title") or "").strip()
    )
    lower_util = capas["lower"]["on"] and bool(capas["lower"]["name"].strip())

    # Una placa sin título no tiene nada que mostrar (a diferencia del gancho,
    # no tiene de dónde sacar un texto).
    cards_utiles = {
        k: capas[k] for k in ("intro", "outro")
        if capas[k]["on"] and capas[k]["title"].strip()
    }
    if not hook_util and not lower_util and not cards_utiles:
        return None

    salida = {}
    if hook_util:
        salida["hook"] = capas["hook"]
    if lower_util:
        salida["lower"] = capas["lower"]
    salida.update(cards_utiles)
    return salida


def collision(clip: dict) -> str | None:
    """
    Aviso si dos capas van a quedar una encima de la otra.

    Pasa con el gancho puesto "abajo" y la placa de nombre: las dos se apoyan
    justo arriba de la zona que tapa la interfaz de la app, así que si además
    coinciden en el tiempo se pisan. Es barato avisarlo acá y carísimo
    descubrirlo en el render.
    """
    capas = for_render(clip)
    if not capas:
        return None

    avisos = []

    # El gancho abajo y la placa de nombre se apoyan los dos justo arriba de la
    # zona que tapa la interfaz de la app.
    h, l = capas.get("hook"), capas.get("lower")
    if h and l and h["position"] == "bottom":
        desde = max(h["start"], l["start"])
        hasta = min(h["start"] + h["dur"], l["start"] + l["dur"])
        if hasta > desde:
            avisos.append(
                f"El gancho abajo y la placa de nombre se pisan entre el segundo "
                f"{desde:.1f} y el {hasta:.1f}."
            )

    # La placa de apertura ocupa el centro desde el frame 0; el gancho suele
    # estar ahí en el mismo momento.
    intro = capas.get("intro")
    if h and intro and h["start"] < intro["dur"]:
        avisos.append(
            f"La placa de apertura dura {intro['dur']:.1f} s y el gancho arranca en "
            f"{h['start']:.1f} s: se superponen."
        )

    if not avisos:
        return None
    return " ".join(avisos) + " Corré uno en el tiempo, o movelo de lugar."


def describe(clip: dict) -> str:
    """Resumen de una línea para mostrar en la lista de clips."""
    capas = for_render(clip)
    if not capas:
        return ""
    partes = []
    if "hook" in capas:
        partes.append("gancho")
    if "lower" in capas:
        partes.append(f"placa: {capas['lower']['name']}")
    return " · ".join(partes)
