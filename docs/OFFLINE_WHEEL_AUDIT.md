# Verificar el wheel privado antes de instalar

`packages/equiframe/tools/audit_wheel.py` utiliza sólo la biblioteca estándar de
Python 3.10–3.13. No importa EquiFrame, extrae archivos, abre un navegador,
instala dependencias ni consulta la red. El script procede del checkout
confiable; no ejecute un script que venga en un wheel aún no confiable.

Reciba el SHA-256, nombre y versión por el canal privado verificado por el que
obtuvo el candidato. Calcular el hash del archivo y suministrarlo como supuesto
valor esperado sólo comprueba consistencia; no autentica al distribuidor.
El auditor no resuelve la licencia ni garantiza ausencia de vulnerabilidades.

## Comando manual

Desde la raíz del checkout, con Python ya instalado:

```powershell
python packages/equiframe/tools/audit_wheel.py C:/ruta/equiframe-0.12.0a13-py3-none-any.whl --sha256 SHA256_RECIBIDO --name equiframe --version 0.12.0a13 --output C:/ruta/recibo-nuevo.json
```

En Linux o la VM existente:

```bash
python3 packages/equiframe/tools/audit_wheel.py /ruta/equiframe-0.12.0a13-py3-none-any.whl --sha256 SHA256_RECIBIDO --name equiframe --version 0.12.0a13 --output /ruta/recibo-nuevo.json
```

Para el benchmark cambie el archivo a
`equiframe_benchmark-0.12.0a13-py3-none-any.whl` y el nombre a
`equiframe-benchmark`; use **su propio hash** y otro recibo. Cada salida necesita
un directorio padre existente y un nombre de archivo nuevo.

## Qué comprueba

- SHA-256 esperado antes de analizar ZIP; inspección sobre la misma imagen de bytes.
- Un único `dist-info`, nombre/versión exactos, Requires-Python y marcador `py.typed`.
- Rutas canónicas cerradas; sin duplicados, enlaces simbólicos, directorios,
  entradas especiales ni cifradas. Límites explícitos de tamaño y número de entradas.
- Inventario RECORD completo, sin duplicados, con hashes SHA-256 y tamaños exactos.
- Destinos de archivos en enlaces Markdown inline presentes en el wheel.
  Excluye bloques de código y registra enlaces externos/anchors como no verificados.

La comprobación de navegación es acotada: no evalúa anchors, enlaces de
referencia, imágenes, HTML, acceso remoto ni UX. La identidad del wheel se
comprueba antes de instalar; su compatibilidad funcional exige pruebas aparte.
El inventario de hashes del recibo permite cotejar payloads, pero no es una firma.

Salida de proceso: **0** PASS; **1** fallo de hash, estructura, RECORD o enlaces;
**2** error de uso o imposibilidad de reservar el recibo (incluye destino ocupado).
Los intentos fallidos conservan su recibo cuando pudieron reservarlo. Un segundo
intento no reemplaza el anterior. Los controles funcionan con Python `-O`.

Después de PASS, siga la
[guía de instalación privada](../packages/equiframe/docs/installed-private.md)
para el artefacto y sus dependencias revisadas, en un entorno nuevo fuera del
checkout. Ejecute `pip check`, `equiframe doctor` y su caso representativo.
No use el resultado para ejecutar callbacks o plugins de origen desconocido.

Plan y definición del porcentaje:
[rúbrica de calidad de paquete](PACKAGE_QUALITY_PLAN_20261010.md).
