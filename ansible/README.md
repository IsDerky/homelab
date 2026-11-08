# Ansible

Roles para montar piezas del homelab:

- `base`: zona horaria, paquetes básicos y usuario de administración con sus claves SSH.
- `ssh`: `sshd_config` desde plantilla, solo con claves por defecto.
- `ufw` y `fail2ban`: cortafuegos y baneos, con jails y filtros propios (`playbooks/firewall.yml`).
- `backup`: backups con restic a Google Drive (vía rclone), timers de systemd y simulacro de restauración.
- `avisos`: DMs por Discord para inicios de sesión SSH, errores de SMART y el latido a un vigilante externo.
- `nginx`: nginx con los vhosts del inventario y certbot con validación DNS de Cloudflare.
- `cloudflared`: túnel de Cloudflare gestionado desde el panel, solo con el token.
- `bentonime`: la parte de sistema de la app principal (usuario, unidad systemd, sudo mínimo para el deploy). El código lo despliega su CI.
- `adguard`: AdGuard Home en Docker Compose como servicio systemd, con Unbound opcional (`playbooks/apps.yml`, junto con `bentonime`).
- `code_server`: code-server con un usuario sin privilegios (también en `playbooks/apps.yml`).
- `roninfc`: una web Next.js con puppeteer como servicio systemd encerrado, que se puede dejar instalada y apagada (`playbooks/webs.yml`).
- `monitoring`: Prometheus, Alertmanager, Grafana, blackbox, node_exporter y cAdvisor, más un exportador propio en Python y los avisos por DM de Discord (`playbooks/monitoring.yml`).
- `honeypot`: el mismo honeypot de [cowrie-honeypot](https://github.com/IsDerky/cowrie-honeypot), pero como rol en vez de `install.sh`.
- `pterodactyl`: Wings (binario con versión fija, unidad y límites), live-restore de Docker y la cola y el planificador del panel (`playbooks/pterodactyl.yml`).

## Uso

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp inventory.example.ini inventory.ini   # tu servidor y tus variables
ansible-playbook playbooks/base.yml --check --diff   # ver qué cambiaría
ansible-playbook playbooks/base.yml
```

Para muchas variables es más cómodo `group_vars/<grupo>.yml` que el inventario. Esa carpeta tampoco va a git. Yo tengo el inventario y las variables en un repo privado aparte, con los secretos cifrados con Ansible Vault, y apunto a él con `ANSIBLE_INVENTORY`.

El honeypot necesita en el servidor Docker con Compose v2, systemd e iptables.

`playbooks/site.yml` aplica todo en orden. En una máquina nueva, restaura `/etc/letsencrypt` del backup antes de llegar a nginx.

## Rol `base`

| Variable | Por defecto | |
|---|---|---|
| `base_timezone` | `Europe/Madrid` | |
| `base_packages` | ver `defaults/main.yml` | Paquetes que tienen que estar instalados |
| `base_admin_user` | `admin` | Usuario con sudo |
| `base_admin_keys` | `[]` | Claves públicas que pueden entrar con ese usuario |
| `base_masked_services` | `[]` | Servicios parados y enmascarados (con su `.socket` si lo tienen) |
| `base_disable_cloud_init` | `false` | Crea `/etc/cloud/cloud-init.disabled` |

En una instalación de Ubuntu con escritorio que luego se queda como servidor sobran cosas que siguen arrancando: wifi, bluetooth, perfiles de energía, automontaje de discos… Enmascararlas (no solo deshabilitarlas) evita que D-Bus u otro paquete las vuelva a levantar.

## Rol `ssh`

Ansible pasa a ser el dueño de `/etc/ssh/sshd_config`: los cambios a mano se pierden en la siguiente pasada. Antes de instalar el fichero lo valida con `sshd -t`, así que una plantilla rota no llega a aplicarse. Si cambia, hace `reload` (las sesiones abiertas no se cortan) y guarda copia del anterior.

Los valores por defecto son los seguros. Si hace falta relajar algo mientras se migra (por ejemplo, dejar la contraseña hasta tener claves en todos los equipos), se sobrescribe en el inventario y se quita después.

| Variable | Por defecto | |
|---|---|---|
| `ssh_allow_users` | `[]` | `usuario` o `usuario@ip`. Vacío = sin `AllowUsers` |
| `ssh_password_authentication` | `false` | |
| `ssh_permit_root_login` | `prohibit-password` | |
| `ssh_x11_forwarding` | `false` | |
| `ssh_match_blocks` | `[]` | Bloques `Match` (ver `defaults/main.yml`) |

Antes de aplicarlo la primera vez: deja una sesión abierta como root y comprueba que el usuario nuevo entra con su clave y puede usar sudo.

## Rol `ufw`

Pone las reglas, después las políticas por defecto y al final activa ufw, así que en una máquina nueva no hay ningún momento con todo cerrado y SSH sin abrir. Si ninguna regla abre `ufw_ssh_port`, el rol falla antes de tocar nada.

Solo añade reglas: una que se quite de `ufw_rules` hay que borrarla a mano con `ufw delete`.

```yaml
ufw_rules:
  - port: "443"
    proto: tcp
  - port: "22"
    proto: tcp
    from: 192.168.1.0/24
    comment: SSH LAN
```

## Rol `backup`

Instala `server-backup` y sus timers: `sistema` cada 6 h, `clientes` a diario, `mantenimiento` los domingos (prune y `check` de un cuarto del repo) y `simulacro` el primer domingo de mes, que restaura en `/var/tmp` y comprueba que lo restaurado sirve.

Los secretos (`backup_restic_password` y `backup_rclone_conf`) van en Ansible Vault y solo se escriben si el fichero no existe, es decir, en una máquina nueva. Si ya existe no se toca: sobrescribir la contraseña de un repo que ya tiene datos lo dejaría sin poder abrirse, y rclone reescribe su config al renovar el token. A cambio, el rol comprueba que la contraseña del vault es la del servidor y, al final, que restic abre el repositorio de verdad (`restic cat config`, solo lectura).

El script usa `discord-dm` y `ops-ping` para avisar; no los instala este rol.

### Copia local y NAS

Con `backup_local_mount` (un disco montado), `sistema` y `clientes` hacen además la misma copia en un repo restic local, con la misma contraseña y la misma retención. Va en un proceso aparte (`server-backup _local <modo>`): si el disco no está o falla, la copia de Drive ya está hecha y no se marca como fallida. `mantenimiento` hace en local un `check --read-data` completo cada semana. En local es rápido, y es la única forma de saber que el disco está sano cuando la carcasa USB no deja leer el SMART.

El modo `nas` copia la carpeta del NAS a Drive a diario. No a local: estaría en el mismo disco.

Cada ejecución deja su resultado en `/var/lib/server-backup/estado/<modo>-<destino>.json` (si fue bien, cuándo, la última vez que fue bien y la antigüedad máxima aceptable). `ops-exporter` lo publica y el rol `monitoring` avisa si una copia local falla o si alguna copia se queda atrás. Los fallos de Drive siguen avisando por DM desde el script, como antes.

| Variable | Por defecto | |
|---|---|---|
| `backup_modes` | sistema, clientes, mantenimiento, simulacro | Timers que se instalan. Hay también `nas` |
| `backup_local_mount` | `""` | Disco para la copia local. Vacío = sin copia local |

## Rol `usb_storage`

Un disco externo con LVM: una partición, un grupo de volúmenes y los volúmenes del inventario, cada uno en ext4 y montado por UUID. Lo que no se asigna queda libre en el grupo, y agrandar un volumen después es cambiar su tamaño en el inventario y `resize2fs`, sin mover datos.

```yaml
usb_storage_device: /dev/disk/by-id/usb-...   # no /dev/sdX: cambia según el orden de conexión
usb_storage_volumes:
  - { name: backup, size: 80g, mount: /srv/backup-local, owner: root, mode: "0700" }
  - { name: nas, size: 120g, mount: /srv/nas }
```

- **Lo único que borra datos** (firmas y tabla de particiones) solo se ejecuta con `-e usb_storage_init=true` y si el disco aún no es de LVM. Una pasada normal nunca formatea: `lvol` no reduce volúmenes (`shrink: false`) y `filesystem` no reformatea uno que ya existe.
- Montaje con `nofail` y un timeout de 10 s: si el disco no está, el servidor arranca igual.
- Los permisos de cada volumen solo se tocan si tiene `owner`. Si no, los pone el rol que lo usa (así dos roles no se los cambian en cada pasada).

Para desconectar el disco sin riesgo:

```bash
systemctl stop smbd                     # suelta el NAS
umount /srv/nas /srv/backup-local
vgchange -an usb
```

Al volver a conectarlo: `mount -a && systemctl start smbd`.

## Rol `nas`

Una carpeta compartida por Samba para la LAN:

- Solo SMB3, con cifrado si el cliente lo admite. Sin NetBIOS (`nmbd` enmascarado, solo el puerto 445), sin invitados ni sesiones anónimas, sin impresoras.
- Escucha solo en las interfaces de `nas_interfaces` y acepta solo `nas_hosts_allow`. El cortafuegos va aparte (regla del 445 solo para la LAN en `ufw_rules`).
- Un usuario de sistema sin shell. La contraseña de Samba sale del vault y solo se pone al crearlo. Para cambiarla: `smbpasswd <usuario>` en el servidor y actualizar el vault.
- Con `nas_require_mount` (por defecto) se niega a seguir si la carpeta no está montada. Si no, sería una carpeta vacía en el disco del sistema y los archivos acabarían ahí.
- La configuración se valida con `testparm` antes de instalarla.

## Rol `fail2ban`

Cada jail y cada filtro va en su fichero de `jail.d/` y `filter.d/`. Si algo cambia, primero pasa `fail2ban-client --test` y solo entonces recarga; con una config rota, fail2ban sigue con la anterior. Deja esas carpetas solo para root, porque fail2ban ejecuta como root las `action` que haya en ellas.

Ejemplo para el SFTP de Wings (Pterodactyl), que no pasa por sshd:

```yaml
fail2ban_filters:
  - name: wings-sftp-bots
    definition:
      journalmatch: _SYSTEMD_UNIT=wings.service
      failregex: 'WARN:.*failed to validate user credentials \(invalid format\) ip=<HOST>:\d+'

fail2ban_jails:
  - name: wings-sftp-bots
    settings:
      enabled: true
      filter: wings-sftp-bots
      backend: systemd
      maxretry: 3
      findtime: 1d
      bantime: 7d
      bantime.increment: true
      action: iptables[name=wings-sftp-bots, port=2022, protocol=tcp]
```

## Rol `avisos`

Instala `discord-dm` y los scripts que lo usan:

- `login-alert`, llamado desde PAM al abrir sesión por SSH. Avisa salvo si se entra desde `avisos_login_trusted_ips`. Va como `optional`, así que si falla se entra igual.
- `smartd-discord`, que se engancha a la línea de `smartd.conf` que pongas en `avisos_smartd_line`.
- `ops-ping` y su timer, solo si defines `avisos_watchdog_env`.

`avisos_discord_env` y `avisos_watchdog_env` son el contenido de los `.env` y van en el vault.

## Rol `nginx`

Los vhosts no son plantillas: son los `.conf` tal cual, en `files/nginx/` junto al inventario (`nginx_sites_dir`). Antes de recargar pasa `nginx -t`.

```yaml
nginx_sites:
  - name: pterodactyl
  - name: web-nueva
    enabled: false   # se copia pero no se activa
    check:           # cuando esté activa, tiene que dar 200
      url: http://127.0.0.1:8084/
      host: web.example.com
```

Con `check`, al final del rol (ya recargado nginx) pide esa URL con esa cabecera `Host` y falla si no da 200. Solo para los vhosts activos.

Los certificados no se piden desde el rol. El rol deja certbot, su plugin de Cloudflare y el token en `/root/.secrets/cloudflare.ini` (`nginx_certbot_cloudflare_ini`), y `certbot.timer` se encarga de renovar.

- `nginx_certbot_dns_certs`: certificados creados con el plugin nginx (validan por el puerto 80) que pasan a renovarse por DNS-01. Lo hace `certbot reconfigure`, que prueba la renovación antes de guardar el cambio. Así ya no dependen del 80 ni de por dónde llegue el tráfico.
- `nginx_certbot_deploy_hooks`: comando a lanzar cuando se renueva un certificado concreto, para servicios que solo lo leen al arrancar (Wings, por ejemplo).

Pasar el panel de Pterodactyl al túnel y cerrar 80/443 en el router: [runbook](../docs/runbook-panel-por-tunel.md).

## Rol `cloudflared`

Añade el repo de Cloudflare, instala `cloudflared` y lo arranca con el token del túnel (`cloudflared_tunnel_env`, en el vault). Las rutas del túnel se gestionan en el panel de Cloudflare, no aquí. Como reiniciar el túnel corta lo que pasa por él, solo se reinicia si cambia el token o la unidad.

## Rol `bentonime`

Solo lo que es del sistema: el usuario (con el grupo `render` para que ffmpeg use la GPU), la unidad systemd y un sudoers que deja al deploy reiniciar y consultar su servicio y nada más (validado con `visudo -cf` antes de instalarlo). El código, las dependencias y las migraciones los hace el CI de la app, por versiones y con vuelta atrás.

Al cambiar la unidad **solo recarga systemd, no reinicia la app**, para no cortar a quien esté viendo algo. El siguiente deploy reinicia y aplica el cambio. El `.env.production` (con los secretos) no lo crea el rol: si falta, falla y pide restaurarlo del backup.

## Rol `adguard`

AdGuard Home con el DNS solo en la IP de la LAN (`adguard_dns_listen`; en `127.0.0.53:53` ya está systemd-resolved) y el panel en loopback para nginx. `conf/` y `work/` son datos de AdGuard y van en el backup, no en Ansible. El compose es el mismo que había, así que aplicar el rol no recrea el contenedor: en un servidor que es el único DNS de la casa, eso es un corte.

### Unbound

Con `adguard_unbound: true`, AdGuard deja de mandar las consultas a un DNS público y se las pasa a Unbound, que resuelve él mismo desde los servidores raíz y valida DNSSEC. Nadie de fuera ve todas las consultas de la casa juntas, y una respuesta falsificada con la firma rota se rechaza. A cambio, la primera consulta a un dominio tarda algo más (luego sale de caché, y Unbound la renueva antes de que caduque).

- Unbound va en el mismo compose, en una red propia con IP fija y sin puertos publicados: solo le llega AdGuard.
- Antes de tocar AdGuard, el rol comprueba que Unbound resuelve y que devuelve SERVFAIL para `dnssec-failed.org`, un dominio con la firma rota a propósito. Si falla, AdGuard sigue como estaba.
- El upstream está en `conf/AdGuardHome.yaml`, que es de AdGuard: el rol lo lee, cambia solo `upstream_dns` y `fallback_dns`, guarda copia del anterior y reinicia el contenedor. Como respaldo se queda con los upstream de antes (o `adguard_fallback_dns`), así que si Unbound se cae la casa sigue teniendo DNS.
- Activarlo la primera vez recrea AdGuard (cambia de red): unos segundos sin DNS.
- Que la LAN resuelve se comprueba desde un cliente permitido, no desde el servidor: con `allowed_clients`, AdGuard le responde REFUSED al propio servidor. Desde Windows: `Resolve-DnsName nlnetlabs.nl -Server <ip>` tiene que resolver y `dnssec-failed.org` tiene que fallar.
- Unbound descarta las respuestas que apuntan a IPs privadas (protección contra DNS rebinding), así que un registro público como `oficina.derkyu.lol → 192.168.1.50` se queda sin respuesta. Los dominios de `adguard_unbound_private_domains` sí pueden devolverlas; el rol los pone en `unbound/lan.conf`, que se monta en `custom.conf.d/` de la imagen.

| Variable | Por defecto | |
|---|---|---|
| `adguard_unbound` | `false` | |
| `adguard_unbound_image` | `klutchell/unbound:1.26.2` | |
| `adguard_network_subnet` | `172.31.53.0/24` | Red del compose |
| `adguard_unbound_ip` | `172.31.53.53` | |
| `adguard_fallback_dns` | `[]` | Vacío = los upstream que tuviera AdGuard |
| `adguard_unbound_private_domains` | `[]` | Dominios propios que pueden resolver a IPs de la LAN |

## Rol `code_server`

code-server (VS Code en el navegador, del paquete `.deb`) corriendo con un usuario normal en vez de root. Su terminal y sus extensiones tienen los permisos de ese usuario: si alguien llegara a entrar, no sería root directamente, y para administrar hay que pasar por `sudo` con contraseña.

Con `code_server_migrate_from` hace el cambio una sola vez: para el `code-server@` del usuario anterior, copia su `config.yaml`, extensiones y ajustes, corrige las rutas absolutas de `extensions.json` y arranca el del usuario nuevo en el mismo puerto. Si el usuario nuevo ya tenía un code-server suyo, sus carpetas se apartan (`*.antes-de-migrar-<fecha>`), no se borran. Al acabar deja una marca (`.migrado-de-<usuario>`) para no repetirlo. Lo que haya delante (en mi caso un proxy con TOTP) no se entera del cambio.

| Variable | Por defecto | |
|---|---|---|
| `code_server_user` | `""` | Obligatoria |
| `code_server_migrate_from` | `""` | Usuario del que migrar (p. ej. `root`) |
| `code_server_port` | `8081` | El de su `config.yaml`, para comprobar que arranca |

## Rol `roninfc`

La web que vino del VPS ([runbook de la migración](../docs/runbook-migracion-vps.md)). El rol solo prepara la máquina: usuario de sistema sin shell, `/srv/roninfc/releases` y la unidad systemd. El código no lo toca: lo compila y publica el CI en `releases/<sha>` y enlaza `current`.

Con `roninfc_enabled: false` deja la unidad instalada pero parada y deshabilitada. Con `true` la arranca, y antes comprueba que el CI ha publicado alguna versión. Después espera a que `roninfc_check_path` devuelva JSON con datos (`success` y `data` no vacío), no solo un 200: la ruta hace scraping con Chrome y así se prueba también que puppeteer funciona dentro del encierro de systemd.

| Variable | Por defecto | |
|---|---|---|
| `roninfc_enabled` | `false` | Encendida o solo preparada |
| `roninfc_port` | `3051` | Solo en `127.0.0.1` |
| `roninfc_root` | `/srv/roninfc` | Fijada también en el script de despliegue |
| `roninfc_memory_max` | `1536M` | Next y Chrome juntos |
| `roninfc_check_path` / `roninfc_check_timeout` | `/api/partidos` / `90` | |

## Rol `monitoring`

```
node_exporter ─┐
cAdvisor ──────┤
blackbox ──────┤                         ┌─ Grafana (dashboards)
ops-exporter ──┼─→ Prometheus (15 días) ─┤
alertmanager ──┘                         └─ Alertmanager ─→ alert-dm ─→ discord-dm ─→ DM
```

- **Prometheus, Alertmanager, Grafana, blackbox, node_exporter y cAdvisor** en Docker Compose, como un servicio systemd (`monitoring.service`). Todos con la red del host y escuchando solo en `127.0.0.1`: lo que publica Docker se salta ufw, así que no se publica ningún puerto. Cada contenedor tiene tope de memoria.
- **node_exporter** da además el estado de las unidades systemd de `monitoring_systemd_units` (por D-Bus, con el socket montado de solo lectura). Solo las de la lista: todas serían cientos de series.
- **cAdvisor**: CPU, memoria, swap, red, E/S y OOM de cada contenedor, incluidos los servidores de juego de Wings. Es lo que faltaba para ver si un servidor va justo de memoria o tiene la CPU limitada. Va en el 9338 (su 8080 de siempre es el de Wings) y con las métricas caras desactivadas (uso de disco por capa, procesos, TCP...).
- **blackbox** hace dos tipos de comprobación: las HTTP de `monitoring_http_probes`, que exigen un 200 y un cuerpo concreto y cuentan para el SLO, y las TLS de `monitoring_tls_probes`, que solo piden que el servicio conteste por HTTPS con un certificado válido (Wings sin token da 401 y vale). Las TLS sirven para los nodos de Wings de fuera, que no vigila nadie más, y para avisar si un certificado no se renueva.
- **`ops-exporter`** (Python, solo la librería estándar): lee el JSON que deja `ops-collect` cada 5 minutos (backups, simulacro, SMART, certificados, servicios, fail2ban, deploys y servidores de juego de los tres nodos de Wings) y lo sirve en el formato de texto de Prometheus. No repite nada de lo que da node_exporter. Corre con un usuario efímero de systemd (`DynamicUser`) que solo puede leer ese fichero, por el grupo.
- **`alert-dm`**: Alertmanager solo sabe escribir en canales de Discord, y los avisos del servidor van por DM. Este pequeño receptor traduce su webhook a una llamada a `discord-dm`. El token de Discord es de root (0600): systemd se lo pasa como credencial (`LoadCredential`) a un usuario efímero, sin cambiarle los permisos. Si no consigue mandar el DM, responde 500 y Alertmanager lo reintenta.
- **Dashboards y fuente de datos como código** (provisioning de Grafana). Lo que se cambie desde la web no se guarda. Hay cuatro: *Servidor* (node_exporter), *Bentonime y operación*, *Pterodactyl y contenedores* (nodos, servidores de juego y cAdvisor) y *Todos los servicios*, una tesela verde o roja por cada web, unidad systemd y contenedor, con enlace a la web cuando la tiene.

La configuración se valida antes de instalarla (`promtool check config`, `promtool check rules` y `amtool check-config` con las mismas imágenes). Si cambia, se recarga con SIGHUP sin reiniciar. Por eso se monta por carpetas y no fichero a fichero: Ansible reemplaza cada fichero por uno nuevo, y un montaje de fichero suelto seguiría viendo el antiguo (la recarga cargaba la configuración de antes sin dar ningún error). Al final, el rol espera a que Prometheus pueda leer **todos** sus objetivos; no basta con que los contenedores estén arrancados.

### Alertas

Pocas y solo de cosas graves. Lo demás (backups, certificados de este servidor, servidor caído entero, SMART) ya lo avisan el vigilante externo, el bot y smartd, y repetirlo sería ruido.

| Alerta | Cuándo |
|---|---|
| `SLOQuemaRapida` | Una web gasta su margen de error 14,4 veces más rápido de lo permitido, en 1 h y en 5 min a la vez |
| `DiscoCasiLleno` | Menos del 10 % libre en `/` durante 15 min |
| `MemoriaAgotada` | Menos del 5 % de RAM disponible durante 10 min |
| `ObjetivoCaido` | Prometheus no puede leer algún exporter en 15 min (si no, las alertas que dependen de él no saltarían) |
| `RecolectorParado` | El snapshot de `ops-collect` lleva más de 30 min sin actualizarse |
| `SinRespuestaHTTPS` | Una comprobación TLS falla durante 10 min (un reinicio de Wings tarda segundos y no cuenta) |
| `CertificadoPorCaducar` | Un certificado de las comprobaciones TLS caduca en menos de 14 días. Certbot renueva a 30, así que a 14 algo ha fallado; el caso típico es Wings, que solo lee el certificado al arrancar |

**El SLO.** Cada comprobación HTTP tiene un objetivo de disponibilidad en 30 días (`monitoring_slo_target`, 99,5 % por defecto: unas 3,6 h de fallo al mes). Avisar en cuanto falla una comprobación sería ruido. Esperar a incumplir el objetivo sería avisar tarde. La alerta mira **a qué ritmo se gasta el margen**, en dos ventanas a la vez, como propone el libro de SRE de Google: a 14,4 veces el ritmo permitido, el margen del mes se acaba en unos 2 días. La ventana larga (1 h) evita que salte por un fallo suelto. La corta (5 min) hace que se apague en cuanto se arregla.

Las alertas tienen tests (`tests/alertas_test.yml`, con `promtool test rules`): una caída completa avisa, un fallo suelto de vez en cuando no, y al arreglarse se apaga. El CI los pasa junto con los tests de los dos scripts.

### Variables

| Variable | Por defecto | |
|---|---|---|
| `monitoring_grafana_admin_password` | `""` | Obligatoria. En el vault |
| `monitoring_grafana_root_url` | `http://127.0.0.1:3005/` | Si va detrás de nginx en un subdirectorio, la URL completa |
| `monitoring_grafana_anonymous_viewer` | `false` | Ver sin iniciar sesión (rol Viewer) |
| `monitoring_http_probes` | `[]` | `servicio`, `url` y opcionalmente `body_regex` y `slo` |
| `monitoring_slo_target` | `0.995` | Objetivo por defecto de las comprobaciones |
| `monitoring_tls_probes` | `[]` | `nombre` y `url`. No cuentan para el SLO |
| `monitoring_systemd_units` | `[]` | Unidades cuyo estado exporta node_exporter (expresiones regulares) |
| `monitoring_cadvisor` | `true` | Métricas por contenedor |
| `monitoring_wings_local_node` | `local` | Nombre del nodo de Wings local en las métricas de servidores de juego |
| `monitoring_ops_group` | `""` | Grupo que puede leer el snapshot. Vacío = sin ops-exporter |
| `monitoring_alert_dm` | `true` | Avisos por DM (necesita `discord-dm`, del rol `avisos`) |
| `monitoring_retention_time` / `_size` | `15d` / `2GB` | Lo primero que se cumpla |
| `monitoring_mem` | ver `defaults/main.yml` | Tope de memoria por contenedor |

## Qué hace el rol `honeypot`

1. Comprueba que hay destinos para la prueba de aislamiento y que la subred Docker está libre.
2. Instala el cortafuegos (`honeypot-firewall`), el compose, el `.env`, la limpieza de `systemd-tmpfiles` y la unidad systemd. Todo sale de variables (`defaults/main.yml`).
3. Arranca `honeypot.service`, que pone las reglas de iptables antes de levantar el contenedor.
4. Espera a que escuchen los puertos y lanza la prueba de aislamiento desde la red del honeypot. **Si algún destino responde, para el honeypot y falla.**

Es idempotente: una segunda pasada sin cambios termina con `changed=0`, y solo se reinicia el servicio cuando cambia algo que le afecta.

| Variable | Por defecto | |
|---|---|---|
| `honeypot_test_targets` | `[]` | Obligatoria. `ip:puerto` que el honeypot no debe alcanzar |
| `honeypot_subnet` | `172.30.250.0/24` | Subred Docker; el cortafuegos filtra por ella |
| `honeypot_ssh_port` / `honeypot_telnet_port` | `2222` / `2223` | Puertos del host |
| `honeypot_hostname` | `web-prod-02` | Lo que ve el atacante |
| `honeypot_retention` | `30d` | Antigüedad a partir de la que se borran logs y descargas |
| `honeypot_image` | `cowrie/cowrie:3.1.4` | |
| `honeypot_user` | `cowrie` | Usuario del host con el que corre el contenedor. La imagen trae el uid 999, que en Ubuntu suele ser de otro servicio |
| `honeypot_data_group` | igual que el usuario | Grupo de los datos (p. ej. `systemd-journal` para leer los logs sin root) |

## Cómo se prueba

El workflow `ansible.yml` pasa `ansible-lint` y además aplica el rol de verdad sobre el runner de GitHub Actions, que trae Docker, systemd e iptables:

1. Levanta dos señuelos: un servidor HTTP en el host y un nginx en otra red Docker.
2. **Control positivo**: comprueba que un contenedor normal sí llega a los dos. Si no llegara, la prueba no demostraría nada.
3. Aplica el rol con esos señuelos como destinos prohibidos. La prueba de aislamiento del rol tiene que pasar.
4. Lo aplica otra vez y exige `changed=0`.

## Rol `pterodactyl`

Lo que rodea a Pterodactyl y se puede describir como configuración. El código del panel no: se actualiza a mano con Blueprint y sus extensiones, y eso no encaja en un rol.

- **Wings** con versión fija y el SHA-256 de cada arquitectura. Si el binario instalado ya coincide, no se descarga nada; para actualizar, se cambian versión y sumas en `defaults/main.yml`. La unidad es la de la documentación, y el límite de ficheros abiertos va en un ajuste aparte (`wings.service.d/limites.conf`): con el 4096 de la documentación, Wings avisa al arrancar de que se queda corto.
- **live-restore en Docker.** docker-ce viene de un repositorio de fuera y unattended-upgrades no lo actualiza, así que se actualiza a mano. Sin live-restore, reiniciar dockerd reinicia todos los contenedores, también los servidores de juego. Con él, siguen funcionando mientras dockerd vuelve. Se añade a lo que ya hubiera en `daemon.json` y se aplica con un reload, sin reiniciar nada.
- **Panel** (solo en el nodo que lo tiene): la unidad de la cola (`pteroq`) y el planificador (`schedule:run` cada minuto) en `/etc/cron.d/pterodactyl`. Antes estaba a mano en el crontab de root: el rol lo quita de ahí antes de ponerlo, para que no corra dos veces.

Reiniciar Wings no para los servidores de juego (son contenedores y Wings se reengancha al volver). Solo se cortan unos segundos la consola web y el SFTP. El rol lo reinicia cuando cambia el binario, la unidad o el límite.

`playbooks/pterodactyl.yml` lo aplica a este servidor con el panel y a los nodos del grupo `wings_remotos` (solo Wings y Docker), si el inventario lo tiene.

| Variable | Por defecto | |
|---|---|---|
| `pterodactyl_wings_version` / `_sha256` | `1.13.4` | Sumas por arquitectura (`amd64`, `arm64`) |
| `pterodactyl_wings_nofile` | `65536` | `LimitNOFILE` de Wings |
| `pterodactyl_docker_live_restore` | `true` | |
| `pterodactyl_panel` | `false` | Cola y planificador del panel |
| `pterodactyl_panel_dir` / `_user` | `/var/www/pterodactyl` / `www-data` | |
