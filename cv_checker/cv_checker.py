#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cv_checker.py — Verificador local de CVs (ATS + reclutador estricto), inspirado en
las categorías del Resume Checker de Enhancv, pensado para CVs en español.

Uso:
  python cv_checker.py CV.pdf
  python cv_checker.py CV.pdf --vacante aviso.txt --puesto "Técnico de Soporte" \
         --excluyentes "Power BI,Excel" --estricto --json reporte.json

Dependencias: Python 3.9+, pypdf (pip install pypdf).
Opcionales: poppler (pdftotext/pdfimages) para mejor extracción;
            language-tool-python + Java para ortografía en español.

Extensible: cualquier archivo .py dentro de ./plugins (o pasado con --plugin)
que defina  `def check(cv, args) -> list[Resultado]`  se ejecuta y suma sus
resultados al reporte. Pensado para el módulo de adaptación a la vacante.

Código de salida: 0 = APROBADO, 1 = NO APROBADO, 2 = error de lectura.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

VERSION = "1.2.0"

# ----------------------------------------------------------------------------
# Modelo de resultados
# ----------------------------------------------------------------------------

@dataclass
class Resultado:
    categoria: str          # Contenido | Secciones | ATS | Riesgos RR.HH. | Adaptación | (plugin)
    nombre: str
    puntaje: float          # 0..1
    peso: float = 1.0
    duro: bool = False      # filtro eliminatorio: si falla, el CV queda NO APROBADO
    aprobado: bool = True
    problemas: list = field(default_factory=list)
    sugerencia: str = ""


# Peso de cada categoría en el puntaje final (suma 100). "Adaptación" solo cuenta
# si se pasó --vacante / --excluyentes / --puesto; si no, se renormaliza.
PESOS_CATEGORIA = {
    "Contenido": 35,
    "Secciones": 10,
    "ATS": 25,
    "Riesgos RR.HH.": 15,
    "Adaptación": 15,
}

# ----------------------------------------------------------------------------
# Utilidades de texto
# ----------------------------------------------------------------------------

def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", sin_tildes(s).lower()).strip()


STOPWORDS = set("""
a al algo ante antes como con contra cual cuando de del desde donde durante e el ella ellos en entre era es esa ese eso esta este esto
fue ha hasta la las le les lo los mas me mi mis muy ni no o os otra otro para pero por que se segun ser si sin sobre su sus tambien
tanto te tiene todo tras tu un una uno unos unas y ya yo the and of to in for with on at by an or as is are be from that this your you
nivel area areas asi cada otros otras etc incluyendo mediante través traves bajo segun forma tipo
requisitos requisito deseable deseables funciones empresa puesto beneficios beneficio seguro eps ofrecemos buscamos postula postular vacante modalidad horario sueldo
""".split())

MESES = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3, "abr": 4, "abril": 4, "may": 5, "mayo": 5,
    "jun": 6, "junio": 6, "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "set": 9, "sep": 9, "sept": 9,
    "septiembre": 9, "setiembre": 9, "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11, "dic": 12,
    "diciembre": 12, "jan": 1, "apr": 4, "aug": 8, "dec": 12,
}

RE_MES = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|sept|set|oct|nov|dic|jan|apr|aug|dec)[a-z]*\.?"
RE_RANGO = re.compile(
    rf"((?:\d{{1,2}}\s+)?{RE_MES}\s*\d{{0,4}}|\d{{1,2}}/\d{{4}}|\d{{4}})\s*[–—-]\s*"
    rf"((?:\d{{1,2}}\s+)?{RE_MES}\s*\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}}|actualidad|presente|a la fecha|la fecha|actual|present)",
    re.I,
)

SECCIONES = {
    "perfil": ["perfil", "perfil profesional", "resumen", "resumen profesional", "acerca de mi", "sobre mi",
               "objetivo", "objetivo profesional", "summary", "profile", "professional summary"],
    "experiencia": ["experiencia", "experiencia laboral", "experiencia profesional", "experiencia relevante",
                    "historial laboral", "work experience", "experience", "professional experience"],
    "educacion": ["educacion", "formacion", "formacion academica", "estudios", "education"],
    "habilidades": ["habilidades", "habilidades tecnicas", "competencias", "competencias clave", "conocimientos",
                    "aptitudes", "skills", "technical skills", "herramientas"],
    "certificaciones": ["certificaciones", "certificados", "certificaciones coursera", "licencias y certificaciones",
                        "certifications"],
    "cursos": ["cursos", "cursos y seminarios", "cursos y seminarios relevantes", "capacitacion", "capacitaciones",
               "cursos relevantes", "courses"],
    "proyectos": ["proyectos", "proyecto de tesis", "proyectos relevantes", "tesis", "projects"],
    "actividades": ["actividades extracurriculares", "actividades extracurriculares y liderazgo", "actividades",
                    "liderazgo", "voluntariado", "extracurricular activities", "logros", "premios"],
    "idiomas": ["idiomas", "languages"],
}

VERBOS_ACCION = set(norm(v) for v in """
diseñé diseñe implementé implemente desarrollé desarrolle diagnostiqué diagnostique reparé repare instalé instale
configuré configure automaticé automatice optimicé optimice reduje aumenté aumente incrementé incremente mejoré mejore
lideré lidere coordiné coordine gestioné gestione organicé organice dirigí dirigi fundé funde capacité capacite dicté dicte
documenté documente elaboré elabore programé programe integré integre analicé analice evalué evalue ejecuté ejecute
interpreté interprete mantuve supervisé supervise planifiqué planifique logré logre obtuve gané gane presenté presente
construí construi modelé modele simulé simule calibré calibre validé valide verifiqué verifique migré migre negocié negocie
atendí atendi resolví resolvi entrené entrene creé cree establecí estableci reemplacé reemplace inspeccioné inspeccione
monitoreé monitoree medí medi estandaricé estandarice ahorré ahorre redujé
""".split())

INICIOS_DEBILES = ["responsable de", "encargado de", "encargada de", "apoyo en", "apoye en", "ayude en", "ayudé en",
                   "participe en", "participé en", "tareas de", "funciones de", "me encargue", "me encargué",
                   "realizacion de", "realización de", "colabore en", "colaboré en"]

