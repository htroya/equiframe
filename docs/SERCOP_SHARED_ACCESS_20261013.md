# SERCOP: acceso compartido y continuidad del enlace

La entrega vigente está en:

```text
/var/tmp/equiframe-public-sercop-2025/entrega-20261012-v1
```

Jhair usa la cuenta Linux **`jair`**. Se habilitó lectura para el grupo
**`equiframe`**, al que pertenecen `jair` y `ubuntu`. La cuenta exacta usada por
José debe confirmarse al ingresar: no existen cuentas `jose`, `joise` ni variantes
de Gaona en esta VM. `root` ya tiene acceso administrativo y no es una cuenta
personal a la que asignar permisos de lector.

Desde su propia sesión, cualquiera de esas dos cuentas puede usar:

```bash
id
cd /var/tmp/equiframe-public-sercop-2025/entrega-20261012-v1
ls
cat LEEME.txt
```

No necesita entrar en el home de Hernán. Directorios `0550`, archivos `0440`,
grupo `equiframe`; los lectores no tienen permisos de modificación. Se verificó
la pertenencia a ese grupo y los permisos efectivos, sin iniciar sesión con las
credenciales de los colaboradores. Los 287 archivos fueron comprobados por
tamaño/SHA-256; el manifiesto conserva
`712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c`.

El [enlace entregado a la tutora](https://garlic-comments-semiconductor-assume.trycloudflare.com/)
continúa igual. Se cambió sólo la raíz del servidor HTTP de lectura en loopback
a esta carpeta. El túnel conservó PID **291724** antes/después; se reemplazó su
dependencia `Requires` por `Wants` para que reiniciar el origen no detuviera el
túnel. Se comprobaron el índice por hash, el manifiesto por hash y **286 enlaces
externos HEAD** tras el cambio.

Después de esas comprobaciones, se eliminó exclusivamente
`/home/hernan/public-sercop-2025/entrega-20261012-v1` y su padre vacío, como pidió
el propietario. Los permisos del home privado no cambiaron. La copia Windows y
el archivo de transferencia permanecen respaldados. Los recibos operativos
están en `/home/hernan/sercop-delivery-control-20261012/shared-origin-receipt-20261013.json`
y `/var/tmp/equiframe-public-sercop-2025/access-receipt-20261013.json`.

La ubicación en `/var/tmp` está sujeta a la política de limpieza del sistema.
Una ubicación permanente como `/srv` necesita intervención administrativa;
Hernán no dispone de sudo sin contraseña. El hostname del Quick Tunnel continúa
siendo temporal y puede cambiar si se reinicia su propio proceso. Esta entrega
no lo reinició ni lo presenta como hosting permanente.
