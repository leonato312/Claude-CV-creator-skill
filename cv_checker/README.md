# cv_checker v1.2 — Verificador local de CVs (ATS + reclutador estricto)

Revisa un CV en PDF con las mismas categorías del Resume Checker de Enhancv: Contenido, Secciones, ATS, Riesgos RR.HH. y Adaptación. Está pensado para CVs **en español** y aplica filtros eliminatorios de reclutador exigente.

Sirve para iterar rápido y gratis antes de la **validación final obligatoria en Enhancv (> 90)**.

## Instalación (una vez)
```bash
pip install pypdf                      # obligatorio
pip install language-tool-python       # opcional: ortografía en español (necesita Java 17+)
# No uses pyspellchecker para español: su diccionario rechaza palabras válidas.
```
Si tienes poppler (`pdftotext`), el script lo usa: extrae mejor el texto. Si no lo tienes, usa pypdf.

## Uso
```bash
python cv_checker.py Nombre_Apellido_CV_Puesto.pdf
python cv_checker.py CV.pdf --estricto                         # 1 página, umbrales duros
python cv_checker.py CV.pdf --vacante aviso.txt --puesto "Técnico de Soporte TI" \
       --excluyentes "Power BI,Excel,Active Directory" --json reporte.json
python cv_checker.py CV_maestro.pdf --max-paginas 3            # CV maestro (más largo)
python cv_checker.py CV.pdf --estricto --practicas             # vacante de prácticas en Perú
```
Códigos de salida: `0` = APROBADO (puntaje > 90 y sin filtros eliminatorios), `1` = NO APROBADO, `2` = error.

## Qué revisa

| Categoría | Chequeo | ¿Eliminatorio? |
|---|---|---|
| Contenido | Lectura por ATS: texto extraíble, íconos convertidos en basura, ligaduras, tildes rotas, palabras cortadas con guion | Sí, si el PDF es imagen |
| Contenido | Impacto cuantificado: % de viñetas de experiencia con cifras (los años no cuentan) | — |
| Contenido | Verbos de acción en pasado, inicios débiles ("Responsable de"), verbos repetidos, tiempo verbal mezclado | — |
| Contenido | Repetición de palabras | — |
| Contenido | Longitud de viñetas y del perfil, puntuación final consistente | — |
| Contenido | Ortografía y gramática en español (LanguageTool), con diccionario técnico | Sí en `--estricto` (> 3 errores) |
| Secciones | Secciones esenciales (Perfil, Experiencia, Educación, Habilidades) y títulos estándar | Sí, si falta Experiencia o Educación |
| Secciones | Contacto: correo, teléfono y LinkedIn arriba, en el cuerpo | Sí, si falta correo o teléfono |
| ATS | Una sola columna / sin tablas | Sí, si más del 25 % del texto está en columnas |
| ATS | Fechas en la misma línea que el cargo | — |
| ATS | Un solo formato de fecha | — |
| ATS | Tamaño menor a 2 MB, número de páginas y nombre de archivo | Sí, si pesa 2 MB o más, o si pasa del máximo de páginas (2 por defecto; `--max-paginas` lo cambia) |
| ATS | Enlaces clicables | — |
| Riesgos RR.HH. | Sin foto, sin datos sensibles (DNI, edad, estado civil…) | — |
| Riesgos RR.HH. | Correo profesional; clichés; texto de plantilla o IA sin reemplazar | Sí, si quedó texto de plantilla |
| Secciones | Estado académico declarado: ciclo, egresado o bachiller (Perú, Ley 28518) | Sí, con `--practicas` |
| ATS | Fechas con mes y año (sin rangos de solo años ni apóstrofes) | — |
| Riesgos RR.HH. | Señales de texto genérico o de IA (vocabulario inflado, viñetas simétricas) | — |
| Adaptación | Requisitos excluyentes con coincidencia **exacta** (como Workday/Taleo), cobertura de palabras clave del aviso, título adaptado | Sí, si falta un excluyente |

