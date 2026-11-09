# Decisiones

- **Una máquina, sin Kubernetes.** systemd y Docker Compose cubren lo que necesito con mucha menos complejidad. Cada servicio es una unidad con su usuario y sus límites.
- **Un solo disco interno.** Lo cubren los backups fuera de casa cada 6 h, los simulacros mensuales y una segunda copia en un SSD externo por USB (3-2-1: tres copias, dos soportes, una fuera).
- **Google Drive como destino de backups.** Ya tenía el espacio pagado y restic cifra antes de subir, así que el proveedor no ve nada. La app OAuth de rclone solo tiene acceso a los ficheros que crea ella.
- **Cloudflare Tunnel para lo público.** No abro puertos web y Cloudflare filtra por delante. El precio es depender de un tercero para esos servicios. Lo que no puede ir por el túnel (Wings, juegos) va directo.
- **WireGuard con los nodos, abierto desde casa.** Los nodos tienen IP fija y escuchan; casa conecta saliendo. Así no hay que abrir nada en el router ni depender de que no cambie la IP de casa.
- **Vaultwarden solo en la LAN.** Fuera de casa las apps de Bitwarden siguen funcionando con su copia local y sincronizan al volver. Exponerlo a Internet sería más cómodo, pero no compensa para un gestor de contraseñas.
- **Configuración en Ansible** ([roles](ansible.md)). Empezó como scripts en bash idempotentes: para una máquina funcionaban, pero reconstruirla desde cero costaba. Ahora casi todo son roles, y `site.yml` aplica el servidor entero (una segunda pasada da `changed=0`). Los valores y secretos van en un repo privado con Ansible Vault. Cada rol nuevo se prueba antes en contenedores con systemd, y el honeypot se prueba en el CI aplicándolo de verdad sobre el runner.
- **Jenkins no como CI central.** Lo probé en un proyecto, pero aquí comería RAM en la misma máquina que los servidores de juego, y GitHub Actions con workflows reutilizables hace lo mismo sin mantener nada.
- **El bot no tiene poder propio.** Todo lo que puede hacer está en una lista blanca con permisos mínimos (polkit o sudoers con argumentos fijos) y necesita mi clic.

## Pendiente

- Reconstruir el servidor en una VM vacía solo con `site.yml`, para probar que de verdad basta.
- Pasar a Ansible lo que todavía va a mano: los runners de CI y el panel de Pterodactyl.
- Traer a casa el CtrlPanel que sigue en uno de los nodos.
