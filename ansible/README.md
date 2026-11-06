# Ansible

Roles para montar piezas del homelab:

- `base`: zona horaria, paquetes básicos y usuario de administración con sus claves SSH.
- `ssh`: `sshd_config` desde plantilla, solo con claves por defecto.
- `ufw` y `fail2ban`: cortafuegos y baneos, con jails y filtros propios (`playbooks/firewall.yml`).
- `backup`: backups con restic a Google Drive (vía rclone), timers de systemd y simulacro de restauración.
- `avisos`: DMs por Discord para inicios de sesión SSH, errores de SMART y el latido a un vigilante externo.
- `nginx`: nginx con los vhosts del inventario y certbot con validación DNS de Cloudflare.
- `cloudflared`: túnel de Cloudflare gestionado desde el panel, solo con el token.
- `roninfc`: una web Next.js con puppeteer como servicio systemd encerrado, que se puede dejar instalada y apagada (`playbooks/webs.yml`).
- `monitoring`: Prometheus, Alertmanager, Grafana, blackbox y node_exporter, más un exportador propio en Python y los avisos por DM de Discord (`playbooks/monitoring.yml`).
- `honeypot`: el mismo honeypot de [cowrie-honeypot](https://github.com/IsDerky/cowrie-honeypot), pero como rol en vez de `install.sh`.

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

## Rol `cloudflared`

Añade el repo de Cloudflare, instala `cloudflared` y lo arranca con el token del túnel (`cloudflared_tunnel_env`, en el vault). Las rutas del túnel se gestionan en el panel de Cloudflare, no aquí. Como reiniciar el túnel corta lo que pasa por él, solo se reinicia si cambia el token o la unidad.

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
blackbox ──────┤                         ┌─ Grafana (dashboards)
ops-exporter ──┼─→ Prometheus (15 días) ─┤
alertmanager ──┘                         └─ Alertmanager ─→ alert-dm ─→ discord-dm ─→ DM
```

- **Prometheus, Alertmanager, Grafana, blackbox y node_exporter** en Docker Compose, como un servicio systemd (`monitoring.service`). Todos con la red del host y escuchando solo en `127.0.0.1`: lo que publica Docker se salta ufw, así que no se publica ningún puerto. Cada contenedor tiene tope de memoria.
- **`ops-exporter`** (Python, solo la librería estándar): lee el JSON que deja `ops-collect` cada 5 minutos (backups, simulacro, SMART, certificados, servicios, fail2ban, deploys) y lo sirve en el formato de texto de Prometheus. No repite nada de lo que da node_exporter. Corre con un usuario efímero de systemd (`DynamicUser`) que solo puede leer ese fichero, por el grupo.
- **`alert-dm`**: Alertmanager solo sabe escribir en canales de Discord, y los avisos del servidor van por DM. Este pequeño receptor traduce su webhook a una llamada a `discord-dm`. El token de Discord es de root (0600): systemd se lo pasa como credencial (`LoadCredential`) a un usuario efímero, sin cambiarle los permisos. Si no consigue mandar el DM, responde 500 y Alertmanager lo reintenta.
- **Dashboards y fuente de datos como código** (provisioning de Grafana). Lo que se cambie desde la web no se guarda.

La configuración se valida antes de instalarla (`promtool check config`, `promtool check rules` y `amtool check-config` con las mismas imágenes). Si cambia, se recarga con SIGHUP sin reiniciar. Por eso se monta por carpetas y no fichero a fichero: Ansible reemplaza cada fichero por uno nuevo, y un montaje de fichero suelto seguiría viendo el antiguo (la recarga cargaba la configuración de antes sin dar ningún error). Al final, el rol espera a que Prometheus pueda leer **todos** sus objetivos; no basta con que los contenedores estén arrancados.

### Alertas

Pocas y solo de cosas graves. Lo demás (backups, certificados, servidor caído entero, SMART) ya lo avisan el vigilante externo, el bot y smartd, y repetirlo sería ruido.

| Alerta | Cuándo |
|---|---|
| `SLOQuemaRapida` | Una web gasta su margen de error 14,4 veces más rápido de lo permitido, en 1 h y en 5 min a la vez |
| `DiscoCasiLleno` | Menos del 10 % libre en `/` durante 15 min |
| `MemoriaAgotada` | Menos del 5 % de RAM disponible durante 10 min |
| `ObjetivoCaido` | Prometheus no puede leer algún exporter en 15 min (si no, las alertas que dependen de él no saltarían) |
| `RecolectorParado` | El snapshot de `ops-collect` lleva más de 30 min sin actualizarse |

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

## Cómo se prueba

El workflow `ansible.yml` pasa `ansible-lint` y además aplica el rol de verdad sobre el runner de GitHub Actions, que trae Docker, systemd e iptables:

1. Levanta dos señuelos: un servidor HTTP en el host y un nginx en otra red Docker.
2. **Control positivo**: comprueba que un contenedor normal sí llega a los dos. Si no llegara, la prueba no demostraría nada.
3. Aplica el rol con esos señuelos como destinos prohibidos. La prueba de aislamiento del rol tiene que pasar.
4. Lo aplica otra vez y exige `changed=0`.
