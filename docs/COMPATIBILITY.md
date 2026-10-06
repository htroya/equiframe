# Compatibilidad y estabilidad del candidato STEP6

La política siguiente es un compromiso **prospectivo** del candidato privado
0.11.1. No acredita una publicación, una versión que no se haya probado, una
certificación externa ni la estabilidad científica del experimento. El registro
no ejecuta motores, no carga plugins y no cambia contratos, datos o evidencia.

## Consultar la clasificación exacta

```python
import equiframe as ef

for entry in ef.get_stability_register():
    print(entry.model_dump_json())

print(ef.get_compatibility_policy().model_dump_json())
for adapter in ef.get_adapter_capabilities():
    print(adapter.model_dump_json())
```

Son registros Pydantic estrictos, inmutables e inspeccionables. Se clasifican por
separado `api`, `cli`, `format`, `evidence`, `presentation` y `namespace`. El
inventario explícito contiene todos los nombres de `equiframe.__all__`, cada
comando y parámetro de la CLI y cada esquema JSON distribuido. Añadir un nombre
no lo convierte automáticamente en estable: debe clasificarse y revisarse.

`get_stability_register()` es la autoridad exhaustiva por nombre; las siguientes
agrupaciones explican su intención. **Estable** protege la firma y el significado
documentado dentro de las capacidades admitidas, no todas las entradas ni un
rendimiento/plataforma implícitos. **Experimental** permite evolución anunciada;
no permite resultados ficticios, conversiones ocultas ni modificar retrospectivamente
el significado de evidencia guardada. `unsupported` identifica una interfaz retirada
y en cuarentena, no una funcionalidad experimental operativa.

## API Python

| Clasificación | Superficie |
|---|---|
| Estable | Contratos, escalares, políticas, estados y errores públicos; serialización canónica y validación |
| Estable | Entradas/capturas tipadas, puertos `DataSource`/`ArtifactStore`/`EngineAdapter`, registro de transformaciones confiables, `execute` y adaptadores nativos dentro de sus límites |
| Estable | `compare`, `diff`, declaraciones `bag_contract`/`keyed_contract`/`sequence_contract`, inferencia explícita y sus lectores; estados/completitud separados |
| Estable | Reglas R, evaluaciones y hallazgos; `equivalence_decision`, `assert_equivalent` y errores específicos |
| Estable | Modelo común `ComparisonReport`, sus opciones/políticas y APIs de lectura/publicación/renderizado; el diseño visual y los bytes HTML/texto no están congelados |
| Estable | Verify operacional, sus tipos y `read_verification`; API de bundle de evidencia y sus modelos; no autentican revisores ni acreditan corrección independiente |
| Estable | Los tres inspectores de compatibilidad/capacidades y sus cuatro tipos de registro |
| Experimental | Perfiles, selección normal, preprocesamiento, IF/MAD, calibración y composición H; su estabilidad algorítmica no se deduce de formato `1.0` |
| Experimental | IR/compiladores/migrador y sus modelos/lectores, ingestión, destinos y workflows |
| Experimental | Pipeline, su lector/inspector/resumen, reporte de pipeline y reducción acotada |
| Fuera de este inventario | API interna no exportada, nombres `_...`, dependencias y métodos auxiliares de validación; la API completa del paquete separado `equiframe_benchmark` requiere su propio contrato |

Las firmas de las funciones estables y los campos/defaults/literales de sus
modelos tienen controles de deriva. Para comparar firmas en Python 3.12 y 3.13
se normaliza únicamente la identidad de la clase estándar `pathlib.Path`, cuyo
módulo interno cambió; no se borran anotaciones, defaults ni nombres de parámetros.
Los constructores de modelos siguen siendo
estrictos: las nuevas opciones no autorizan coerciones de tipos. Los métodos
públicos documentados de los tipos registrados conservan su contrato; métodos
heredados de Pydantic y detalles internos no se convierten en API propia.

Las excepciones tipadas y estados conservan su significado. Mensajes diagnósticos,
HTML, CSS, texto de consola y orden visual pueden mejorar sin romper la API.
No analizar frases de error ni HTML como un protocolo. La veracidad, redacción de
valores y separación de `complete`, estado y aceptación sí son obligaciones.

