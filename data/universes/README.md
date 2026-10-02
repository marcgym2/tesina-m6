# Listas de símbolos

- `sebrad_extended.csv`: el universo extendido que usa el método de sebrad (#18).
  - Son 732 acciones y 431 ETFs de EE. UU., con los tickers en formato Yahoo.
  - Se extrajeron de `data/stocks_extended.qs` y `data/etf_extended.qs` de
    <https://github.com/sebrad/M6> (commit `0c7d0dd`) con `qs::qread` (paquete qs 0.26.1).
  - El repositorio de sebrad no declara licencia, así que su código no se copia aquí. Esta
    lista contiene solo tickers.
  - La lista se compiló después de la competencia. El sesgo de supervivencia que eso
    implica está documentado en `vendor/sebrad/README.md`.
  - `scripts/download_eodhd.py --group sebrad` descarga estos símbolos. Si alguno falta en
    EODHD, se registra en el manifest y no detiene la descarga, igual que en el código
    original, que también tolera fallas.
