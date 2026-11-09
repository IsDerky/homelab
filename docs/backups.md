# Backups

restic sobre rclone a Google Drive, y una segunda copia en el disco USB. Todo se cifra en el servidor antes de salir. Un script (`server-backup`) con varios modos, cada uno con su timer de systemd:

| Modo | Cuándo | Qué hace | Retención |
|---|---|---|---|
| `sistema` | Cada 6 h | BDs SQLite con `sqlite3 .backup` (la app y Vaultwarden), dump del panel, `/etc`, `/opt`, scripts, crons | 7 días enteros, 4 semanales, 12 mensuales |
| `clientes` | A diario | Volúmenes y backups de los servidores de juego, también los de los nodos | 7 diarios, 4 semanales, 3 mensuales |
| `nas` | A diario | La carpeta del NAS, solo a Drive (en local estaría en el mismo disco) | 7 diarios, 4 semanales, 6 mensuales |
| `mantenimiento` | Domingos | `prune` y `check` de una cuarta parte en Drive; en local, `check --read-data` completo | — |
| `simulacro` | Primer domingo de mes | Restaura en `/var/tmp` y comprueba que lo restaurado sirve | — |

Los volúmenes de los servidores de juego se copian como ficheros desde el host, sin ejecutar nada dentro de ellos. Es una copia "como si se fuera la luz" (crash-consistent); por eso se guardan varias versiones.

## Los nodos

Los nodos no guardan ni la contraseña de restic ni el acceso a Drive. Es el servidor de casa el que tira de ellos: en cada nodo, root tiene su clave con `restrict,command="rrsync -ro /var/lib/pterodactyl"`. Con ella no hay shell ni reenvíos, y solo se puede leer esa carpeta. Además de los volúmenes se trae la config de Wings y un JSON con el estado del sistema, que deja cada 6 h un timer del nodo. Si un nodo no responde, la copia sigue con los demás y avisa.

## Copia local

`sistema` y `clientes` hacen después la misma copia en un repo restic del disco USB, en un proceso aparte. Si el disco no está o falla, la copia de Drive ya está hecha y no se marca como fallida. La carcasa USB no deja leer el SMART, así que la salud de ese disco se comprueba con el `check --read-data` semanal.

Cada copia deja su resultado en un JSON (si fue bien, cuándo, la antigüedad máxima aceptable). Un exportador lo convierte en métricas y Prometheus avisa si una copia local falla o si alguna se queda atrás.

## El simulacro

Un backup que nunca se ha restaurado no es un backup. Cada mes el simulacro restaura los volcados en `/var/tmp` y comprueba:

- `integrity_check` y que haya filas en las BDs SQLite;
- que el dump del panel esté completo y tenga sus tablas;
- un fichero cualquiera de un servidor de juego, leído entero desde Drive, con el tamaño que dice el índice.

Su resultado también se vigila: si pasan 40 días sin un simulacro bueno, avisa el vigilante externo ([Vigilancia](vigilancia.md)).