CLICHES = ["proactivo", "proactiva", "persona dinamica", "joven dinamico", "joven dinamica", "apasionado", "apasionada", "orientado a resultados",
           "orientada a resultados", "trabajo bajo presion", "alta capacidad de", "facilidad de palabra",
           "persona responsable", "honesto", "honesta", "puntual", "team player", "hard worker", "multitasking",
           "excelente comunicacion", "pensamiento fuera de la caja", "sinergia", "con ganas de aprender"]

DATOS_SENSIBLES = {
    "DNI / documento": r"\b(dni|d\.n\.i\.|documento de identidad|pasaporte|c\.e\.|carnet de extranjeria)\b",
    "edad / nacimiento": r"\b(edad|\d{2}\s*anos|fecha de nacimiento|nacido el|nacida el)\b",
    "estado civil": r"\b(estado civil|soltero|soltera|casado|casada|divorciad[oa]|viud[oa])\b",
    "sexo / genero": r"\b(sexo|genero)\s*:",
    "religion / salud": r"\b(religion|credo|discapacidad|enfermedad)\s*:",
    "nacionalidad": r"\bnacionalidad\b",
}

RESIDUOS_IA = [r"como modelo de lenguaje", r"\[insert", r"\[insertar", r"lorem ipsum", r"\bxxx+\b", r"\btodo\s*:",
               r"\{\{", r"\}\}", r"<nombre>", r"\bplaceholder\b", r"aqui va", r"\(cifra\)"]

RE_BULLET = re.compile(r"^\s*([•●▪◦∙·\-–—*‣➢➤►✓✔o])\s+(.*)")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_TEL = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
RE_LINKEDIN = re.compile(r"linkedin\.com/in/[\w\-%]+", re.I)
RE_CIFRA = re.compile(
    r"(\d|\b(uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|quince|veinte|treinta|cien|"
    r"cientos|mil|miles|doble|triple|mitad)\b)",
    re.I,
)

# ----------------------------------------------------------------------------
# Lectura del PDF
# ----------------------------------------------------------------------------

@dataclass
class CV:
    ruta: Path
    texto: str            # orden de lectura (lo que "lee" un ATS)
    texto_layout: str     # con disposición espacial
    paginas: int
    bytes: int
    imagenes: int
    enlaces: list
    lineas: list = field(default_factory=list)
    secciones: dict = field(default_factory=dict)   # clave -> list[str] líneas
    vinetas: dict = field(default_factory=dict)     # clave sección -> list[str]
    encabezado: list = field(default_factory=list)
    titulos_no_estandar: list = field(default_factory=list)


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=60).stdout
    except Exception:
        return ""


def leer_pdf(ruta: Path) -> CV:
    texto = layout = ""
    paginas = imagenes = 0
    enlaces = []
    try:
        from pypdf import PdfReader
        r = PdfReader(str(ruta))
        paginas = len(r.pages)
        for p in r.pages:
            try:
                imagenes += len(p.images)
            except Exception:
                pass
            for a in (p.get("/Annots") or []):
                try:
                    o = a.get_object()
                    uri = o.get("/A", {}).get("/URI")
                    if uri:
                        enlaces.append(str(uri))
                except Exception:
                    pass
        if not shutil.which("pdftotext"):
            texto = "\n".join((p.extract_text() or "") for p in r.pages)
            try:
                layout = "\n".join((p.extract_text(extraction_mode="layout") or "") for p in r.pages)
            except Exception:
                layout = texto
    except ImportError:
        if not shutil.which("pdftotext"):
            sys.exit("Falta pypdf: ejecuta  pip install pypdf")
    if shutil.which("pdftotext"):
        texto = _run(["pdftotext", "-enc", "UTF-8", str(ruta), "-"])
        layout = _run(["pdftotext", "-enc", "UTF-8", "-layout", str(ruta), "-"])
        if not paginas:
            info = _run(["pdfinfo", str(ruta)])
            m = re.search(r"Pages:\s+(\d+)", info)
            paginas = int(m.group(1)) if m else 0
    cv = CV(ruta=ruta, texto=texto, texto_layout=layout, paginas=paginas, bytes=ruta.stat().st_size,
            imagenes=imagenes, enlaces=enlaces)
    segmentar(cv)
    return cv


RE_ICONO_INICIO = re.compile(r"^\s*([^\w\s•\-–—*(¿¡\"']|[ïÔÕ¢²³¹ºª§¤¥])\s+")

PREFIJOS_NO_ESTANDAR = {
    "experiencia": "experiencia", "trayectoria": "experiencia", "historial": "experiencia",
    "formacion": "educacion", "educacion": "educacion", "estudios": "educacion",
    "habilidades": "habilidades", "herramientas": "habilidades", "competencias": "habilidades",
    "conocimientos": "habilidades", "skills": "habilidades",
    "certificaciones": "certificaciones", "certificados": "certificaciones",
    "cursos": "cursos", "proyectos": "proyectos",
    "liderazgo": "actividades", "actividades": "actividades", "logros": "actividades", "premios": "actividades",
    "idiomas": "idiomas", "perfil": "perfil", "resumen": "perfil",
}


def es_titulo_seccion(linea: str):
    """Devuelve (clave, estandar:bool) o None."""
    limpio = RE_ICONO_INICIO.sub("", linea)
    l = norm(limpio).rstrip(":")
    if not l or len(l) > 60:
        return None
    for clave, sinonimos in SECCIONES.items():
        if l in sinonimos:
            return clave, limpio == linea.strip() or not RE_ICONO_INICIO.match(linea)
    if RE_RANGO.search(limpio) or limpio.rstrip().endswith((".", ",", ";")) or RE_BULLET.match(limpio):
        return None
    primera = l.split()[0] if l.split() else ""
    if primera in PREFIJOS_NO_ESTANDAR and len(l.split()) <= 8 and limpio.strip()[:1].isupper():
        # Variante no estándar ("Experiencia en Mantenimiento de Campo"): el ATS puede no reconocerla.
        return PREFIJOS_NO_ESTANDAR[primera], False
    return None


