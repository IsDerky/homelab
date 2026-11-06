# Ansible

Roles para montar piezas del homelab:

- `base`: zona horaria, paquetes básicos y usuario de administración con sus claves SSH.
- `ssh`: `sshd_config` desde plantilla, solo con claves por defecto.
- `honeypot`: el mismo honeypot de [cowrie-honeypot](https://github.com/IsDerky/cowrie-honeypot), pero como rol en vez de `install.sh`.

## Uso

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp inventory.example.ini inventory.ini   # tu servidor y tus variables
ansible-playbook playbooks/base.yml --check --diff   # ver qué cambiaría
ansible-playbook playbooks/base.yml
```

Para muchas variables es más cómodo `group_vars/<grupo>.yml` que el inventario. Esa carpeta tampoco va a git.

El honeypot necesita en el servidor Docker con Compose v2, systemd e iptables.

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
