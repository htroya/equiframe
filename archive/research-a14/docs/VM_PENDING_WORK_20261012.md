# Estado de la VM y trabajo restante

VM `157.137.227.1`, usuario `hernan`, Linux ARM64. SSH se recuperó con la nueva
clave; los antiguos timeouts permanecen como intentos históricos. Conexión:

```powershell
ssh -i "C:\HT\maestria datos\tesis\VM\hernan_nueva.key" hernan@157.137.227.1
```

## Completado realmente

- [M13](M13_VM_COMPLETED_20261012.md): kit r2, 115 comandos, 52 perfiles,
  Python 3.10/3.12, regresión, construcción, consumidor, fallos y recuperación.
  Expediente completo y supervisión devueltos y cotejados. El original fallido
  se conserva separado; no queda pendiente la devolución de estos ensayos.
- [Comparación anual completa](SERCOP_ANNUAL_VM_20261011.md): 81 comprobaciones,
  incluidas 27 sobre todas las adjudicaciones, tras ampliar el presupuesto
  explícito del comparador. El antiguo límite de 256 MiB permanece histórico.
- [Dataset público](SERCOP_PUBLIC_DELIVERY_20261012.md): entrega autorizada,
  287 archivos, hashes verificados, sólo lectura y HTTPS por túnel saliente.
  No hay EDA/reflexión ni DW aceptado en esa carpeta.
- [Alpha A14 y EDA](EDA_IMPLEMENTATION_20261012.md): misma pareja de wheels
  y dependencias comunes que Windows, instalación y payloads cotejados,
  suite ARM completa anterior más delta final, benchmark con `resources`,
  modo optimizado y ocho tablas anuales. Los runs quedan privados fuera
  de la carpeta pública. El expediente devuelto de 343 miembros pasó SHA/CRC.
- Limpieza: 9.421.471.744 bytes de laboratorios M13 respaldados y
  683.454.464 bytes de temporales A14; se conserva el runtime vigente.

## Pendiente real

1. M04: completar únicamente las celdas nativas/perfiles/bandas comprometidas
   aún sin recibo. Linux ARM64 3.10/3.12 y ejemplos Windows 3.10–3.13 no cubren
   Linux x64, macOS ni automáticamente todos los perfiles restantes.
2. Ejecución científica: requiere contrato/cohorte/normalidad, freeze y etiquetas
   humanas aprobadas antes de ajustar o interpretar un conjunto de prueba final.
3. DW y gateway del equipo: Jhair/José deben entregar sus commits, comando/error
   real y garantías comprobadas. El [diagnóstico](JHAIR_DW_DIAGNOSTIC_20261012.md)
   reproduce fallos del prototipo con datos sintéticos locales; no desplegó esos
   componentes ni atribuye a la VM un problema no observado.
4. Continuidad pública: confirmar hosting estable si se necesita enlace fijo.
   Los servicios de usuario están habilitados; un reinicio del Quick Tunnel
   cambia el hostname y requiere comunicar el enlace nuevo.
5. Celdas A14: esta nueva evidencia corresponde a Windows y ARM64 Python 3.12;
   no convierte los ensayos A13 de otros Python/plataformas en pruebas A14.
   La extensión EDA ya está instalada en ambos hosts. Falta reevaluar las
   rúbricas completas y restantes celdas comprometidas con el nuevo candidato.

No hace falta repetir los expedientes completos devueltos sin motivo nuevo.
Las pruebas restantes deben tener alcance y resultado propios. Para retirar
temporales hay que inventariar rutas, confirmar respaldo verificado y preservar
originales, evidencias fallidas y datos públicos; no se borra por tamaño únicamente.