def segmentar(cv: CV):
    lineas = [l.rstrip() for l in cv.texto.replace("\f", "\n").split("\n")]
    cv.lineas = [l for l in lineas if l.strip()]
    actual = "_encabezado"
    secs = {actual: []}
    cv.titulos_no_estandar = []
    for l in cv.lineas:
        r = es_titulo_seccion(l)
        if r:
            actual, estandar = r
            if not estandar:
                cv.titulos_no_estandar.append(l.strip())
            secs.setdefault(actual, [])
            continue
        secs.setdefault(actual, []).append(l)
    cv.encabezado = secs.pop("_encabezado", [])
    cv.secciones = secs
    # Viñetas: une las líneas de continuación con la viñeta que las inicia.
    for clave, ls in secs.items():
        vs, cur = [], None
        for l in ls:
            m = RE_BULLET.match(l)
            st = l.strip()
            if m:
                if cur:
                    vs.append(cur)
                cur = m.group(2).strip()
            elif cur is not None and not RE_RANGO.search(st) and (
                    st[:1].islower() or st[:1] in "(\"'" or not cur.rstrip().endswith((".", ":", ";"))):
                cur += " " + st
            else:
                if cur:
                    vs.append(cur)
                cur = None
        if cur:
            vs.append(cur)
        cv.vinetas[clave] = vs


# ----------------------------------------------------------------------------
# Chequeos
# ----------------------------------------------------------------------------

def ck_parse(cv: CV, a) -> list:
    out = []
    t = cv.texto
    n = len(t.strip())
    raros = sum(1 for c in t if c == "\ufffd" or 0xE000 <= ord(c) <= 0xF8FF)
    ligaduras = len(re.findall("[\ufb00-\ufb06]", t))
    tildes_rotas = len(re.findall(r"[´`¨]\s?[aeiouAEIOU]|[aeiouAEIOU]\s[´`]", t))
    problemas = []
    if n < 400:
        problemas.append(f"Solo se extrajeron {n} caracteres: el PDF podría ser una imagen o estar protegido.")
    if raros:
        problemas.append(f"{raros} caracteres ilegibles (íconos o fuentes sin Unicode).")
    if ligaduras:
        problemas.append(f"{ligaduras} ligaduras (ﬁ/ﬂ): usa \\pdfgentounicode=1 o desactiva ligaduras.")
    if tildes_rotas:
        problemas.append(f"{tildes_rotas} tildes separadas de su letra: el ATS no reconocerá esas palabras.")
    permitidos = set("|•–—-·/&%:+=yaoeuYAOEU")
    iconos = [t for t in re.findall(r"(?:(?<=\s)|^)(\S)(?=\s)", t, re.M)
              if t not in permitidos and not t.isdigit() and not t.isalpha()]
    iconos += re.findall(r"(?:(?<=\s)|^)([ïÔÕ¢²³¹ºª§¤¥])(?=\s)", t, re.M)
    if iconos:
        problemas.append(f"{len(iconos)} íconos/símbolos convertidos en basura ({' '.join(sorted(set(iconos)))[:40]}): "
                         "el ATS los lee como texto y pueden romper teléfono, correo o títulos.")
    cortes = re.findall(r"[a-záéíóúñ]{2,}-\n[a-záéíóúñ]", cv.texto_layout + "\n" + t)
    if cortes:
        problemas.append(f"{len(cortes)} palabras partidas con guion al final de línea: el ATS no las encuentra "
                         "como palabra clave (desactiva la división silábica).")
    malos = raros + ligaduras + tildes_rotas + len(iconos) + 2 * len(cortes)
    puntaje = 0.0 if n < 400 else max(0.0, 1 - malos / 20)
    out.append(Resultado("Contenido", "Lectura por ATS (parse)", puntaje, 2, duro=n < 400,
                         aprobado=puntaje >= 0.9, problemas=problemas,
                         sugerencia="PDF de texto real, una columna, sin íconos; compila con \\pdfgentounicode=1."))

    # Fechas separadas del cargo (efecto de minipages/columnas): el ATS pierde la relación cargo-fecha.
    lay = [l for l in cv.texto_layout.split("\n") if l.strip()]
    sueltas = [l for l in lay if RE_RANGO.fullmatch(l.strip())]
    con_texto = [l for l in lay if RE_RANGO.search(l) and not RE_RANGO.fullmatch(l.strip())]
    total = len(sueltas) + len(con_texto)
    if total:
        p = len(con_texto) / total
        out.append(Resultado("ATS", "Fechas unidas al cargo/título", p, 1.5, aprobado=p >= 0.8,
                             problemas=[f"{len(sueltas)} de {total} rangos de fechas están en una línea aparte del cargo "
                                        "(el ATS puede asignarlos al empleo equivocado)."] if sueltas else [],
                             sugerencia="Pon la fecha en la MISMA línea que el cargo con \\hfill, sin minipages ni tablas."))
    return out


def ck_columnas(cv: CV, a) -> list:
    # Heurística: líneas del layout con dos bloques de texto separados por >=8 espacios,
    # donde el bloque derecho NO es una fecha/lugar corto.
    sospechosas = 0
    total = 0
    for l in cv.texto_layout.split("\n"):
        if not l.strip():
            continue
        total += 1
        partes = [p for p in re.split(r"\s{8,}", l.strip()) if p]
        if len(partes) >= 2:
            der = partes[-1]
            if RE_RANGO.search(der) or len(der) <= 30:
                continue
            sospechosas += 1
    ratio = sospechosas / total if total else 0
    p = 1.0 if ratio < 0.05 else max(0.0, 1 - ratio * 4)
    return [Resultado("ATS", "Una sola columna / sin tablas", p, 2, duro=ratio > 0.25, aprobado=ratio < 0.05,
                      problemas=[f"{sospechosas} líneas parecen tener texto en paralelo (columnas o tablas)."]
                      if ratio >= 0.05 else [],
                      sugerencia="Usa diseño de una columna; Workday y Taleo mezclan el texto de columnas y tablas.")]


def ck_formato_archivo(cv: CV, a) -> list:
    out = []
    mb = cv.bytes / 1024 / 1024
    out.append(Resultado("ATS", "Formato y tamaño", 1.0 if mb < 2 else 0.0, 1, duro=mb >= 2, aprobado=mb < 2,
                         problemas=[] if mb < 2 else [f"Pesa {mb:.1f} MB (límite habitual 2 MB)."],
                         sugerencia="Comprime imágenes o quita la foto."))
    maxp = a.max_paginas or (1 if a.estricto else 2)
    if cv.paginas <= maxp:
        p = 1.0
    elif cv.paginas == maxp + 1 and maxp >= 2:
        p = 0.6
    elif cv.paginas == 2:
        p = 0.6
    else:
        p = 0.2
    out.append(Resultado("ATS", "Extensión", p, 1.5, duro=cv.paginas > max(2, maxp), aprobado=cv.paginas <= maxp,
                         problemas=[] if cv.paginas <= maxp else [f"Tiene {cv.paginas} páginas (máximo {maxp}). "
                                                                   "El 17 % de los reclutadores descarta CVs de más de 2 páginas."],
                         sugerencia="Ajusta fuente/márgenes y recorta lo menos afín al puesto."))
    nombre = cv.ruta.stem
    ok = bool(re.fullmatch(r"[A-Za-z]+(_[A-Za-z]+)+", sin_tildes(nombre))) and "cv" in nombre.lower()
    out.append(Resultado("ATS", "Nombre del archivo", 1.0 if ok else 0.5, 0.5, aprobado=ok,
                         problemas=[] if ok else [f"'{cv.ruta.name}' no sigue Nombre_Apellido_CV_Puesto.pdf."],
                         sugerencia="Renombra a Nombre_Apellido_CV_Puesto.pdf (sin espacios ni tildes)."))
    return out


