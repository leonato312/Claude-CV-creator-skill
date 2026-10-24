# creador-cv-harvard-ats

Skill de Claude para crear o adaptar CVs en formato Harvard, aptos para ATS, desde un CV maestro y un aviso de empleo o prácticas.

- `SKILL.md`: el skill (flujo de 10 pasos, reglas de Perú, validación en 2 etapas).
- `cv_checker/`: verificador local en Python (`cv_checker.py`, plugin `ajuste_puesto.py`, diccionario técnico y un CV de ejemplo ficticio).

## Uso rápido
```bash
pip install pypdf language-tool-python   # Java 17+ para la ortografía
python cv_checker/cv_checker.py MiCV.pdf --estricto --vacante aviso.txt --puesto "Título" [--practicas]
```
Para instalar el skill en Claude, súbelo como skill personalizado usando `SKILL.md`.
