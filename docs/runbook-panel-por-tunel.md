# Runbook: el panel de Pterodactyl por el túnel de Cloudflare

Hoy el panel entra por los puertos 80 y 443 del router con la IP de casa a la vista. Los demás servicios web ya salen por el túnel. Pasar también el panel permite cerrar 80 y 443 en el router.

Lo que **no** cambia: Wings (8080), su SFTP (2022) y los puertos de juego siguen entrando directos. El navegador abre la consola contra el nodo, no contra el panel, y los juegos necesitan la IP. El Wings local habla con el panel por `127.0.0.1` (entrada en `/etc/hosts`), así que tampoco le afecta.

La idea para no cortar nada: el camino viejo (router → nginx:443) se queda abierto hasta que el nuevo lleva días funcionando. Durante el cambio de DNS, quien tenga la IP vieja en caché sigue entrando por el router.

## Fase 0: certificados por DNS (sin corte)

Los certificados del panel y del nodo se crearon con el plugin nginx de certbot, que valida por el puerto 80. Cerrar el 80 rompería la siguiente renovación. Y el del nodo lo lee Wings solo al arrancar, así que tras renovar seguiría sirviendo el viejo hasta caducar.

- Rol `nginx`: `nginx_certbot_dns_certs` pasa esos certificados a DNS-01 con `certbot reconfigure` (hace una renovación de prueba y solo guarda el cambio si funciona) y `nginx_certbot_deploy_hooks` reinicia Wings cuando se renueva el suyo.
- Aplicar: `ansible-playbook playbooks/nginx.yml --diff`.
- Comprobar: `grep authenticator /etc/letsencrypt/renewal/*.conf` → todos `dns-cloudflare`; `certbot renew --dry-run` sin errores.

## Fase 1: IP real detrás del túnel (sin corte)

Por el túnel todas las peticiones llegan desde cloudflared, es decir, desde `127.0.0.1`. Sin más, el panel vería a todo el mundo con esa IP: el límite de intentos de login sería compartido y el registro de actividad no serviría. En el vhost del panel:

```nginx
set_real_ip_from 127.0.0.1;
set_real_ip_from ::1;
real_ip_header CF-Connecting-IP;
```

Solo se fía de la cabecera si la petición viene de la propia máquina. Lo que entra hoy por el router no se ve afectado. Se aplica con el mismo `nginx.yml`.

## Fase 2: probar el túnel con un nombre de prueba (sin corte)

En Cloudflare Zero Trust → Tunnels → el túnel → Public Hostname, añadir uno temporal:

- Hostname: `panel-prueba.<dominio>`
- Service: `https://localhost:443`
- Additional settings → TLS → Origin Server Name: el nombre del panel. HTTP Settings → HTTP Host Header: el nombre del panel.

Comprobar:

- `curl -sI https://panel-prueba.<dominio>/auth/login` → 200 de nginx/Laravel, no una página de Cloudflare.
- `curl -s -A "Pterodactyl Wings" https://panel-prueba.<dominio>/api/remote/servers` → un 401/403 en JSON del panel. Si sale un reto de Cloudflare (HTML), algo de Security (Bot Fight Mode, WAF) bloquearía a los nodos remotos: hay que arreglarlo antes de seguir.

Después, borrar el nombre de prueba.

## Fase 3: el cambio (corte = ninguno si se hace en este orden)

1. En DNS, borrar el registro A del panel (el que apunta a la IP de casa, nube gris).
2. En el túnel, añadir Public Hostname con el nombre del panel y los mismos ajustes de la fase 2. Cloudflare crea el CNAME al túnel con proxy.
3. Mientras caduca la caché del registro viejo (TTL), unos clientes entran por el túnel y otros por el router. Los dos caminos funcionan.

Comprobar:

- `nslookup <panel> 1.1.1.1` → IPs de Cloudflare.
- El panel carga y deja entrar.
- Admin → Nodes: todos con el corazón verde (el panel llega a los Wings; esto no ha cambiado).
- Los Wings remotos llegan al panel: entrar por SFTP a un servidor de cada nodo remoto (Wings valida el login contra el panel) o reiniciar uno y ver que el estado se actualiza.
- `/var/log/nginx/pterodactyl.app-error.log` sin errores nuevos.

**Vuelta atrás:** borrar el Public Hostname y volver a crear el A a la IP de casa (nube gris). El router sigue abierto, así que vuelve a funcionar en cuanto propaga.

## Fase 4: cerrar el router (cuando lleve días bien)

1. Livebox → NAT/PAT: quitar las reglas de 80 y 443.
2. ufw: 80 y 443 solo desde la LAN, porque nginx sigue sirviendo los vhosts de la LAN. El rol `ufw` solo añade reglas, así que las viejas se quitan a mano con `ufw delete allow 80/tcp` y lo mismo para 443, después de añadir las de la LAN en el inventario y aplicar `firewall.yml`.
3. Comprobar desde fuera (datos del móvil): `curl -m 5 http://<ip-de-casa>` tiene que fallar, y el panel tiene que seguir cargando.