## Ajuste al puesto (plugin `plugins/ajuste_puesto.py`, incluido)
Se activa solo con `--vacante aviso.txt`. Compara el CV con el aviso **sin IA ni servicios externos**:
- Separa el aviso en **Requisitos / Deseable / Funciones**: usa esos encabezados en `aviso.txt`; ver `ejemplo/aviso_ejemplo.txt`.
- Mide cada requisito en dos niveles:
  - **exacta**: la frase aparece tal cual, que es lo que busca un ATS booleano como Workday o Taleo;
  - **parcial**: están la mayoría de sus palabras, aceptando plurales, tildes y verbo en infinitivo o en pasado ("documentar" ≈ "documenté").
- Revisa requisitos duros: **años de experiencia** (suma las fechas de Experiencia), **ciclo o grado** (p. ej. "desde 8.º ciclo", "egresado") y **nivel de inglés**.
- Da un **% de ajuste global** (ALTO ≥ 80 %, MEDIO ≥ 60 %, BAJO) y la lista de brechas.
- En `--estricto`, si más de un tercio de los requisitos queda sin evidencia, es filtro eliminatorio.

Regla de uso: las brechas indican qué agregar **solo si es cierto**. Si no lo cumples, no se escribe; en ese caso conviene evaluar si postular.

## Extender (fase de adaptación a la vacante)
Copia `plugins/_plantilla_plugin.py` a `plugins/mi_plugin.py`, sin el guion bajo inicial, e implementa `check(cv, args)`. Todo `.py` de `plugins/` se carga automáticamente, y también puedes pasar uno con `--plugin`. Aquí se conectará la herramienta de adaptación a la vacante.

## Otras validaciones externas
- **Enhancv** (gratis): ver la sección de calibración más abajo.
- **Resume Worded** ("Score My Resume"): exige crear una cuenta gratuita antes de mostrar el puntaje. La persona tiene que crearla ella misma.
- **JobStep.io**: el ATS Checker gratis da un puntaje general sin cuenta. Al CV ficticio le dio 71, con Structure 90, Details 90, Summary 79, Employment 77, Education 69 y Skills 89. La comparación contra un aviso (*tailoring*) exige cuenta y plan de pago, y no tiene API. Por eso no se integra.

## Diccionario técnico
`diccionario_tecnico.txt` contiene marcas, software y tecnicismos que el corrector no debe marcar. Puedes agregar uno propio con `--diccionario mis_terminos.txt`.

## Calibración (23/10/2026)

| CV | cv_checker | Enhancv (versión gratuita) |
|---|---|---|
| CV maestro Harvard (3 págs., con foto) | 66 (normal) / 74 (`--max-paginas 3`) | **70**. Contenido 60 %, parse 70 %, 22 avisos de ortografía, 3 de cuantificación. |
| CV FFAA (2 págs.) | — | **80** |
| CV ficticio de ejemplo (1 pág., cifras en todas las viñetas) | **97,5** (estricto) | **80**. Contenido 95 %, Secciones 100 %, **0 problemas visibles**. |

**Hallazgo importante:** en la versión gratuita de Enhancv, un CV sin ningún problema visible igual queda en **~80/100**. Hay dos razones:

1. Las categorías bloqueadas por PRO (HR Red Flags, Discrimination, Seniority, File Name, Dates & Links) siempre puntúan entre 60 y 78 %, y su valor cambia entre subidas del mismo archivo.
2. "Design" penaliza cualquier plantilla que no sea de Enhancv ("generic layout").

Por eso, **más de 90 en Enhancv gratis no es alcanzable** con un PDF propio. El criterio práctico es:

- cv_checker con más de 90 en `--estricto` y sin filtros eliminatorios, **y**
- Enhancv con **0 problemas en todas las subcategorías desbloqueadas** (Contenido ≥ 95 %, Secciones 100 %, "File Format" sin problemas).