## CLI

| Clasificación | Comandos |
|---|---|
| Estable | `contract validate`, `compare`, `verify validate/run/migration/inspect`, `bundle export/import/verify` |
| Experimental | `run`, `report`, `evidence verify`, `reduce`, `ingestion run`, `migration validate/run/verify`, `workflow validate/run/inspect` |

El registro incluye nombres, argumentos, opciones, obligatoriedad y defaults de
cada comando, además de sus posibles códigos de proceso. `--help` sale 0;
argumentos inválidos pueden salir 2 también en inspectores. No se garantiza el
texto/colores/espaciado de ayuda o stderr. La clasificación de `report` corresponde
al reporte de **pipeline**, distinto de la API estable `comparison_report`.

- `compare`: 0 sólo con equivalencia completa y evidencia exigida verificable;
  1 diferencia completa; 2 entrada/configuración inválida; 3 no evaluable/fallo
- `verify run/migration`, `run` y `migration/workflow run`: conservan la distinción
  operacional 0/1/2/3 documentada para lo solicitado
- Los comandos `inspect`/`verify` de integridad pueden salir 0 al validar evidencia
  de una corrida que históricamente falló: no convierten ese estado en éxito
- `ingestion run`: 0 completo; 1 cuarentena/rechazo de registros; 2 entrada inválida;
  3 fallo técnico. Ese 1 no es una decisión de equivalencia
- `reduce`: 0 reducido/sin cambio; 2 entrada inválida; 3 fallo o límite; no promete
  un mínimo global ni utiliza 1 como diferencia

El auxiliar `equiframe.benchmark` está `unsupported`: siete helpers lanzan
`UnsupportedBenchmarkError`; CLI 2 salvo ayuda 0. El paquete experimental separado
no es un reemplazo compatible ni se importa desde el núcleo.

## Formatos, reportes y evidencia

La versión del paquete, `schema_version` y revisión semántica de un contrato son
independientes. Las especificaciones distribuidas se inventarían por nombre y
SHA-256 de su JSON estructural canónico, sin atribuir el digest a un estándar de
certificación. `equiframe-metadata-json-v1` conserva su algoritmo propio, no JCS.

- Contratos, comparación/diferencias/declaraciones, reglas, ejecución, aserciones,
  reportes de comparación, Verify y bundle mantienen las clasificaciones estables
  explícitas del registro
- Los formatos de productores experimentales conservan esa clasificación. Su
  **lectura histórica** tiene la misma ventana de retirada que los estables
- HTML/texto/notebook son presentaciones evolutivas. Los reportes JSON etiquetados,
  sus manifiestos y hashes constituyen el intercambio verificable
- Un cambio incompatible exige versión nueva de formato, lector explícito y
  procedimiento de migración. No sobrescribir el histórico ni reinterpretarlo
  bajo la versión vieja. Las versiones desconocidas se rechazan
- Migrar crea un artefacto nuevo con procedencia y conserva el original. Este paso
  no promete una conversión automática ni lectores para versiones no incluidas
  en el corpus histórico
- Validar un esquema no verifica archivos, valores, vínculos ni reglas cruzadas.
  Los lectores correspondientes conservan sus comprobaciones; un hash no autentica
  identidad, independencia humana ni exactitud del esperado
- Las rutas absolutas históricas no se vuelven portátiles por clasificar el formato.
  La portabilidad sigue las APIs de bundle o exportación verificadas

El lector compara/inventaría datos históricos según la versión declarada, sin
reejecutar ETL ni exigir bytes del renderizador actual. Pipeline, migración y
Verify verifican sus reportes históricos con el renderizador congelado de la
versión admitida, además de comprobar inventario, hashes y contenido semántico.
Actualizar la presentación actual no obliga a reescribir esos reportes ni
permite aprobar un reporte alterado rehasheándolo. El corpus histórico y sus
pruebas fijan el alcance comprobado, no una aceptación universal de artefactos
antiguos o desconocidos. Evidencia corrupta nunca se aprueba por ser histórica.

