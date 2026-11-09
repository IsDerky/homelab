# CI/CD

Push a `main` = despliegue.

## Workflows comunes

Los repos usan los mismos workflows reutilizables (`workflow_call`) de [IsDerky/ci](https://github.com/IsDerky/ci), versionados con `@v1`:

- `app-node.yml`: instalar, lint, tipos, tests y build, con bun, npm o pnpm;
- `imagen.yml`: build de la imagen de Docker, prueba de humo y, si se pide, publicación en GHCR;
- `deploy.yml`: el despliegue en el servidor (abajo);
- `ansible.yml`: ansible-lint;
- `actionlint.yml`: los propios workflows.

Cada repo se queda con un workflow de pocas líneas. Un arreglo en el común llega a todos moviendo la etiqueta `v1`.

## Despliegue sin dar poder al runner

- Un runner autoalojado por repo, con un usuario `deployer` sin shell.
- Lo único que `deployer` puede hacer con sudo es `deploy-repo <repo> <sha>`.
- `deploy-repo` no usa el código del runner: se trae el repo con una deploy key de solo lectura y solo instala commits que ya estén en `origin/main`. Si alguien tomara el runner, solo podría desplegar lo que ya está publicado, no colar código propio como root.

## La app web, por versiones

1. CI en GitHub: lint, tipos, migraciones contra una BD vacía, tests y build.
2. En el servidor: `git worktree` en `releases/<sha>`, build con una BD desechable, backup de la SQLite, migraciones, cambio atómico del enlace `current` y reinicio.
3. Health check. Si falla, rollback automático a la versión anterior. Se guardan 3 versiones.
4. Aviso por Discord con el resultado.

## Dependencias

Renovate, con un preset común en el repo de CI: los lunes temprano, como mucho 5 PRs, las actions agrupadas y las imágenes de Docker agrupadas por minor/patch.

En este repo vigila las imágenes fijadas en los `defaults` de los roles (Prometheus, Grafana, AdGuard, Vaultwarden…) y los binarios que se bajan con versión y suma fija (restic, rclone, Wings, Lynis). Para estos últimos, un workflow pone en el mismo PR las sumas SHA-256 nuevas, así que el PR llega listo. Wings solo se actualiza cuando lo pido desde el dashboard de Renovate: va a los nodos y tiene que casar con el panel.
