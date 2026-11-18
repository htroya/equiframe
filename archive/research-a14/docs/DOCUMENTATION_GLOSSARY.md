# Glosario / Glossary

[Portal](README.md) · [Semántica completa / Full semantics](../packages/equiframe/docs/semantics.md)

| Español / English | Significado operativo / Operational meaning | Referencia |
|---|---|---|
| Contrato / Contract | Declara lo que debe conservarse; validarlo no prueba que una tabla lo cumpla. Declares requirements; metadata validation is not data validation. | [API de contratos](API_CONTRACTS.md#2-modelos-materializados) |
| Esquema / Schema | `schema_version` identifica el formato; `revision` identifica una declaración. Neither is the package version. | [Serialización](API_CONTRACTS.md#3-serialización-y-versiones) |
| Equivalente / Equivalent | Los datos capturados satisfacen el contrato evaluado. Does not prove business correctness or universal program equivalence. | [Semántica](../packages/equiframe/docs/semantics.md) |
| Diferente / Different | Se observa incumplimiento; un gate de equivalencia lo rechaza. Observed mismatch; the gate rejects it. | [Gates](../packages/equiframe/docs/outcome-gates.md) |
| No evaluable / Not evaluable | No puede concluirse equivalencia; nunca equivale a aprobado o sin alerta. Insufficient/invalid evidence is not acceptance. | [Tres estados](DOCUMENTATION_WORKFLOW.md#interpretar-los-tres-casos) |
| Completo / Complete | Informa finalización/cobertura de la evaluación; `complete=True` por sí solo no acepta. Completion alone is not acceptance. | [Assertions](ASSERTIONS.md) |
| Snapshot fijado / Pinned snapshot | Entrada inmutable identificada una vez, con inventario y hashes. No mid-run resolution of `latest`. | [Extensiones](../packages/equiframe/docs/extending.md) |
| Clave / Key | Identifica filas bajo reglas de unicidad e incompletitud; no deduplica silenciosamente. Key policy does not silently deduplicate. | [Comparación](../packages/equiframe/docs/semantics.md) |
| Multiplicidad / Multiplicity | El número de repeticiones de una fila importa según el contrato. A set conversion can lose meaningful duplicates. | [Semántica](../packages/equiframe/docs/semantics.md) |
| Esperado / Expected output | Referencia explícita; su integridad y revisión no garantizan infalibilidad. Engines agreeing can share a bug. | [Verify](VERIFY.md) |
| Hash / Digest | Identifica bytes frente a una referencia confiable; no firma autoría ni aprueba el esperado. Integrity is not authenticity or correctness. | [Auditoría](OFFLINE_WHEEL_AUDIT.md) |
| Recibo / Receipt | Registro de intento, código, artefactos y resultados realmente observados. A configured job is not an executed check. | [Política](DOCUMENTATION_MAINTENANCE.md) |
| Motor nativo / Native engine | Cada motor ejecuta su propia implementación. Converting one result into three frames is not three native runs. | [IR](../packages/equiframe/docs/migration-ir.md) |
| Presupuesto / Budget | Controles cooperativos del núcleo; no garantizan límites duros del SO. Hard isolation requires the surrounding process/service. | [Rendimiento](../packages/equiframe/docs/performance.md) |
| R / M / B / H / O | Reglas, Isolation Forest, MAD, R OR M y referencia independiente. Labels/other-engine results are not detector features. | [Arquitectura](ARCHITECTURE.md) |
| Alpha privada / Private Alpha | Candidato experimental identificado por versión, commit y SHA-256. Private access is not public release or redistribution permission. | [Release](../packages/equiframe/docs/releasing.md) |

Para nombres/campos exactos prevalece la [referencia de API](../packages/equiframe/docs/api.md)
de la distribución identificada. Para resultados medidos prevalece su recibo;
una definición del glosario no afirma que todas las capacidades o plataformas
estén implementadas o verificadas.
