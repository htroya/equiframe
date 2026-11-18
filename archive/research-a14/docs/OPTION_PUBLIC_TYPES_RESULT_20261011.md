# Tipos públicos: 74 obligaciones nuevas verificadas

La trazabilidad del núcleo A13 pasa de **5.786 a 5.860 obligaciones de 8.385**,
**69,89 %**. La meta vigente es al menos 85 %: **7.128 IDs verificados**;
faltan **1.268**. El [agregado y hashes](OPTION_PUBLIC_TYPES_RESULT_20261011.json)
conserva el [resultado anterior](OPTION_LITERAL_FIELD_RESULT_20261011.json).

El catálogo se fijó antes de ejecutar: 13 tipos `Literal`, sus 58 alternativas
y tres constantes públicas, contrastados con sus declaraciones A13. Tiene
61 casos positivos y 13 guardias de rechazo sin obligaciones asociadas.
Trece casos positivos comprueban tanto el tipo como su primera alternativa:
se verifican **74 IDs pendientes únicos**, sin inventar IDs de rechazo ausentes
del inventario. Las guardias no incrementan los 74 puntos acreditados.

La [herramienta](../tools/option_public_types_followup.py) ejecutó el catálogo
normal y optimizado en Windows CPython 3.12. Ambas ejecuciones coincidieron:
61 PASS y 13 EXPECTED_REJECTION. La segunda ejecución añade **cero** obligaciones.
Las 22 comprobaciones del arnés y del promedio pasan en ambos modos; el modo
optimizado conserva la advertencia de pytest sobre asserts ajenos a tests.
El arnés emplea controles explícitos y no usa asserts para conceder cobertura.

La revisión IA «mi dot» verificó fuentes y mapeo antes de ejecutar. Identificó
una falsa aceptación posible del arnés: una guardia no debe pasar si su lector
admite el dato. Se corrigió antes de ejecutar y una contraprueba lo verifica.
No representa revisión humana ni modifica el SDK instalado.

El wheel original mantiene SHA-256
`c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23`;
los 127 miembros del payload instalado se cotejaron con sus bytes. Los recibos
privados identifican catálogo, fuentes, herramientas y plataforma. La unión
contiene 4.980 casos de aserción distintos, no 4.980 muestras científicas.

El crédito establece **admisión de tipos declarativos e identidad de constantes**.
No prueba estados calculados por detectores, ejecución nativa de motores,
interacciones de parámetros, efectos de CLI ni resultados de la tesis.
El Word, formatos históricos y las otras rúbricas mantienen sus identidades.
