# Validación manual de perfiles identificados

`validate_profiles.py` comprueba instalaciones aisladas del núcleo y benchmark
de la versión declarada, ocho perfiles del núcleo y cinco del benchmark. Usa los wheels
privados y los ejemplos/probe del sdist correspondiente. No modifica el núcleo,
activa Actions, publica paquetes ni crea infraestructura.

El controlador necesita Python 3.10–3.13 y `uv` ya instalado. Se deben entregar
un intérprete explícito, los dos wheels del candidato, fuentes extraídas de ambos sdists,
una caché de uv y un archivo de versiones públicas fijadas. `--output` debe
ser una carpeta nueva fuera del checkout. No emplear un venv con el paquete
editable ni copiar resultados históricos. Los paquetes opcionales se instalan
mediante resolución normal, con las constraints indicadas; no `--no-deps`.

```bash
python tools/universality/validate_profiles.py \
  --candidate-version 0.12.0a13 \
  --uv "$UV" --base-python "$PYTHON" --cache "$CACHE" --pins "$PUBLIC_PINS" \
  --artifacts "$A11_WHEELS" --source "$CORE_SDIST_SOURCE" \
  --benchmark-source "$BENCHMARK_SDIST_SOURCE" \
  --benchmark-probe tools/universality/benchmark_probe.py --output "$NEW_OUTPUT"
```

El valor predeterminado conserva el recorrido histórico A11. Para reevaluar
otra versión hay que declararla: el controlador rechaza un par de wheels cuya
identidad no coincida y los probes verifican los bytes instalados. Un recibo A11
no se convierte en A13 al cambiar ese argumento.

En PowerShell se pasan los mismos argumentos y se invoca el ejecutable con `&`.
Los argumentos admiten rutas con espacios. El archivo de constraints se copia
al laboratorio y se pasa con una ruta relativa para evitar la interpretación
incorrecta de espacios observada en uv al leer una ruta absoluta con `-c`.
`--offline` restringe la resolución a la caché existente; una dependencia
ausente conserva un fallo de establecimiento, no demuestra incompatibilidad.

`--package core|benchmark` y `--profile NOMBRE` (repetible) permiten repetir
solo perfiles afectados, siempre en una carpeta nueva. Los recibos completos
de cada perfil aprobado pueden reunirse conservando también los fallidos;
una selección parcial no acredita por sí sola los trece perfiles.

Cada entorno prueba origen instalado y bytes completos del núcleo, inventario
real, extras presentes/ausentes, importación sin motores anticipados, contratos
válidos/inválidos, comparación equivalente/discrepante/no evaluable y evidencia
persistida. Los perfiles pertinentes ejecutan ejemplos nativos de cinco
familias, seis migraciones o ajuste/calibración/detección sintética.
El benchmark verifica además sus bytes instalados, un esquema inválido y CLI.
Los perfiles `resources`/`all` miden tres repeticiones reales de 1000 filas;
los restantes deben conservar la limitación explícita de `resources` ausente,
sin ejecutar ni aceptar una medición inexistente.

El archivo `summary.json` contiene estados observados, comandos/resultados por
etapa, identidad de intérprete/plataforma/dependencias y hashes. Los logs y
artefactos permanecen en el laboratorio privado. El proceso limita hilos,
aplica timeouts de 1200 segundos por comando y exige 4 GiB libres antes de cada
etapa; no establece cuotas duras de memoria ni prueba tamaños arbitrarios.

El recorrido acredita únicamente los perfiles, versiones y plataformas
observados. No cierra extremos de dependencias, macOS, veinte celdas nativas,
revisión humana independiente ni el protocolo científico del benchmark.
