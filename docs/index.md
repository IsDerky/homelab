# homelab

Cómo está montado mi servidor casero: qué corre, cómo se expone, cómo se hacen y se comprueban los backups, cómo me entero de que algo va mal y cómo se despliega. Es una máquina en casa y dos nodos en la nube, pero lo trato como si fuera producción, porque una parte lo es: aloja los servidores de juego de amigos y conocidos.

Aquí no hay IPs, dominios ni credenciales. La configuración está en [Ansible](ansible.md), con los valores y secretos en un repo privado. El código de cada pieza va en su propio repo: [cowrie-honeypot](https://github.com/IsDerky/cowrie-honeypot), [asistente-ops](https://github.com/IsDerky/asistente-ops) (recolector, bot y vigilante) y [oficina-pixel](https://github.com/IsDerky/oficina-pixel) (el panel).

## Máquinas

- **Servidor de casa.** Dell OptiPlex con un i5-8500 (6 núcleos), 38 GB de RAM y un SSD de 256 GB. Un SSD NVMe externo de 250 GB por USB-C (10 Gbps), con LVM: copia local de los backups y NAS. Ubuntu Server 24.04, sin escritorio.
- **Dos nodos en Oracle Cloud** (ARM, Ubuntu 22.04). Solo Docker y Wings: alojan servidores de juego y los gestiona el panel de casa. Se hablan con el servidor por un túnel WireGuard.

## Qué corre

| Servicio | Cómo | Se llega por |
|---|---|---|
| [App web propia](https://github.com/IsDerky/bentonime-showcase) (Next.js + SQLite) | systemd, usuario propio, solo loopback | Cloudflare Tunnel |
| Dos webs más (Next.js y Vite) | systemd encerrado y nginx en loopback | Cloudflare Tunnel |
| Pterodactyl (panel) | nginx + PHP-FPM + MariaDB + Redis | Cloudflare Tunnel |
| Wings (casa y los dos nodos) | binario con versión fija + Docker | Puertos del router / IP pública del nodo |
| code-server | usuario sin privilegios, detrás de un proxy con TOTP | Cloudflare Tunnel |
| AdGuard Home + Unbound | Docker Compose; Unbound resuelve desde los raíz y valida DNSSEC | Solo LAN (DNS y DoH) |
| Vaultwarden | Docker Compose, usuario propio, solo loopback | Solo LAN |
| Homepage | Docker Compose, iconos pixel-art propios | Solo LAN |
| Prometheus, Alertmanager, Grafana | Docker Compose con la red del host, solo loopback | Grafana solo LAN |
| Panel de estado y del honeypot | web estática + API local del bot | Solo LAN |
| Honeypot Cowrie | Docker, aislado con iptables | Puertos 22 y 23 del router |
| Bot de operaciones | Bun + discord.js, systemd con `ProtectSystem=strict` | Sale a Discord, no escucha |
| NAS | Samba (SMB3 cifrado) en el disco USB | Solo LAN |
| Runners de GitHub Actions | un runner por repo, usuario sin shell | Solo salida a GitHub |

Todo lo que es web y solo para casa tiene su propio nombre con HTTPS: un certificado comodín emitido por DNS-01, registros DNS que apuntan a la IP de la LAN y un `allow` de la red de casa en cada vhost.

## En esta web

- [Arquitectura](arquitectura.md): el diagrama y por dónde entra cada cosa.
- [Red y seguridad](red-y-seguridad.md): qué está abierto, el túnel con los nodos, el endurecimiento y cómo se midió.
- [Backups](backups.md): restic a Drive y a un disco local, y el simulacro de restauración mensual.
- [Vigilancia](vigilancia.md): el vigilante externo, el recolector, el bot y las métricas.
- [CI/CD](cicd.md): workflows comunes, despliegue sin dar poder al runner y Renovate.
- [Decisiones](decisiones.md): lo que elegí, lo que no y lo que queda.
- [Ansible](ansible.md): los roles uno a uno.
