# -*- coding: utf-8 -*-
"""
Plugin: ajuste del CV al puesto (CV vs. aviso de trabajo).

Se activa con:  python cv_checker.py CV.pdf --vacante aviso.txt [--estricto] [--practicas]

Qué hace (sin IA ni servicios externos):
  1. Separa el aviso en bloques: excluyentes / deseables / funciones (por encabezados
     como "Requisitos", "Indispensable", "Deseable", "Funciones", "Responsabilidades").
  2. Para cada requisito mide la evidencia en el CV en dos niveles:
       - EXACTA   : la frase del aviso aparece tal cual (lo que busca un ATS booleano).
       - PARCIAL  : aparecen la mayoría de sus palabras clave, con plurales y tildes
                    normalizados (lo que vería un lector humano o un ATS semántico).
  3. Compara requisitos "duros": años de experiencia, estado académico (ciclo, egresado,
     bachiller), nivel de inglés.
  4. Devuelve un % de ajuste y la lista de brechas, para decidir qué agregar SOLO si es cierto.

Formato recomendado de aviso.txt (también acepta texto libre):
  Puesto: Practicante de Mantenimiento
  Empresa: ...
  Requisitos:
  - Estudiante de 8.º ciclo a más de Ingeniería Mecatrónica
  - Conocimiento de PLC Siemens (TIA Portal)
  Deseable:
  - Inglés intermedio
  Funciones:
  - Ejecutar mantenimiento preventivo de equipos
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cv_checker import Resultado, norm, STOPWORDS, RE_RANGO, MESES  # noqa: E402

BLOQUES = {
    "excluyentes": ["requisitos", "requerimientos", "requisito", "indispensable", "excluyente", "excluyentes",
                    "perfil requerido", "lo que buscamos", "buscamos", "debes contar con", "necesario"],
    "deseables": ["deseable", "deseables", "valorable", "se valorara", "plus", "sera un plus", "opcional"],
    "funciones": ["funciones", "responsabilidades", "que haras", "tus retos", "actividades", "principales funciones"],
    "ignorar": ["beneficios", "ofrecemos", "te ofrecemos", "condiciones", "horario", "lugar", "modalidad", "sueldo",
                "salario", "empresa", "puesto", "sobre nosotros", "ubicacion"],
}

PALABRAS_VACIAS = STOPWORDS | set("""
conocimiento conocimientos manejo experiencia capacidad habilidad habilidades nivel minimo minima deseable
indispensable conocer dominio uso buen buena buenos buenas excelente solida solido alta alto basico basica
estudiante estudiantes egresado egresada carrera carreras afines afin ingenieria ingeniero tecnico similar
similares relacionadas relacionados etc incluye mas menos años anos ano año meses mes
apoyar apoyo brindar realizar participar colaborar asistir encargarse contar tener
""".split())


def _stem(w: str) -> str:
    """Raíz aproximada: une infinitivo del aviso ("documentar") con pasado del CV ("documenté"),
    y singular con plural ("equipo"/"equipos")."""
    w = norm(w)

    def cortar(x, suf):
        return x[: -len(suf)] if x.endswith(suf) and len(x) - len(suf) >= 3 else x

    for suf in ("aciones", "acion", "iciones", "icion", "ciones", "cion", "ando", "iendo", "aste", "iste", "amos", "imos"):
        nuevo = cortar(w, suf)
        if nuevo != w:
            w = nuevo
            break
    for suf in ("es", "s"):
        nuevo = cortar(w, suf)
        if nuevo != w:
            w = nuevo
            break
    for suf in ("ar", "er", "ir"):
        nuevo = cortar(w, suf)
        if nuevo != w:
            w = nuevo
            break
    if w and w[-1] in "aeio" and len(w) > 3:
        w = w[:-1]
    return w


def _tokens(texto: str):
    return [t for t in re.findall(r"[a-záéíóúñü0-9+#./-]{2,}", texto.lower())
            if norm(t) not in PALABRAS_VACIAS and not re.fullmatch(r"\d+", t)]


def parsear_aviso(texto: str) -> dict:
    out = {"excluyentes": [], "deseables": [], "funciones": [], "libre": []}
    actual = "libre"
    for linea in texto.splitlines():
        l = linea.strip(" \t•-–—*·").strip()
        if not l:
            continue
        cab = norm(l.split(":")[0])
        clave = next((k for k, vs in BLOQUES.items() if any(cab == v or cab.startswith(v + " ") for v in vs)), None)
        if clave:
            actual = clave
            resto = l.split(":", 1)[1].strip() if ":" in l else ""
            if not resto:
                continue
            l = resto
        if actual == "ignorar":
            continue
        # Un ítem por línea; si una línea trae varios separados por comas o ";", se dividen.
        partes = [p.strip() for p in re.split(r";|,(?![^()]*\))", l) if len(p.strip()) > 2]
        out[actual].extend(partes if len(partes) > 1 and all(len(p) < 80 for p in partes) else [l])
    if not any(out[k] for k in ("excluyentes", "deseables", "funciones")):
        out["excluyentes"] = out["libre"]  # texto libre: todo se trata como requisito
    return out


def evidencia(item: str, cv_norm: str, cv_stems: set) -> tuple:
    """Devuelve (nivel, faltantes): nivel 1.0 exacta, 0.5–0.99 parcial, 0 sin evidencia."""
    if norm(item) in cv_norm:
        return 1.0, []
    toks = _tokens(item)
    if not toks:
        return 1.0, []
    hallados = [t for t in toks if norm(t) in cv_norm or _stem(t) in cv_stems]
    frac = len(hallados) / len(toks)
    faltan = [t for t in toks if t not in hallados]
    return (round(min(0.99, frac), 2) if frac >= 0.5 else 0.0), faltan


# --- Requisitos duros ------------------------------------------------------------

def _mes_anio(txt: str, anio_defecto=None):
    t = norm(txt)
    if re.search(r"actualidad|presente|a la fecha|actual|present", t):
        return None  # abierto
    m = re.search(r"(\d{1,2})/(\d{4})", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    mes = next((v for k, v in MESES.items() if re.search(rf"\b{k}\b", t)), None)
    a = re.search(r"(19|20)\d{2}", t)
    anio = int(a.group(0)) if a else anio_defecto
    if anio is None:
        return None
    return anio, (mes or 1)


def meses_experiencia(cv) -> int:
    total = 0
    for linea in cv.secciones.get("experiencia", []):
        for m in RE_RANGO.finditer(linea):
            fin = _mes_anio(m.group(2))
            if fin is None:
                fin = (2026, 10)  # abierto: se cuenta hasta la fecha de cálculo aproximada
            ini = _mes_anio(m.group(1), anio_defecto=fin[0])
            if ini is None:
                continue
            total += max(1, (fin[0] - ini[0]) * 12 + (fin[1] - ini[1]) + 1)
    return total


NIVELES_IDIOMA = {"basico": 1, "elemental": 1, "intermedio": 2, "intermedio alto": 3, "avanzado": 4, "fluido": 4,
                  "nativo": 5, "b1": 2, "b2": 3, "c1": 4, "c2": 5, "a2": 1}


def _nivel(texto: str, idioma: str):
    t = norm(texto)
    m = re.search(rf"{idioma}[^.\n]{{0,25}}?\b(basico|elemental|intermedio alto|intermedio|avanzado|fluido|nativo|"
                  rf"a2|b1|b2|c1|c2)\b", t) or re.search(rf"\b(basico|intermedio alto|intermedio|avanzado|fluido|nativo)\b"
                                                     rf"[^.\n]{{0,15}}{idioma}", t)
    return NIVELES_IDIOMA.get(m.group(1)) if m else None


def _ciclo(texto: str):
    t = norm(texto)
    m = re.search(r"\b(\d{1,2})\s*(?:°|º|\.º|vo|mo|no|er|ro|to|avo)?\s*ciclo", t)
    if m:
        return int(m.group(1))
    orden = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6, "septimo": 7,
             "setimo": 7, "octavo": 8, "noveno": 9, "decimo": 10, "undecimo": 11, "duodecimo": 12}
    m = re.search(r"\b(" + "|".join(orden) + r")\s+ciclo", t)
    return orden[m.group(1)] if m else None


def requisitos_duros(aviso: str, cv, estricto: bool):
    res = []
    av = norm(aviso)
    cvt = norm(cv.texto)
    # Años de experiencia
    m = re.search(r"(\d+)\s*(?:\+\s*)?(?:a[nñ]os?|anos?)\s+(?:de\s+)?experiencia", av) or \
        re.search(r"experiencia\s+(?:minima\s+)?(?:de\s+)?(\d+)\s*(?:a[nñ]os?|anos?)", av)
    if m:
        req = int(m.group(1)) * 12
        tiene = meses_experiencia(cv)
        ok = tiene >= req
        res.append(Resultado("Adaptación", f"Experiencia mínima ({req // 12} año/s)", 1.0 if ok else tiene / req, 2,
                             duro=not ok and estricto and tiene < req * 0.5, aprobado=ok,
                             problemas=[] if ok else [f"El aviso pide {req // 12} año/s; el CV suma ~{tiene} meses en "
                                                      "Experiencia (prácticas y proyectos con fechas pueden sumar si son reales)."],
                             sugerencia="Si tienes experiencia relevante en proyectos o voluntariado con fechas, muéstrala."))
    # Estado académico
    pide_egresado = re.search(r"\b(egresad[oa]s?|bachiller|titulad[oa]s?|colegiad[oa]s?)\b", av)
    pide_ciclo = _ciclo(av)
    ciclo_cv = _ciclo(cvt)
    es_estudiante = bool(re.search(r"\bestudiante\b", cvt)) and not re.search(r"\b(egresad|bachiller|titulad)", cvt)
    if pide_ciclo:
        ok = ciclo_cv is not None and ciclo_cv >= pide_ciclo
        res.append(Resultado("Adaptación", f"Ciclo académico (≥ {pide_ciclo}.º)", 1.0 if ok else 0.0, 2, duro=not ok,
                             aprobado=ok,
                             problemas=[] if ok else [f"El aviso pide desde {pide_ciclo}.º ciclo; el CV "
                                                      f"{'indica ' + str(ciclo_cv) + '.º' if ciclo_cv else 'no indica el ciclo'}."],
                             sugerencia="Declara el ciclo en Educación (p. ej. 'Estudiante de 10.º ciclo')."))
    elif pide_egresado and not re.search(r"\b(o|y/o)\s+(estudiante|ultimos ciclos)", av):
        ok = not es_estudiante
        res.append(Resultado("Adaptación", f"Grado requerido ({pide_egresado.group(1)})", 1.0 if ok else 0.0, 2,
                             duro=not ok, aprobado=ok,
                             problemas=[] if ok else [f"El aviso pide '{pide_egresado.group(1)}' y el CV indica estudiante. "
                                                      "En Perú es filtro legal (Ley 28518: prácticas profesionales = egresados)."],
                             sugerencia="Postula solo si cumples; si egresas pronto, indica la fecha prevista de egreso."))
    # Inglés
    req_en = _nivel(av, "ingles")
    if req_en:
        cv_en = _nivel(cvt, "ingles")
        ok = cv_en is not None and cv_en >= req_en
        res.append(Resultado("Adaptación", "Nivel de inglés", 1.0 if ok else (0.5 if cv_en else 0.0), 1,
                             duro=False, aprobado=ok,
                             problemas=[] if ok else ["El aviso pide un nivel de inglés mayor al declarado en el CV."
                                                      if cv_en else "El aviso pide inglés y el CV no declara nivel."],
                             sugerencia="Declara el nivel real (y certificado si lo tienes); no lo subas sin evidencia."))
    return res


def check(cv, args):
    if not getattr(args, "vacante", None):
        return []
    aviso = Path(args.vacante).read_text(encoding="utf-8", errors="replace")
    bloques = parsear_aviso(aviso)
    cv_norm = norm(cv.texto)
    cv_stems = {_stem(t) for t in re.findall(r"[a-záéíóúñü0-9+#./-]{2,}", cv.texto.lower())}
    resultados = []
    pesos = {"excluyentes": 3, "deseables": 1, "funciones": 1.5}
    resumen = {}
    for bloque, peso in pesos.items():
        items = bloques[bloque]
        if not items:
            continue
        evals = [(it,) + evidencia(it, cv_norm, cv_stems) for it in items]
        exactas = [e for e in evals if e[1] == 1.0]
        parciales = [e for e in evals if 0 < e[1] < 1]
        nulas = [e for e in evals if e[1] == 0]
        puntaje = sum(e[1] for e in evals) / len(evals)
        resumen[bloque] = puntaje
        meta = 0.75 if args.estricto else 0.6
        probs = []
        if nulas:
            probs.append(f"Sin evidencia ({len(nulas)}): " + " | ".join(e[0][:70] for e in nulas[:8]))
        if parciales:
            probs.append(f"Parcial ({len(parciales)}), falta la palabra exacta: " +
                         " | ".join(f"{e[0][:50]} → " + (f"falta {', '.join(e[2][:3])}" if e[2] else "mismas palabras, otro orden")
                                    for e in parciales[:6]))
        nombre = {"excluyentes": "Requisitos del aviso", "deseables": "Deseables del aviso",
                  "funciones": "Funciones del puesto reflejadas en el CV"}[bloque]
        resultados.append(Resultado(
            "Adaptación", f"{nombre}: {len(exactas)} exactas, {len(parciales)} parciales, {len(nulas)} sin evidencia",
            puntaje, peso, duro=(bloque == "excluyentes" and args.estricto and len(nulas) > 0 and
                                 len(nulas) / len(evals) > 0.34),
            aprobado=puntaje >= meta and not (bloque == "excluyentes" and nulas), problemas=probs,
            sugerencia="Agrega SOLO lo que sea cierto, con la palabra exacta del aviso. Lo que no cumples, no se escribe: "
                       "evalúa si conviene postular."))
    resultados += requisitos_duros(aviso, cv, args.estricto)
    if resumen:
        w = sum(pesos[b] for b in resumen)
        ajuste = sum(resumen[b] * pesos[b] for b in resumen) / w
        veredicto = ("ALTO" if ajuste >= 0.8 else "MEDIO" if ajuste >= 0.6 else "BAJO")
        resultados.append(Resultado("Adaptación", f"Ajuste global al puesto: {ajuste:.0%} ({veredicto})", ajuste, 0.5,
                                    aprobado=ajuste >= (0.75 if args.estricto else 0.6),
                                    problemas=[] if ajuste >= 0.6 else
                                    ["Ajuste bajo: o el CV no muestra experiencias que sí tienes, o el puesto no "
                                     "encaja con tu perfil actual."],
                                    sugerencia="Revisa las brechas de arriba antes de postular."))
    return resultados