def ck_foto(cv: CV, a) -> list:
    hay = cv.imagenes > 0
    return [Resultado("Riesgos RR.HH.", "Sin foto ni imágenes", 0.3 if hay else 1.0, 1.5, aprobado=not hay,
                      problemas=[f"El PDF contiene {cv.imagenes} imagen(es) (foto/íconos). Penaliza en ATS y en sesgo."]
                      if hay else [],
                      sugerencia="Quita la foto salvo que la vacante la exija; genera una versión sin foto para portales.")]


def ck_contacto(cv: CV, a) -> list:
    cab = "\n".join(cv.encabezado[:8]) or "\n".join(cv.lineas[:6])
    todo = cv.texto
    problemas = []
    email = RE_EMAIL.search(todo)
    tel = RE_TEL.search(cab)
    lk = RE_LINKEDIN.search(todo) or any("linkedin" in e for e in cv.enlaces)
    if not email:
        problemas.append("Falta correo electrónico.")
    if not tel:
        problemas.append("Falta teléfono en el encabezado.")
    if not lk:
        problemas.append("Falta LinkedIn (linkedin.com/in/usuario).")
    if email and not RE_EMAIL.search(cab):
        problemas.append("El correo no está en las primeras líneas (puede estar en encabezado/pie que el ATS ignora).")
    p = 1 - 0.3 * len(problemas)
    out = [Resultado("Secciones", "Datos de contacto", max(0, p), 1, duro=not (email and tel), aprobado=not problemas,
                     problemas=problemas, sugerencia="Nombre, ciudad, teléfono, correo y LinkedIn en el cuerpo, arriba.")]
    if email:
        e = email.group(0).lower()
        local = e.split("@")[0]
        malos = []
        if re.search(r"\d{3,}", local):
            malos.append("tiene una serie de números")
        if re.search(r"(sexy|love|bebe|nene|crazy|loco|gamer|xx|kiss|angel|princes|diabl|hot)", local):
            malos.append("contiene un apodo poco profesional")
        if not re.search(r"(gmail|outlook|hotmail|yahoo|icloud|proton|live)\.", e) and not re.search(r"\.(pe|edu|com|org)", e):
            malos.append("dominio poco común")
        p = 1.0 if not malos else (0.4 if "apodo" in " ".join(malos) else 0.75)
        out.append(Resultado("Riesgos RR.HH.", "Correo profesional", p, 0.5, aprobado=not malos,
                             problemas=[f"'{e}' {', '.join(malos)}. El 35 % de los reclutadores lo considera descalificante."]
                             if malos else [],
                             sugerencia="Usa nombre.apellido@… sin números ni apodos."))
    if lk and not cv.enlaces:
        out.append(Resultado("ATS", "Enlaces clicables", 0.6, 0.3, aprobado=False,
                             problemas=["LinkedIn aparece como texto pero no es un enlace clicable."],
                             sugerencia="Usa \\href{https://linkedin.com/in/usuario}{…}."))
    return out


def ck_secciones(cv: CV, a) -> list:
    ess = ["perfil", "experiencia", "educacion", "habilidades"]
    faltan = [s for s in ess if s not in cv.secciones]
    p = 1 - len(faltan) / len(ess)
    out = []
    if cv.titulos_no_estandar:
        out.append(Resultado("Secciones", "Títulos de sección estándar", max(0.3, 1 - 0.15 * len(cv.titulos_no_estandar)),
                             1, aprobado=False,
                             problemas=["Títulos no estándar o con íconos: " + "; ".join(cv.titulos_no_estandar[:6])],
                             sugerencia="Usa exactamente: Perfil Profesional, Experiencia Laboral, Educación, "
                                        "Habilidades, Certificaciones, Proyectos, Idiomas."))
    out += [Resultado("Secciones", "Secciones esenciales", p, 1.5, duro=("experiencia" in faltan and "proyectos" not in cv.secciones)
                     or "educacion" in faltan, aprobado=not faltan,
                     problemas=[f"No se reconoce la sección: {', '.join(faltan)}. Usa títulos estándar."] if faltan else [],
                     sugerencia="Títulos estándar: Perfil Profesional, Experiencia Laboral, Educación, Habilidades.")]
    return out


def _todas_vinetas(cv: CV, solo=None):
    res = []
    for k, vs in cv.vinetas.items():
        if solo and k not in solo:
            continue
        res.extend(vs)
    return res


def ck_cuantificacion(cv: CV, a) -> list:
    exp = _todas_vinetas(cv, ["experiencia"])
    todas = _todas_vinetas(cv, ["experiencia", "proyectos", "actividades"])
    if not exp:
        return [Resultado("Contenido", "Impacto cuantificado", 0.0, 3, aprobado=False,
                          problemas=["No se detectaron viñetas en Experiencia."],
                          sugerencia="Usa viñetas: verbo + tarea + herramienta + resultado con cifra.")]

    def tiene(v):
        v2 = re.sub(r"\b(19|20)\d{2}\b", "", v)          # años no cuentan como cifra
        v2 = re.sub(r"\b[A-Z]{2,}\d+\b|\b\d+[A-Z]\b|\bCAT\d\b|\bS\d\b|\b\dD\b", "", v2)  # modelos (CAT6, S8, 3D)
        return bool(RE_CIFRA.search(v2))

    sin = [v for v in exp if not tiene(v)]
    r_exp = 1 - len(sin) / len(exp)
    r_all = sum(tiene(v) for v in todas) / len(todas) if todas else r_exp
    meta = 0.6 if a.estricto else 0.5
    p = min(1.0, (0.7 * r_exp + 0.3 * r_all) / meta)
    probs = [f"{len(sin)} de {len(exp)} viñetas de experiencia no tienen cifras (34 % de reclutadores lo descarta)."] if sin else []
    probs += [f"  · «{v[:90]}…»" for v in sin[:4]]
    return [Resultado("Contenido", "Impacto cuantificado", p, 3, aprobado=r_exp >= meta, problemas=probs,
                      sugerencia="Añade cifras REALES: cantidad (equipos, usuarios, marcas), tiempo, %, premios, personas.")]


