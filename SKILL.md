---
name: "creador-cv-harvard-ats"
description: "Crear o adaptar un CV en formato Harvard apto para ATS, desde un CV maestro y una vacante, validado con cv_checker (>90 estricto) y Enhancv."
---

# Creador de CV Harvard + ATS (v4: validación en 2 etapas + reglas de Perú + ajuste al puesto)

Sigue los pasos EN ORDEN y no saltes ninguno. Responde en el idioma de la persona (por defecto, español). Crea una lista de tareas con los pasos 0–9.

## Reglas que nunca se rompen
1. **No inventes nada.** Cada frase sale de una fuente: CV maestro, certificado, informe, malla o algo que la persona dijo en el chat. Esto incluye cifras, herramientas, niveles y resultados. Si falta un dato, PREGUNTA. Si no puedes preguntar, OMÍTELO.
2. Parte del CV maestro vigente, nunca de otro CV adaptado.
3. Formato Harvard: una columna, apto para ATS, sin foto por defecto.
4. No declares el CV terminado sin pasar el Paso 7 (cv_checker) y el Paso 8 (Enhancv).
5. Las preferencias "solo por esta vez" no se vuelven regla.
6. Nunca crees cuentas en sitios externos a nombre de la persona.

## Paso 0 — Contexto
- Si existe "MD Maestro Creacion de CVs" en el proyecto o en la carpeta de la persona, LÉELO primero. Sus preferencias, decisiones pendientes y frases prohibidas mandan.
- Lee también los registros "Aprendizajes CV …".
- Localiza `cv_checker.py` (v1.2 o superior, con `plugins/ajuste_puesto.py`):
  - (a) en una carpeta conectada, p. ej. `C:\CVs\cv_checker\` (tráelo con `device_stage_files` junto a `diccionario_tecnico.txt` y `plugins/`);
  - (b) en los documentos del proyecto `claude/cv_checker/` (léelos con `project_read` y escríbelos a disco).
  - Si no está, continúa con el checklist manual y avisa en una línea.

## Paso 1 — Intake
Reúne:
- CV maestro.
- Certificados.
- Informes.
- Malla curricular.
- Aviso: empresa, título EXACTO, funciones, requisitos excluyentes y deseables, lugar, y si es de **prácticas** (preprofesionales o profesionales) o empleo.

Guarda el aviso en `aviso.txt` con estos encabezados, uno por línea, para que el plugin de ajuste lo entienda:
```
Puesto: <título exacto>
Empresa: <empresa>
Requisitos:
- <cada requisito excluyente en su línea>
Deseable:
- <cada deseable>
Funciones:
- <cada función>
```
Si solo hay un título de puesto, NO supongas el resto.

## Paso 2 — Analiza la vacante
**Primero, el diagnóstico de ajuste con el CV maestro** (si hay PDF del maestro):
```bash
python cv_checker.py CV_maestro.pdf --vacante aviso.txt --max-paginas 3 [--practicas]
```
Lee las líneas "[Adaptación]":
- % de ajuste global: ALTO ≥ 80 %, MEDIO ≥ 60 %, BAJO.
- Requisitos con evidencia exacta, parcial o sin evidencia.
- Experiencia mínima, ciclo o grado, e inglés.

Si un requisito duro no se cumple (p. ej. pide egresado y la persona es estudiante), **avísale antes de seguir** y pregunta si igual quiere postular.

Después, arma una tabla con las columnas `requisito | excluyente/deseable | evidencia (sí/no, dónde)`. Copia la grafia EXACTA del aviso (Workday y Taleo buscan por palabra exacta) y anota también las siglas.

## Paso 3 — Pregunta los huecos (máx. 4 preguntas, en una sola tanda)
Prioridades:
- (a) Requisitos excluyentes sin evidencia.
- (b) **Cifras reales**: cantidad, frecuencia, tiempo, %, personas, sedes, premios.
- (c) Para minería o energía: ¿disponibilidad para régimen atípico (14x7, 21x7), para trabajar en altura geográfica y para reubicarse? ¿tiene licencia de conducir?

NUNCA estimes una cifra.

## Paso 4 — Selecciona el contenido
Orden:
1. Encabezado: nombre + **título del aviso tal cual** + distrito/ciudad | teléfono | correo | LinkedIn clicable.
2. Perfil (3–4 líneas).
3. Experiencia (cronológico inverso, "Cargo – Empresa", 2–4 viñetas).
4. Educación, con el **estado académico explícito**: "Estudiante de 10.º ciclo", "Egresado" o "Bachiller". En Perú define la modalidad de prácticas (Ley 28518).
5. Proyectos o Tesis (solo si aportan).
6. Cursos.
7. Certificaciones (3–5).
8. Actividades.
9. Habilidades + Idiomas.

Criterios:
- 3–4 soft skills, solo con evidencia.
- Sin duplicados.
- No vacíes las secciones de habilidades, cursos ni actividades.
- Sin foto, DNI, fecha de nacimiento, estado civil ni dirección exacta (Ley 29733).
- 1 página si la persona tiene 3 años o menos de experiencia; 2 como máximo.

Por sector:
- **Minería / energía:** disponibilidad y licencia (solo si son ciertas). En puestos de ingeniero junior, el CIP bajo el nombre.
- **Manufactura:** herramientas y normas explícitas (AutoCAD, SAP, TPM, ISO 9001, Lean).
- **Banca:** SQL, Python, visualización, metodologías ágiles y cifras.

## Paso 5 — Redacta
- Cada viñeta: **verbo de acción en pasado + qué + herramienta + resultado con cifra**. 1–2 líneas (≤ 180 caracteres).
- No repitas un verbo más de 2 veces. Sin pronombres.
- Siglas con el nombre completo la primera vez: "Controlador Lógico Programable (PLC)".
- Todas las fechas con **mes y año**, en un solo formato ("Ene. 2026 – Mar. 2026"). Sin rangos de solo años ni apóstrofes.
- Evita el vocabulario inflado típico de la IA ("orquesté", "sinergia", "vanguardia", "apasionado") y las viñetas todas de igual longitud.
- Usa títulos de sección estándar: Perfil Profesional, Experiencia Laboral, Educación, Habilidades, Certificaciones, Proyectos, Idiomas.

## Paso 6 — Maqueta en LaTeX
Usa esta plantilla (una columna, 10 pt, texto extraíble, sin cortes de palabra):
```latex
\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{mathptmx}
\usepackage[top=1.2cm,bottom=1.2cm,left=1.8cm,right=1.8cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\input{glyphtounicode}\pdfgentounicode=1
\pagestyle{empty}
\setlength{\parindent}{0pt}
\hyphenpenalty=10000 \exhyphenpenalty=10000
\titleformat{\section}{\normalsize\bfseries\uppercase}{}{0pt}{}[\vspace{-6pt}\rule{\textwidth}{0.4pt}]
\titlespacing*{\section}{0pt}{6pt}{4pt}
\setlist[itemize]{leftmargin=1.2em,itemsep=0pt,topsep=2pt,parsep=0pt}
\newcommand{\entry}[4]{\textbf{#1} \hfill #2\\ \textit{#3} \hfill #4\par}
\begin{document}
\begin{center}
{\Large\bfseries NOMBRE APELLIDO}\\[2pt]
Título exacto del puesto\\[2pt]
Distrito, Ciudad \;|\; +51 999 999 999 \;|\; nombre.apellido@dominio.com \;|\; \href{https://linkedin.com/in/usuario}{linkedin.com/in/usuario}
\end{center}
\section{Perfil Profesional}
...
\section{Experiencia Laboral}
\entry{Cargo -- Empresa}{Ene. 2026 -- Mar. 2026}{Área}{Ciudad, País}
\begin{itemize}
  \item Verbo + tarea + herramienta + resultado con cifra.
\end{itemize}
\end{document}
```
Reglas de la plantilla:
- No uses `babel[spanish]`, íconos, tablas, columnas ni minipages.

Compila y MIRA cada página:
```bash
pdflatex -interaction=nonstopmode Nombre_Apellido_CV_Puesto.tex
pdftoppm -png -r 80 Nombre_Apellido_CV_Puesto.pdf preview
```

## Paso 7 — Etapa 1: cv_checker (obligatorio, gratis, iterar sin límite)
```bash
pip install pypdf language-tool-python   # la ortografía necesita Java 17+; NO uses pyspellchecker para español
python cv_checker.py Nombre_Apellido_CV_Puesto.pdf --estricto \
   --puesto "<título exacto>" --excluyentes "<req1>,<req2>" --vacante aviso.txt [--practicas]
```
- Usa `--practicas` si la vacante es de prácticas: el estado académico pasa a ser eliminatorio.
- **Meta: "APROBADO" con más de 90 y ningún filtro eliminatorio** (código de salida 0). Cobertura de palabras clave del aviso ≥ 75 %.
- Lee el DETALLE, corrige, recompila y repite.
- Si un término técnico válido sale como error ortográfico, agrégalo a `diccionario_tecnico.txt`.
- Si solo faltan cifras que únicamente la persona conoce, pregúntale.
- Para un CV maestro largo usa `--max-paginas 3` en vez de `--estricto`.
- Atiende también lo que reporten los plugins de `plugins/`.
- **Ajuste al puesto** (plugin, se activa con `--vacante`):
  - Meta en `--estricto`: "Requisitos del aviso" ≥ 75 %, ningún requisito duro incumplido y ajuste global ALTO, o MEDIO con la brecha explicada a la persona.
  - Las brechas "parcial" se cierran usando la palabra EXACTA del aviso en una frase que ya era verdad.
  - Las brechas "sin evidencia" NO se cierran inventando: se preguntan a la persona o se dejan.

## Paso 8 — Etapa 2: Enhancv (con el navegador)
1. La PRIMERA vez, pide permiso para subir el CV a Enhancv: es un sitio externo con datos personales.
2. Carga el skill del navegador. El PDF debe estar en `/mnt/user-data/uploads/` o en los adjuntos. Si está en la carpeta conectada, usa `device_stage_files`. `/mnt/user-data/outputs` NO se puede subir.
3. Abre `https://enhancv.com/resources/resume-checker/`, localiza con `find` el *file input* principal y sube el PDF con `file_upload`. Nunca hagas clic en el botón de subir.
4. Cierra con la X el popup de idioma, espera unos 20 s y lee el reporte con `get_page_text`.
5. Opcional: en "Resume Tailoring" pega el aviso y pulsa "Get Tailored Insights". Corrige Hard Skills, Action Verbs y Tailored Title.
6. **Criterio de aprobación:**
   - 0 problemas en TODAS las subcategorías desbloqueadas (ATS Parse Rate, Quantifying Impact, Repetition, Spelling & Grammar, Essential Sections, Contact, File Format).
   - Contenido ≥ 95 % y Secciones 100 %.
   - Anota el puntaje global.
7. ⚠️ **Techo conocido:** en la versión gratuita, un CV propio sin ningún problema visible queda en ~80/100, porque las categorías PRO bloqueadas y "Design" lo limitan. NO persigas más de 90 allí. Si la persona lo exige, ofrécele dos opciones: Enhancv PRO, o su plantilla "Ivy League". Resume Worded es otra validación posible, pero exige que la persona cree su propia cuenta.
8. Ofrece borrar el reporte ("Permanently Delete Report Data"). Solo bórralo si la persona lo confirma.
9. Cierra las pestañas que abriste.

## Paso 9 — Entrega y registro
- Guarda el PDF, el `.tex` y `aviso.txt` en la carpeta persistente.
- Responde en 2–3 líneas: el archivo, los puntajes (cv_checker inicial → final; Enhancv global y si quedó en 0 problemas) y una sola pregunta pendiente si la hay.
- Recuerda que las preguntas eliminatorias del formulario de postulación se responden IGUAL que el CV.
- Escribe "Aprendizajes CV <puesto>.md" con estas secciones:
  1. Vacante.
  2. Decisiones.
  3. Qué se priorizó.
  4. Formato.
  5. Puntajes.
  6. ⚠️ Frases no textuales del maestro.
  7. Datos nuevos para el maestro.
  8. Pendientes.
  9. Aprendizajes de proceso.

## Checklist final
- [ ] Todo es trazable a una fuente; no hay frases inventadas.
- [ ] Título del aviso bajo el nombre; palabras exactas del aviso que se cumplen, con siglas.
- [ ] Estado académico explícito (ciclo / egresado / bachiller).
- [ ] La mayoría de las viñetas tiene verbo de acción y cifra real; ninguna pasa de ~180 caracteres.
- [ ] Fechas con mes y año en un solo formato; "Cargo – Empresa" uniforme; títulos de sección estándar.
- [ ] Una columna, sin íconos ni foto ni datos sensibles, sin cortes de palabra, 10 pt, < 2 MB, 1–2 páginas y nombre `Nombre_Apellido_CV_Puesto.pdf`.
- [ ] **cv_checker --estricto: APROBADO (más de 90, sin eliminatorios).**
- [ ] **Ajuste al puesto**: requisitos ≥ 75 %, sin requisitos duros incumplidos; las brechas pendientes se explicaron a la persona.
- [ ] **Enhancv: 0 problemas en las subcategorías desbloqueadas** (puntaje global anotado).
- [ ] Archivos guardados en lugar persistente y registro escrito.