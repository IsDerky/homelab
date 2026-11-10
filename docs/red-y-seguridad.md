# Red y seguridad

## Qué está abierto

- **En el router**: la API y el SFTP de Wings, un rango para los juegos, el honeypot (22 y 23) y el UDP de WireGuard para el móvil. Nada más: ni web ni el SSH real.
- **En los nodos**: SSH (solo con clave), Wings, los juegos y el UDP de WireGuard.
- **ufw** deniega por defecto lo entrante y lo enrutado. SSH, web y NAS solo desde la red de casa. Ojo: lo que publica Docker no pasa por ufw. Por eso los contenedores propios usan la red del host escuchando en `127.0.0.1` (no se publica ningún puerto) y el honeypot se aísla con reglas en `DOCKER-USER`.

## Túnel con los nodos

WireGuard entre el servidor de casa y cada nodo. Los nodos tienen IP fija y escuchan. El servidor de casa no escucha: abre él la conexión y la mantiene viva con keepalive. Así en el router no se abre nada, y si cambia la IP de casa el túnel se rehace solo.

Por el túnel van las métricas: node-exporter en cada nodo escucha solo en su IP del túnel, y desde Internet ese puerto ni existe. Cada máquina genera su clave privada y no la saca de ahí: no pasa por Ansible ni por la plantilla.

## VPN para el móvil

Para usar desde fuera lo que solo está en la LAN (Vaultwarden, Grafana, la oficina…) sin publicarlo. El móvil es un peer más del mismo WireGuard, pero aquí sí escucha el servidor de casa, con el UDP reenviado en el router. Túnel partido: el móvil solo manda por él lo que va a la IP del servidor. Los nombres de la LAN tienen registro A público a esa IP privada, así que ni siquiera hace falta cambiarle el DNS.

ufw y los `allow` de nginx dejan pasar la IP del móvil, no toda la red del túnel: los nodos también están en ella y no tienen por qué ver la LAN. La clave privada se genera en el PC, pasa al móvil con un QR y se borra.

Algunas imágenes de Ubuntu de proveedores cloud traen un iptables propio con un `REJECT` al final, guardado en `rules.v4`. El rol mete sus reglas antes, en el fichero y en caliente, sin `netfilter-persistent save`, que guardaría también las reglas de Docker.

## Endurecimiento

- **Al empezar**: fuera escritorio, CUPS, VNC, ModemManager, snaps y servicios que no se usaban.
- **Usuarios por servicio**: cada app corre con su usuario. La app web solo puede reiniciar su propio servicio vía sudo. El bot solo puede lanzar dos acciones concretas mediante una regla de polkit.
- **SSH**: solo clave, desde la red de casa en el servidor, `MaxAuthTries 3`, `LogLevel VERBOSE`. En los nodos root solo entra con comando forzado (la copia de backups) y el resto con el usuario normal.
- **Rol `endurecimiento`**, después de una auditoría con Lynis: sysctl (redirecciones, `kptr_restrict`, BPF sin privilegios…), protocolos de red que no se usan fuera, sin core dumps, banners y paquetes a medio desinstalar purgados. Antes de aplicar cada punto comprobé si algo lo usaba.
- **Parches**: en los nodos, unattended-upgrades instala solo seguridad y nunca reinicia (cortaría las partidas). Docker y Wings quedan fuera. Si un parche pide reinicio, sale en el dashboard de los nodos.
- **fail2ban** con filtros propios para el SFTP de Wings, que es donde llegan los ataques de verdad: una jaula para usuarios que no existen (3 intentos y baneo creciente) y otra para fuerza bruta.
- **Correo**: los dominios que no mandan correo publican SPF `-all`, DMARC `reject` y una clave DKIM vacía. Así nadie puede hacerse pasar por ellos. DNSSEC activado en todos.

### Auditoría con Lynis

Lynis va en un playbook aparte (`auditoria.yml`), fuera de `site.yml`. Copia Lynis con su suma, lo ejecuta, se trae el informe y borra lo que ha dejado.

| Máquina | Antes | Después |
|---|---|---|
| Servidor de casa | 67 | 72 |
| Nodo 1 | 69 | 76 |
| Nodo 2 | 69 | 75 |

El servidor tiene menos porque sus avisos eran un reinicio pendiente por kernel y parches del día. Lo que queda son sobre todo sugerencias que no compensan aquí (AIDE, auditd, particiones separadas).

En la auditoría salió también lo que había que quitar: en un nodo seguía funcionando un panel de Pterodactyl antiguo que nadie usaba, con MariaDB abierta a Internet. Se copió, se apagó y se quitó por fases.

## Accesos

- **Aviso de inicio de sesión**: PAM llama a un script en cada sesión SSH y manda un DM, salvo desde mi PC. Es `optional`: si falla, no impide entrar.
- **Cuenta de auditoría de solo lectura**: entra solo con clave, solo desde mi PC, sin TTY ni reenvíos, y con sudo limitado a una lista de comandos con argumentos fijos (`ss`, `docker ps`, `ufw status`, `fail2ban-client status`…).
- **Contraseñas** en Vaultwarden, solo en la LAN, sin registro libre y con el panel de admin protegido por un hash argon2.
- **SMART** vigilado con smartd, con aviso por DM.