def ck_verbos(cv: CV, a) -> list:
    vs = _todas_vinetas(cv, ["experiencia", "proyectos", "actividades"])
    if not vs:
        return []
    primeras = [norm(v.split()[0]).strip(".,:;") for v in vs if v.split()]
    accion = [p for p in primeras if p in VERBOS_ACCION or re.fullmatch(r"[a-z]+(e|i)$", p) and len(p) > 4]
    debiles = [v for v in vs if any(norm(v).startswith(d) for d in INICIOS_DEBILES)]
    cnt = Counter(accion)
    repetidos = {k: c for k, c in cnt.items() if c > 2}
    p_acc = len(accion) / len(primeras)
    p = max(0.0, p_acc - 0.1 * len(debiles) - 0.1 * len(repetidos))
    probs = []
    if p_acc < 0.8:
        probs.append(f"Solo {len(accion)} de {len(primeras)} viñetas empiezan con verbo de acción en pasado.")
    if debiles:
        probs.append(f"{len(debiles)} viñetas empiezan con fórmula débil (\"Responsable de\", \"Apoyo en\"…).")
    if repetidos:
        probs.append("Verbos repetidos más de 2 veces: " + ", ".join(f"{k} ×{c}" for k, c in repetidos.items()))
    # Tiempo verbal mezclado (pasado vs presente) dentro de experiencia
    exp = _todas_vinetas(cv, ["experiencia"])
    pres = [v for v in exp if v.split() and re.fullmatch(r"[a-záéíóú]+(o|a)$", v.split()[0].lower()) and
            norm(v.split()[0]) not in VERBOS_ACCION]
    if exp and pres and len(pres) < len(exp):
        probs.append(f"{len(pres)} viñetas de experiencia en presente y el resto en pasado: unifica el tiempo verbal.")
        p -= 0.1
    return [Resultado("Contenido", "Verbos de acción y repetición", max(0, p), 1.5, aprobado=not probs, problemas=probs,
                      sugerencia="Empieza cada viñeta con un verbo distinto en pasado (diseñé, reduje, implementé…).")]


