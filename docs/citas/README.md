# Citas pendientes: cómo pasarlas a Zotero (#29, #30)

La tesina tiene 75 marcas `[CITA PENDIENTE]`, que corresponden a unas 60 obras. Esta
carpeta sirve para cargarlas a Zotero en pocos minutos y verificarlas antes de citarlas.
Claude no edita `thesis/references.bib` (CLAUDE.md).

| Archivo | Para qué |
|---|---|
| `referencias.csv` | Las obras: identificador (DOI, arXiv o ISBN) y qué marcas resuelve cada una. Los identificadores se verificaron contra Crossref, arXiv y Open Library el 2026-10-02 |
| `identificadores.txt` | 46 identificadores para pegar de una vez en Zotero |
| `manuales.bib` | 10 obras sin identificador: NeurIPS, RiskMetrics, Holm, Politis y Romano, la alerta de la SEC, la ficha de TimesFM-3 y los repositorios |
| `verificacion.md` | Cada marca con el párrafo que la usa, para revisar contra el PDF |

## Pasos (Marco)

1. **Importar por identificador (unos 2 minutos).**
   1. En Zotero, haz clic en la varita mágica ("Add Item by Identifier").
   2. Pega **todo** el contenido de `identificadores.txt`; Zotero acepta varios a la vez.
   3. Presiona Enter. Zotero descarga los metadatos de cada obra desde la fuente
      oficial.
2. **Importar las manuales.**
   1. Ve a File → Import → `docs/citas/manuales.bib`.
   2. Revisa las que dicen "VERIFICAR" en la nota.
   3. Borra la entrada incompleta de FinQBoost (`zotero-item-19`); la reemplaza `finqboost`.
3. **Arreglos que ya estaban pendientes (#30):**
   - **`makridakis2025`:** cámbialo a *Journal Article*, con la revista IJF. Hoy sale
     como "(2025, octubre 1)", sin revista.
   - **El preprint de la M6:** quedó separado (arXiv:2310.13357) en el paso 1. Las cifras
     de `docs/hallazgos_m6.md` se verificaron contra ese preprint.
   - **Títulos en *sentence case*** (la configuración de APA en Zotero o BBT).
4. **Obtener los PDF.** Selecciona todo, clic derecho → "Find Available PDF". Los que
   no aparezcan se consiguen por la biblioteca de la UANL.
5. **Verificar (#29) con `verificacion.md`.**
   - Para cada fila, confirma en el PDF que la obra sostiene lo que dice el párrafo, y
     marca la casilla.
   - Si no lo sostiene, avísale a Claude para corregir el texto o cambiar la fuente.
   - **Ayuda posible:** cuando los PDF estén en Zotero (`~/Zotero/storage`), Claude puede
     leerlos y hacer una primera pasada: la página y el pasaje que sostienen cada
     afirmación. Así tú solo confirmas. La verificación final sigue siendo tuya.
6. **Hacer commit de `thesis/references.bib`.** Better BibTeX lo exporta solo.
7. **Avisarle a Claude.** Claude corre esto y revisa lo que cambió antes del commit:

   ```bash
   uv run python scripts/citas.py resolver            # muestra qué cambiaría
   uv run python scripts/citas.py resolver --escribir # reemplaza las marcas por [@clave]
   uv run python scripts/check_citations.py           # 0 claves desconocidas
   ```

   El resolvedor encuentra la clave de cada obra por su DOI, arXiv, ISBN o título. No
   importa qué clave genere Better BibTeX. Solo reemplaza una marca si todas sus obras
   ya tienen clave.

## Una marca sin fuente

En `thesis/chapters/03-justificacion.qmd` dice que **"rara vez se vuelve a evaluar a
los ganadores con datos posteriores"**. Esa afirmación necesita una fuente: estudios de
réplica o de persistencia en competencias de pronóstico. Hay dos caminos:
- encontrar esa fuente;
- o reformular la frase, por ejemplo: "para la M6 no se encontró una reevaluación de los
  métodos ganadores con datos posteriores a la competencia".

## ¿Un agente con *computer use*?

Para cargar las obras no hace falta: la varita mágica de Zotero hace en un paso lo que un
agente haría clic por clic, y con metadatos de la fuente oficial. Donde sí ayuda una IA
es en la verificación del paso 5. Para eso no hace falta otro agente: Claude puede leer
los PDF locales.
