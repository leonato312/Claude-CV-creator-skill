# -*- coding: utf-8 -*-
"""
Plantilla de plugin para cv_checker.py

Cómo usarla:
  1. Copia este archivo dentro de la carpeta plugins/ con un nombre que NO empiece por "_"
     (los archivos que empiezan por "_" se ignoran). Ejemplo: plugins/adaptacion_vacante.py
  2. Implementa check(cv, args) y devuelve una lista de Resultado.
  3. Ejecuta:  python cv_checker.py CV.pdf --vacante aviso.txt
     (o pasa el archivo con --plugin ruta/al/plugin.py)

Qué recibe check():
  cv.texto          texto en orden de lectura (lo que "ve" un ATS)
  cv.texto_layout   texto con disposición espacial
  cv.secciones      {"experiencia": [líneas], "educacion": [...], ...}
  cv.vinetas        {"experiencia": [viñetas completas], ...}
  cv.encabezado     líneas antes de la primera sección (nombre, título, contacto)
  cv.paginas, cv.bytes, cv.imagenes, cv.enlaces
  args              argumentos de la línea de comandos (args.vacante, args.puesto, args.estricto…)

Cómo puntúa un Resultado:
  categoria  "Adaptación" (u otra; las desconocidas pesan 10 en el total)
  puntaje    0.0 a 1.0
  peso       importancia dentro de su categoría
  duro=True  filtro eliminatorio: si no se aprueba, el CV queda NO APROBADO (tope 69/100)

Idea para la fase de adaptación (herramienta externa): llamar aquí a la herramienta que
compare el CV con el aviso (p. ej. una API o un script local), traducir su puntaje a 0..1
y devolver uno o varios Resultado con los problemas y sugerencias que entregue.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cv_checker import Resultado, norm  # noqa: E402


def check(cv, args):
    if not getattr(args, "vacante", None):
        return []
    aviso = Path(args.vacante).read_text(encoding="utf-8", errors="replace")
    # Ejemplo mínimo: ¿el perfil menciona el nombre de la empresa del aviso?
    empresa = ""
    for linea in aviso.splitlines():
        if linea.lower().startswith("empresa:"):
            empresa = linea.split(":", 1)[1].strip()
    if not empresa:
        return []
    ok = norm(empresa) in norm(" ".join(cv.secciones.get("perfil", [])))
    return [Resultado("Adaptación", "Perfil menciona la empresa", 1.0 if ok else 0.5, peso=0.5,
                      aprobado=ok, problemas=[] if ok else [f"El perfil no menciona a {empresa}."],
                      sugerencia="Menciona la empresa o el sector en la última línea del perfil.")]