def ck_repeticion(cv: CV, a) -> list:
    cuerpo = " ".join(_todas_vinetas(cv) + cv.secciones.get("perfil", []))
    palabras = [w for w in re.findall(r"[a-záéíóúñü]{5,}", cuerpo.lower()) if norm(w) not in STOPWORDS]
    cnt = Counter(norm(w) for w in palabras)
    limite = max(3 if a.estricto else 4, len(palabras) // (180 if a.estricto else 140))
    rep = [(w, c) for w, c in cnt.most_common(15) if c > limite]
    p = max(0.0, 1 - 0.12 * len(rep))
    return [Resultado("Contenido", "Repetición de palabras", p, 1, aprobado=not rep,
                      problemas=["Palabras muy repetidas: " + ", ".join(f"{w} ×{c}" for w, c in rep)] if rep else [],
                      sugerencia="Usa sinónimos o fusiona viñetas que dicen lo mismo.")]


def ck_vinetas_forma(cv: CV, a) -> list:
    vs = _todas_vinetas(cv)
    if not vs:
        return []
    largas = [v for v in vs if len(v) > (180 if a.estricto else 230)]
    finales = Counter("punto" if v.rstrip().endswith(".") else "sin punto" for v in vs)
    probs = []
    if largas:
        probs.append(f"{len(largas)} viñetas superan ~2 líneas (25 % de reclutadores rechaza bloques largos).")
    if len(finales) > 1 and min(finales.values()) / len(vs) > 0.1:
        probs.append(f"Puntuación final inconsistente: {dict(finales)}.")
    parrafos = [l for l in cv.secciones.get("perfil", [])]
    if len(" ".join(parrafos)) > 600:
        probs.append("El perfil supera ~5 líneas: redúcelo a 3–4.")
    p = max(0.0, 1 - 0.15 * len(largas) - (0.2 if len(probs) > len(largas and [1]) else 0))
    return [Resultado("Contenido", "Consistencia y longitud de viñetas", p, 1, aprobado=not probs, problemas=probs,
                      sugerencia="Viñetas de 1–2 líneas, todas con (o sin) punto final.")]


def ck_fechas(cv: CV, a) -> list:
    estilos = Counter()
    meses = Counter()
    for m in RE_RANGO.finditer(cv.texto):
        for parte in (m.group(1), m.group(2)):
            s = parte.strip().lower()
            if re.fullmatch(r"\d{1,2}/\d{4}", s):
                estilos["MM/AAAA"] += 1
            elif re.fullmatch(r"\d{4}", s):
                estilos["AAAA"] += 1
            elif re.match(r"\d{1,2}\s", s):
                estilos["DD Mes AAAA"] += 1
            elif re.search(RE_MES, s):
                tok = re.match(r"[a-z]+\.?", s).group(0)
                estilos["Mes abreviado" if len(tok.rstrip(".")) <= 4 else "Mes completo"] += 1
                meses[tok.rstrip(".")[:3] if tok.rstrip(".")[:3] not in ("set", "sep") else tok.rstrip(".")] += 1
    probs = []
    if len(estilos) > 1:
        probs.append("Formatos de fecha mezclados: " + ", ".join(f"{k} ×{v}" for k, v in estilos.items()))
    if meses.get("set") and meses.get("sep"):
        probs.append("Se usan 'Set.' y 'Sep.' a la vez.")
    p = 1.0 if not probs else max(0.3, 1 - 0.2 * (len(estilos) - 1))
    return [Resultado("ATS", "Formato de fechas consistente", p, 1, aprobado=not probs, problemas=probs,
                      sugerencia="Un solo formato (p. ej. 'Ene. 2026 – Mar. 2026') en todo el CV.")]


def ck_sensibles(cv: CV, a) -> list:
    t = norm(cv.texto)
    hall = [k for k, rx in DATOS_SENSIBLES.items() if re.search(rx, t)]
    return [Resultado("Riesgos RR.HH.", "Sin datos personales sensibles", 0.0 if hall else 1.0, 1, aprobado=not hall,
                      problemas=[f"Aparece: {', '.join(hall)}. Genera sesgo y no lo pide un CV."] if hall else [],
                      sugerencia="Quita DNI, edad, estado civil, nacionalidad, religión, salud.")]


def ck_credibilidad(cv: CV, a) -> list:
    t = norm(cv.texto)
    cl = [c for c in CLICHES if c in t]
    ia = [r for r in RESIDUOS_IA if re.search(r, t)]
    pron = re.findall(r"(?:^|[.;]\s|\n[•\-–]\s)(yo|mi|me)\s", cv.texto.lower())
    probs = []
    if cl:
        probs.append("Clichés sin evidencia: " + ", ".join(cl))
    if ia:
        probs.append("Texto de plantilla/IA sin reemplazar: " + ", ".join(ia))
    if pron:
        probs.append(f"{len(pron)} frases en primera persona explícita (yo/mi).")
    p = max(0.0, 1 - 0.15 * len(cl) - 0.1 * len(pron)) if not ia else 0.0
    return [Resultado("Riesgos RR.HH.", "Credibilidad (clichés, residuos de IA)", p, 1, duro=bool(ia), aprobado=not probs,
                      problemas=probs, sugerencia="Reemplaza adjetivos por hechos con cifra; elimina texto de plantilla.")]


# Reglas de LanguageTool que no aplican al estilo de un CV (encabezados de fecha, títulos, siglas).
REGLAS_IGNORADAS = {"WHITESPACE_RULE", "UPPERCASE_SENTENCE_START", "COMMA_PARENTHESIS_WHITESPACE", "MIN_MESES",
                    "MIN_DIAS", "ES_UNPAIRED_BRACKETS", "UNPAIRED_BRACKETS", "PUNTO_EN_ABREVIATURAS",
                    "ES_QUESTION_MARK", "DOUBLE_PUNCTUATION", "ES_SIMPLE_REPLACE_SIMPLE_MAYUSCULAS",
                    "PREP_VERB"}


def cargar_diccionarios(a) -> set:
    """Términos válidos: diccionario técnico incluido + diccionario del usuario + inglés (hunspell si existe)."""
    palabras = set()
    rutas = [Path(__file__).with_name("diccionario_tecnico.txt")]
    if a.diccionario:
        rutas.append(Path(a.diccionario))
    for r in rutas:
        if r.exists():
            for l in r.read_text(encoding="utf-8").splitlines():
                l = l.split("#")[0]
                palabras.update(norm(w) for w in l.split())
    for d in [Path(__file__).with_name("en_US.dic"), Path("/usr/share/hunspell/en_US.dic"),
              Path("/usr/share/myspell/en_US.dic")]:
        if d.exists():
            for l in d.read_text(encoding="latin-1", errors="ignore").splitlines()[1:]:
                w = l.split("/")[0].strip()
                if w and w.islower():
                    palabras.add(w)
                    palabras.add(w + "s")
            break
    return palabras


def ck_ortografia(cv: CV, a) -> list:
    if a.sin_ortografia:
        return []
    try:
        import language_tool_python as lt
    except ImportError:
        return [Resultado("Contenido", "Ortografía y gramática", 0.8, 2, aprobado=False,
                          problemas=["No verificado: instala language-tool-python y Java para revisar en español."],
                          sugerencia="pip install language-tool-python  (requiere Java 17+).")]
    extra = cargar_diccionarios(a)
    try:
        tool = lt.LanguageTool(a.idioma)
        texto = "\n".join(cv.lineas)
        matches = tool.check(texto)
        tool.close()
    except Exception as e:
        return [Resultado("Contenido", "Ortografía y gramática", 0.8, 2, aprobado=False,
                          problemas=[f"No se pudo ejecutar LanguageTool: {e}"])]
    errores = []
    for m in matches:
        palabra = texto[m.offset:m.offset + m.error_length]
        rid = getattr(m, "rule_id", "") or getattr(m, "ruleId", "")
        cat = str(getattr(m, "category", ""))
        if cat in ("TYPOGRAPHY", "STYLE", "REDUNDANCY") or rid in REGLAS_IGNORADAS:
            continue
        # Nombres propios, siglas, marcas y términos técnicos: no son errores.
        if (palabra[:1].isupper() or re.search(r"\d|[A-Z]{2}", palabra) or norm(palabra) in extra
                or re.search(r"[a-z][A-Z]", palabra)) and cat == "TYPOS":
            continue
        errores.append((palabra, m.replacements[:2], rid))
    n = len(errores)
    p = 1.0 if n == 0 else max(0.0, 1 - 0.12 * n)
    probs = [f"{n} posibles errores (77 % de reclutadores descarta por errores ortográficos):"] if n else []
    probs += [f"  · «{w}» → {', '.join(r) or '?'}  [{rid}]" for w, r, rid in errores[:12]]
    return [Resultado("Contenido", "Ortografía y gramática", p, 2, duro=a.estricto and n > 3, aprobado=n == 0,
                      problemas=probs,
                      sugerencia="Corrige; si es un término técnico válido, agrégalo al diccionario (--diccionario).")]


# --- Adaptación a la vacante (núcleo mínimo; ampliable con plugins) ----------

def _terminos_vacante(texto: str):
    terminos = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9+#./-]{1,}(?:\s[A-Z][A-Za-z0-9+#./-]+){0,3})\b", texto):
        t = m.group(1).strip()
        if norm(t) not in STOPWORDS and len(t) > 1:
            terminos.add(t)
    for m in re.finditer(r"\b[A-Z]{2,}[0-9]*\b", texto):
        terminos.add(m.group(0))
    palabras = [w for w in re.findall(r"[a-záéíóúñ]{5,}", texto.lower()) if norm(w) not in STOPWORDS]
    for w, c in Counter(palabras).most_common(25):
        if c >= 2:
            terminos.add(w)
    return sorted(terminos, key=str.lower)


def ck_adaptacion(cv: CV, a) -> list:
    out = []
    t = norm(cv.texto)
    if a.excluyentes:
        req = [r.strip() for r in a.excluyentes.split(",") if r.strip()]
        faltan = [r for r in req if norm(r) not in t]
        out.append(Resultado("Adaptación", "Requisitos excluyentes (coincidencia exacta)",
                             1 - len(faltan) / len(req), 3, duro=bool(faltan), aprobado=not faltan,
                             problemas=[f"No aparecen literalmente: {', '.join(faltan)}. Workday/Taleo buscan por "
                                        "palabra exacta, no por sinónimo."] if faltan else [],
                             sugerencia="Si de verdad lo cumples, escribe el término EXACTO del aviso (y su sigla)."))
    if a.vacante:
        av = Path(a.vacante).read_text(encoding="utf-8", errors="replace")
        terms = _terminos_vacante(av)
        presentes = [x for x in terms if norm(x) in t]
        cob = len(presentes) / len(terms) if terms else 1
        meta = 0.75 if a.estricto else 0.6
        out.append(Resultado("Adaptación", "Palabras clave del aviso", min(1, cob / meta), 2, aprobado=cob >= meta,
                             problemas=[f"Cobertura {cob:.0%} (meta {meta:.0%}). Faltan: " +
                                        ", ".join([x for x in terms if x not in presentes][:25])] if cob < meta else [],
                             sugerencia="Incluye SOLO las que cumples, con la misma grafía del aviso, en Perfil/Experiencia/Habilidades."))
    if a.puesto:
        cab = norm(" ".join(cv.encabezado[:4]))
        claves = [w for w in norm(a.puesto).split() if w not in STOPWORDS and len(w) > 3]
        hit = sum(w in cab for w in claves) / len(claves) if claves else 1
        out.append(Resultado("Adaptación", "Título adaptado bajo el nombre", hit, 1, aprobado=hit >= 0.5,
                             problemas=[] if hit >= 0.5 else [f"El encabezado no menciona el puesto «{a.puesto}»."],
                             sugerencia="Agrega una línea bajo el nombre con el título del puesto al que postulas."))
    return out


PALABRAS_IA = ["orquest", "dinamic", "sinergi", "vanguardia", "holistic", "robusto", "robusta", "meticulos",
               "apasionad", "transformador", "transformadora", "potencie", "potencié", "impulse la", "impulsé la",
               "ecosistema de", "en el ambito de", "de manera integral", "de forma integral", "altamente motivad",
               "en constante evolucion", "aportar valor", "valor agregado", "desempeñe un papel", "jugue un papel"]


def ck_senales_ia(cv: CV, a) -> list:
    """Señales de texto genérico de IA (los reclutadores y algunos escáneres lo penalizan)."""
    t = norm(" ".join(_todas_vinetas(cv) + cv.secciones.get("perfil", [])))
    hall = sorted({w for w in PALABRAS_IA if norm(w) in t})
    vs = _todas_vinetas(cv, ["experiencia", "proyectos", "actividades"])
    simetria = False
    if len(vs) >= 5:
        largos = [len(v) for v in vs]
        prom = sum(largos) / len(largos)
        simetria = max(largos) - min(largos) < 0.15 * prom  # viñetas casi idénticas en longitud
    probs = []
    if hall:
        probs.append("Vocabulario típico de texto generado por IA: " + ", ".join(hall))
    if simetria:
        probs.append("Todas las viñetas tienen casi la misma longitud (patrón artificial).")
    p = max(0.0, 1 - 0.15 * len(hall) - (0.2 if simetria else 0))
    return [Resultado("Riesgos RR.HH.", "Señales de texto genérico/IA", p, 1, aprobado=not probs, problemas=probs,
                      sugerencia="Reescribe con hechos concretos y cifras; evita adjetivos grandilocuentes.")]


RE_ESTADO_ACADEMICO = re.compile(
    r"(\b\d{1,2}\s*(?:°|º|vo|mo|no|er|ro|to)?\s*ciclo\b|\b(?:primer|segundo|tercer|cuarto|quinto|sexto|septimo|setimo|octavo|"
    r"noveno|decimo|undecimo|duodecimo)\s+ciclo\b|\begresad[oa]\b|\bbachiller\b|\btitulad[oa]\b|\bcolegiad[oa]\b|"
    r"\bcip\s*(?:n[°ºo.]*)?\s*\d+|\b\d{1,2}\s*(?:°|º)?\s*semestre\b|\bultimo ano\b|\bultimos ciclos\b)",
    re.I,
)


def ck_estado_academico(cv: CV, a) -> list:
    """Perú (Ley 28518): el reclutador necesita saber si es estudiante (y de qué ciclo) o egresado/bachiller,
    porque define si aplica prácticas preprofesionales o profesionales. Su ausencia es un filtro eliminatorio."""
    if a.region != "pe":
        return []
    ok = bool(RE_ESTADO_ACADEMICO.search(norm(cv.texto)))
    return [Resultado("Secciones", "Estado académico declarado (ciclo / egresado / bachiller)", 1.0 if ok else 0.0,
                      1.5, duro=not ok and a.practicas, aprobado=ok,
                      problemas=[] if ok else ["No se indica el ciclo ni la condición de egresado/bachiller. En Perú "
                                               "define la modalidad formativa (Ley 28518) y suele ser pregunta eliminatoria."],
                      sugerencia="Escribe p. ej. 'Estudiante de 10.º ciclo de Ingeniería …' o 'Egresado / Bachiller en …'.")]


def ck_fechas_ambiguas(cv: CV, a) -> list:
    solo_anios = []
    for m in re.finditer(r"(?<![/\w])((?:19|20)\d{2})\s*[–—-]\s*((?:\w+\.?\s+)?(?:19|20)\d{2}|presente|actualidad)\b",
                         cv.texto, re.I):
        antes = cv.texto[max(0, m.start() - 12):m.start()].lower()
        if re.search(RE_MES + r"\s*$", antes) or re.search(r"[a-z]", m.group(2).split()[0].lower()) and \
                re.match(RE_MES, m.group(2).lower()):
            continue  # "Julio 2025 – Actualidad" o "2024 – Mar. 2025": tiene mes
        solo_anios.append((m.group(1), m.group(2)))
    apostrofes = re.findall(r"[A-Za-z]{3,}\.?\s*['’]\d{2}\b", cv.texto)
    probs = []
    if solo_anios:
        probs.append(f"{len(solo_anios)} rangos solo con años (p. ej. {'–'.join(solo_anios[0])}): el ATS no puede calcular la duración.")
    if apostrofes:
        probs.append(f"Fechas con apóstrofe ({apostrofes[0]}): muchos ATS no las entienden.")
    if not probs:
        return []
    return [Resultado("ATS", "Fechas con mes y año", max(0.3, 1 - 0.2 * (len(solo_anios) + len(apostrofes))), 1,
                      aprobado=False, problemas=probs, sugerencia="Usa mes y año en todas: 'Mar. 2023 – Dic. 2023'.")]


CHEQUEOS = [ck_parse, ck_columnas, ck_formato_archivo, ck_foto, ck_contacto, ck_secciones, ck_cuantificacion,
            ck_verbos, ck_repeticion, ck_vinetas_forma, ck_fechas, ck_sensibles, ck_credibilidad, ck_ortografia,
            ck_adaptacion, ck_senales_ia, ck_estado_academico, ck_fechas_ambiguas]

# ----------------------------------------------------------------------------
# Plugins
# ----------------------------------------------------------------------------

def cargar_plugins(rutas):
    funcs = []
    for r in rutas:
        p = Path(r)
        archivos = sorted(p.glob("*.py")) if p.is_dir() else [p]
        for f in archivos:
            if f.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(f"plugin_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, "check"):
                    funcs.append(mod.check)
            except Exception as e:
                print(f"[aviso] plugin {f.name} no cargó: {e}", file=sys.stderr)
    return funcs

# ----------------------------------------------------------------------------
# Puntaje y reporte
# ----------------------------------------------------------------------------

def puntuar(resultados, a):
    por_cat = {}
    for r in resultados:
        por_cat.setdefault(r.categoria, []).append(r)
    cats = {}
    for c, rs in por_cat.items():
        w = sum(r.peso for r in rs)
        cats[c] = sum(r.puntaje * r.peso for r in rs) / w if w else 1
    pesos = {c: PESOS_CATEGORIA.get(c, 10) for c in cats}
    total = sum(cats[c] * pesos[c] for c in cats) / sum(pesos.values()) * 100
    duros = [r for r in resultados if r.duro and not r.aprobado]
    if duros:
        total = min(total, 69.0)
    umbral = a.umbral
    aprobado = total > umbral and not duros
    return round(total, 1), {c: round(v * 100) for c, v in cats.items()}, duros, aprobado


def reporte_texto(cv, resultados, total, cats, duros, aprobado, a):
    L = []
    L.append(f"CV CHECKER v{VERSION} — {cv.ruta.name}  ({cv.paginas} pág., {cv.bytes/1024:.0f} KB)"
             f"  modo {'ESTRICTO' if a.estricto else 'normal'}")
    L.append("=" * 78)
    L.append(f"PUNTAJE: {total}/100   →   {'APROBADO' if aprobado else 'NO APROBADO'} (umbral > {a.umbral}"
             f"{', sin filtros eliminatorios' if True else ''})")
    L.append("")
    for c, v in cats.items():
        L.append(f"  {c:<18} {v:>3}%  " + "█" * (v // 5))
    if duros:
        L.append("")
        L.append("FILTROS ELIMINATORIOS FALLADOS (tope 69/100):")
        for r in duros:
            L.append(f"  ✖ [{r.categoria}] {r.nombre}")
    L.append("")
    L.append("DETALLE (lo peor primero):")
    for r in sorted(resultados, key=lambda r: (r.aprobado, r.puntaje)):
        marca = "✔" if r.aprobado else ("✖" if r.duro else "!")
        L.append(f" {marca} [{r.categoria}] {r.nombre}: {r.puntaje*100:.0f}%")
        if not r.aprobado:
            for p in r.problemas:
                L.append(f"     {p}")
            if r.sugerencia:
                L.append(f"     → {r.sugerencia}")
    if not any(r.categoria == "Adaptación" for r in resultados):
        L.append("")
        L.append("Adaptación: no evaluada (usa --vacante aviso.txt, --excluyentes y --puesto).")
    L.append("")
    L.append("Nota: aproximación local. Validación final: Enhancv con 0 problemas en las subcategorías desbloqueadas.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verificador local de CVs (ATS + reclutador estricto).")
    ap.add_argument("pdf")
    ap.add_argument("--vacante", help="archivo .txt con el aviso de trabajo")
    ap.add_argument("--excluyentes", help="requisitos excluyentes separados por coma (coincidencia exacta)")
    ap.add_argument("--puesto", help="título del puesto al que se postula")
    ap.add_argument("--estricto", action="store_true", help="umbrales duros de reclutador exigente")
    ap.add_argument("--umbral", type=float, default=90.0)
    ap.add_argument("--max-paginas", type=int, help="páginas permitidas (por defecto 2; 1 en --estricto; 3 para un CV maestro)")
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--practicas", action="store_true",
                    help="la vacante es de prácticas (pre)profesionales: el estado académico pasa a ser eliminatorio")
    ap.add_argument("--region", default="pe", help="pe = reglas de Perú (estado académico, Ley 28518); otro = sin ellas")
    ap.add_argument("--diccionario", help="archivo con términos válidos (marcas, siglas, software)")
    ap.add_argument("--sin-ortografia", action="store_true")
    ap.add_argument("--plugin", action="append", default=[], help="archivo .py o carpeta con plugins")
    ap.add_argument("--json", help="guardar reporte en JSON")
    a = ap.parse_args(argv)

    ruta = Path(a.pdf)
    if not ruta.exists():
        print(f"No existe: {ruta}", file=sys.stderr)
        return 2
    cv = leer_pdf(ruta)
    resultados = []
    plug_dir = Path(__file__).with_name("plugins")
    funcs = CHEQUEOS + cargar_plugins(([str(plug_dir)] if plug_dir.exists() else []) + a.plugin)
    for f in funcs:
        try:
            resultados.extend(f(cv, a) or [])
        except Exception as e:
            print(f"[aviso] {getattr(f, '__name__', f)} falló: {e}", file=sys.stderr)
    total, cats, duros, aprobado = puntuar(resultados, a)
    print(reporte_texto(cv, resultados, total, cats, duros, aprobado, a))
    if a.json:
        Path(a.json).write_text(json.dumps({
            "archivo": cv.ruta.name, "puntaje": total, "aprobado": aprobado, "categorias": cats,
            "eliminatorios": [r.nombre for r in duros], "resultados": [asdict(r) for r in resultados],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if aprobado else 1


if __name__ == "__main__":
    sys.exit(main())
