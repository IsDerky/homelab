# Runbook: traer las webs del VPS al servidor de casa

El VPS no se renueva. De todo lo que tenía solo se traen dos webs:

| Web | Qué es | En el servidor |
|---|---|---|
| Estática | Vite (SPA), antes con `serve` en PM2 | nginx en `127.0.0.1:8084`, vhost `hosting-derkyu` |
| Next.js | Next 15 + puppeteer, antes en PM2 como root | `roninfc.service` en `127.0.0.1:3051` |

Lo demás (proxys viejos, una app de 2024, el panel del VPS, FTP, correo local) se deja morir sin copia. Ninguna de las dos webs usa base de datos, así que no hay datos que mover: solo código, y ese ya lo publica el CI.

## Cómo está montado

- **Código**: cada push a `main` lo compila un usuario sin privilegios (`webbuild`) y lo publica `deploy-repo` como una versión nueva (`releases/<sha>` + enlace `current`). Funciona aunque la web esté apagada, así que el código del servidor siempre es el último.
- **Configuración**: Ansible. El vhost va en `nginx_sites` con `enabled: false` y el servicio en el rol `roninfc` con `roninfc_enabled: false`. Todo instalado, nada escuchando.
- **Entrada**: Cloudflare Tunnel. Ninguna de las dos abre puertos en el router; escuchan solo en loopback.
- **El corte es DNS**: mientras el dominio apunte al VPS, la web sigue allí. Cuando pasa a ser una ruta del túnel, entra por casa. Volver atrás es deshacer ese cambio.

Encender en el servidor y cambiar el DNS son pasos separados a propósito: la web puede estar encendida y probada en casa sin recibir tráfico.

## Antes del corte

1. CI en verde y la versión publicada igual al último commit de `main`:
   ```bash
   gh api repos/<usuario>/<repo>/commits/main --jq .sha
   readlink -f /srv/roninfc/current   # o /var/www/hosting-derkyu
   ```
2. El servidor está como dice Ansible: `ansible-playbook playbooks/site.yml --check` sin cambios.
3. Hay backup reciente del sistema (el vigilante no ha avisado).

## Corte de la web estática (primero: es la de menos riesgo)

1. En el inventario, `enabled: true` en el vhost `hosting-derkyu` y:
   ```bash
   ansible-playbook playbooks/nginx.yml
   ```
   El rol pasa `nginx -t`, recarga y comprueba que una ruta inventada devuelve el `index.html` (200). Eso demuestra a la vez que nginx sirve la versión publicada y que el fallback de la SPA funciona.
2. En Cloudflare, para cada dominio de la web:
   - DNS: borrar el registro A que apunta al VPS.
   - Túnel → Public Hostnames → añadir el dominio con servicio `http://localhost:8084`. Cloudflare crea solo el CNAME al túnel.
3. Comprobar:
   ```bash
   curl -sI https://<dominio>/          # 200
   tail -f /var/log/nginx/hosting-derkyu.access.log   # llegan las visitas
   ```

**Vuelta atrás**: quitar los Public Hostnames, volver a poner el registro A al VPS y `enabled: false` + `nginx.yml`.

## Corte de la web Next.js

1. En el inventario, `roninfc_enabled: true` y:
   ```bash
   ansible-playbook playbooks/webs.yml
   ```
   El rol se niega a encenderla si el CI no ha publicado ninguna versión. Después la arranca y espera a que `/api/partidos` devuelva datos de verdad, no solo un 200 (esa ruta hace scraping con Chrome, así que prueba que puppeteer funciona dentro del encierro de systemd).
2. En Cloudflare:
   - DNS: borrar el registro A del dominio raíz.
   - Túnel → Public Hostnames → el dominio raíz con servicio `http://localhost:3051`.
   - `www`: sin ruta en el túnel. Una Redirect Rule "www a raíz" (301) y un registro `www` con proxy (AAAA `100::` vale; nunca recibe tráfico, solo sirve para que Cloudflare aplique la regla).
3. Comprobar:
   ```bash
   curl -s https://<dominio>/api/partidos | head -c 200
   journalctl -u roninfc -f
   systemctl show roninfc -p MemoryCurrent   # límite: 1536M
   ```

A partir de aquí, cada push a `main` reinicia el servicio. Si la versión nueva no responde, `deploy-repo` vuelve a la anterior.

**Vuelta atrás**: quitar el Public Hostname, volver a poner el registro A al VPS y `roninfc_enabled: false` + `webs.yml`.

## Después

- Dejarlo una semana mirando logs y memoria antes de dar el VPS por perdido.
- Quitar la cuenta de solo lectura del VPS de `~/.ssh/config`.
- No hay nada más que copiar: lo que no está en esta lista se decidió dejarlo morir.

## Por qué así

- **Ansible y no un script.** Antes había un script bash (`migracion-vps instalar | activar | desactivar`). Funcionaba, pero era una pieza más fuera del inventario: si el servidor se reconstruye con `site.yml`, las webs tienen que volver solas. Ahora encender o apagar una web es cambiar una variable, y se ve en el historial del repo de configuración.
- **Comprobar datos y no solo un 200.** Una web de Next que no consigue lanzar Chrome devuelve 200 con la lista vacía. La prueba tiene que fallar en ese caso.
- **systemd en vez de PM2.** El resto del servidor ya va con systemd, que además pone el encierro (`ProtectSystem=strict`, usuario propio, `MemoryMax`) que PM2 no da. En el VPS la web corría como root.
- **Túnel en vez de abrir puertos.** Es el mismo camino que ya usa la app principal del servidor. Cloudflare pone el HTTPS y no hay que gestionar certificados para estos dominios.