## Cambios y deprecaciones

1. Para retirar o cambiar incompatiblemente una superficie estable se publica
   aviso en changelog con nombres afectados, motivo, alternativa, ejemplo de
   migración, versión y fecha más tempranas de retirada
2. El aviso acompaña al uso del punto de entrada Python mediante
   `DeprecationWarning` cuando sea invocable, y a la CLI mediante stderr sin
   alterar el código de salida por el mero aviso. En documentos/esquemas se
   anuncia además la versión sustituta y el lector que conserva la anterior
3. Deben transcurrir **al menos dos versiones minor posteriores al aviso y 90
   días**, ambas condiciones. Ejemplo: aviso en 0.12; retirada no antes de 0.14 y
   nunca antes del día 90. Si faltan releases, se espera; el tiempo no los sustituye
4. Durante 0.x se admite esa retirada sólo en una minor anunciada; desde 1.x,
   sólo en una major y respetando la misma ventana. Una patch no rompe lo estable
   salvo la excepción de seguridad/corrección indicada abajo
5. Una superficie experimental puede cambiar en una minor sin esa espera, con
   changelog y migración en la misma entrega. Cambiarla a estable requiere revisión,
   documentación y regresiones. Rebajar estable a experimental no elude la ventana
6. La retirada de un lector de formato persistido sigue la ventana estable,
   incluso si su productor es experimental. Un lector anterior seguro o una
   migración explícita debe quedar identificado. La deprecación no borra evidencia

No hay nuevas APIs deprecadas en este candidato: la política describe cómo deberá
implementarse cada aviso futuro, no afirma que haya ocurrido una transición.

**Excepción fail-closed:** una vulnerabilidad, evidencia corrupta, pérdida semántica
o falso `equivalent` permite restringir inmediatamente la aceptación, incluso en
patch. Registrar alcance afectado, motivo, ruta segura de recuperación/migración y
regresión ejecutable. No mantener un falso éxito por compatibilidad ni transformar
un fallo en ausencia de alerta. Una ampliación de capacidades no justifica esta
excepción para cambiar silenciosamente un resultado válido anterior.

## Dependencias, plataformas y revisión

El candidato declara Python `>=3.12,<3.14` (3.12 y 3.13).
`pyproject.toml` es la autoridad para admisión de Python/extras; `uv.lock` fija un
entorno concreto. Ningún rango o lock prueba por sí solo todas sus combinaciones.
La [ficha STEP6](STEP6_CANDIDATE.md) distingue combinación medida, rechazo seguro,
configuración de CI y validación pendiente. No hay promesa adicional de sistema
operativo, arquitectura, volumen, timeout duro o certificación de terceros.

Los [adaptadores](ADAPTER_CAPABILITIES.md) enlazan condiciones, pérdidas y tests.
Los controles de este paso cotejan exportaciones, firmas estables, formas de
modelos, CLI y esquemas con el inventario; comprueban referencias ejecutables y que
la introspección no importe motores. Esos controles detectan deriva, pero no
reemplazan las regresiones semánticas ni una revisión de cambios. No actualizar
las huellas automáticamente para silenciar un fallo de compatibilidad.

## Extensión de costes STEP8 del paquete separado

`equiframe_benchmark.ScaleSpec`, `ScaleTrial`, `ScaleRun`, `measure_scale`,
`read_scale` y `summarize_scale`, y sus comandos `scale`/`verify-scale`, son
**experimentales**. Nuevos documentos de ingeniería `ScaleSpec-1.0`,
`ScaleTrial-1.0` y `ScaleRun-1.0` tienen esquemas propios; no reutilizan ni
reinterpretan los formatos científicos `CostSpec`/`CostProtocol`. Sus lectores
validan finalización e inventario, no autentican la ejecución. La lectura es
local y las rutas originales no son un bundle portátil. [Contrato](SCALING.md).
El inventario del núcleo sigue sin incluir la API del paquete separado; sus
firmas, formatos y registro de adaptadores no se modifican por medir costes.
