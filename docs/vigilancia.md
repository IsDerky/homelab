# Vigilancia

Dos partes, para que un fallo del servidor no apague también el aviso.

## Vigilante externo

Un Cloudflare Worker con cron cada 5 minutos y KV. El servidor y los backups le mandan latidos. Si alguno no llega a tiempo, me escribe por Discord:

| Señal | Plazo |
|---|---|
| Servidor | 15 min |
| Backup del sistema | 13 h |
| Backup de los servidores de juego | 30 h |
| Simulacro de restauración | 40 días |

Avisa una vez al pasarse el plazo, recuerda cada 24 h y avisa cuando vuelve. El Worker, su KV y el cron están declarados en [Terraform](https://github.com/IsDerky/asistente-ops/tree/main/watchdog/terraform). Es el patrón *dead man's switch*: si el servidor muere entero, nadie mandaría el aviso desde dentro.

## Recolector y bot

**Recolector** (`ops-collect`, Python sin dependencias, timer cada 5 minutos). Junta en un JSON el estado del sistema, SMART, servicios, backups, `docker stats`, certificados, fail2ban y el honeypot. También procesa el journal y agrupa los mensajes de log por huella, para detectar lo que es nuevo.

**Bot de operaciones** (Discord, solo DMs y solo yo). Lee el JSON y responde a preguntas tipo "¿cómo van los backups?" usando un LLM con herramientas. Las acciones (reiniciar la app, lanzar un backup) solo se ejecutan con un botón que caduca a los 10 minutos: el modelo propone y yo confirmo. Manda un resumen diario por la mañana y lleva las caducidades de certificados y dominios.

## Métricas

Prometheus + Grafana ([rol `monitoring`](ansible.md#rol-monitoring)):

- node_exporter en el servidor y en los nodos (estos por el túnel);
- cAdvisor para el consumo de cada contenedor, también los de los servidores de juego;
- blackbox para comprobar las webs desde fuera del proceso y que los certificados no caduquen, Wings de los tres nodos incluido;
- un exportador propio en Python que convierte el JSON del recolector y el estado de los backups en métricas.

Dashboards: el servidor, todos los servicios, la operación (disponibilidad y backups), los servidores de juego y los nodos de fuera (con reinicios y parches pendientes).

Alertmanager solo avisa de lo que no cubre lo anterior: que la app falle lo bastante como para comerse su margen de error del mes (SLO del 99,5 %), disco o memoria a punto de acabarse en cualquier máquina, una copia local fallida o atrasada, un certificado a punto de caducar y que la propia monitorización deje de ver algo. Las reglas tienen tests con `promtool` en el CI.

## Qué me avisa y qué no

Solo lo que importa: servidor caído, backup fallido, alguien que inicia sesión, algo que caduca. Probé a avisar de anomalías en los logs y era ruido, así que el bot las aprende en silencio y me las cuenta solo si le pregunto. Los reinicios pendientes de los nodos tampoco avisan: se ven en el dashboard y reinicio cuando no corta partidas.
