# ¿Cuánto del alfa es ilusión?

Tesina de la Maestría en Ciencia de Datos (FCFM, UANL). Réplica y extensión de la competencia M6:
evaluación honesta de pronósticos probabilísticos de rendimiento relativo con aprendizaje automático.

Autor: Marco Antonio Obregón Flores.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (Python ≥ 3.12)
- [Quarto](https://quarto.org/) para renderizar la tesina

## Uso

```bash
uv sync                      # instala dependencias (incluye el grupo dev)
uv run pre-commit install    # activa los hooks
uv run pytest                # corre los tests
uv run python scripts/check_citations.py   # verifica @claves contra thesis/references.bib
```

## Tesina

```bash
quarto render thesis         # genera thesis/_output/tesina.docx
```

- Capítulos en `thesis/chapters/*.qmd`, incluidos desde `thesis/tesina.qmd`.
- Portada, hoja de firmas, dedicatoria y agradecimientos se configuran en la clave `uanl` de `thesis/_quarto.yml`.
- `thesis/templates/reference.docx` se deriva de la plantilla oficial con `uv run python scripts/build_reference_docx.py`.
- El post-render (`scripts/postprocess_docx.py`) agrega portada, firmas, índices y etiquetas "CAPÍTULO N". Al abrir el docx, Word pide actualizar los campos; hay que aceptar para que se llenen los índices.

## Estructura

| Ruta | Contenido |
|------|-----------|
| `src/tesina/` | Paquete: `data`, `evaluation`, `models`, `backtest`, `universe` |
| `data/raw/` | Snapshots de datos congelados (nunca se sobrescriben) |
| `vendor/` | Código adaptado de participantes del M6, con su licencia |
| `experiments/<nombre>/` | `config.toml` + `run.py` por experimento |
| `results/<nombre>/` | Outputs versionados con config y hash del commit |
| `scripts/` | Utilidades (verificación de citas, post-proceso del docx) |
| `tests/` | Tests, incluidos los de anti-leakage |
| `thesis/` | Proyecto Quarto de la tesina |

Las reglas del proyecto (anti-leakage, evaluación, reproducibilidad, citas) están en [`CLAUDE.md`](CLAUDE.md).
Las tareas se gestionan en GitHub Issues.
