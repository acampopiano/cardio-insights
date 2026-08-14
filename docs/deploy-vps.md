# Deploy en VPS con CI/CD (GitHub Actions)

Esta guía explica cómo preparar un servidor VPS (Ubuntu/Debian) para recibir los
deploys automáticos del workflow [`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml).

## Cómo funciona el pipeline

```
PR / push a develop o main
        │
        ├── backend-tests   (pytest, Python 3.12, cobertura 90%)
        └── frontend-tests  (eslint + vitest + build, Node 22, cobertura 90%)
                │
                └── deploy   (solo en push a main, si los tests pasan)
                        │
                        └── SSH al VPS → git pull → docker compose up -d --build
```

- Los **tests** corren en cada Pull Request y en cada push a `develop`/`main`.
- El **deploy** solo se ejecuta al hacer push/merge a `main` y únicamente si ambos
  jobs de test pasaron.
- El deploy se hace por SSH: el server hace `git reset --hard origin/main` y
  reconstruye los contenedores con [`docker-compose.prod.yml`](../docker-compose.prod.yml).

## 1. Preparar el servidor

Conectate por SSH al VPS como usuario con sudo y ejecutá:

```bash
# Instalar Docker + plugin compose (script oficial)
curl -fsSL https://get.docker.com | sudo sh

# Crear un usuario dedicado al deploy y darle acceso a Docker
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
```

## 2. Crear el par de claves SSH para GitHub Actions

En tu máquina local (no en el server) generá un par de claves **sin passphrase**
(las Actions no pueden escribir una passphrase interactiva):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f cardio_deploy_key
```

Esto crea `cardio_deploy_key` (privada) y `cardio_deploy_key.pub` (pública).

Instalá la clave **pública** en el server, en el usuario `deploy`:

```bash
# En el VPS
sudo mkdir -p /home/deploy/.ssh
sudo nano /home/deploy/.ssh/authorized_keys   # pegá el contenido de cardio_deploy_key.pub
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

La clave **privada** (`cardio_deploy_key`) se carga como secret en GitHub (paso 5).

## 3. Clonar el repositorio en el server

Como usuario `deploy`:

```bash
sudo su - deploy
git clone https://github.com/<org>/<repo>.git ~/cardio-insights
cd ~/cardio-insights
```

La ruta resultante (ej. `/home/deploy/cardio-insights`) es el valor del secret
`DEPLOY_PATH`.

> Si el repo es privado, usá un [deploy key de solo lectura](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
> o un token para poder hacer `git pull` sin credenciales interactivas.

## 4. Crear el archivo de entorno de producción

El backend lee sus variables desde `backend/.env` (nunca se commitea). Copiá el
ejemplo y completá los valores reales:

```bash
cd ~/cardio-insights
cp backend/.env.example backend/.env
nano backend/.env
```

Valores a ajustar para producción:

- `ENVIRONMENT=production` y `DEBUG=false`
- `JWT_SECRET_KEY` → generar uno fuerte: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `REPOSITORY_BACKEND=mysql`
- `MYSQL_HOST=mysql` (nombre del servicio en compose) y credenciales
- `METABASE_SITE_URL=http://<IP-o-dominio>:3000` y `METABASE_SECRET_KEY`
- `CHAT_ENABLED` / `OPENAI_API_KEY` según se use el asistente

Si querés sobrescribir las credenciales de MySQL/Metabase que usa compose, podés
crear también un `.env` en la raíz del repo con `MYSQL_ROOT_PASSWORD`,
`MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` y `VITE_API_URL` (compose los lee
automáticamente).

## 5. Configurar los secrets en GitHub

En el repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Descripción | Ejemplo |
|--------|-------------|---------|
| `SSH_HOST` | IP o dominio del VPS | `203.0.113.10` |
| `SSH_USER` | Usuario de deploy | `deploy` |
| `SSH_PRIVATE_KEY` | Contenido completo de `cardio_deploy_key` (clave privada) | `-----BEGIN OPENSSH PRIVATE KEY----- ...` |
| `SSH_PORT` | Puerto SSH (opcional, default 22) | `22` |
| `DEPLOY_PATH` | Ruta del repo clonado en el server | `/home/deploy/cardio-insights` |

## 6. Abrir puertos en el firewall

```bash
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # Frontend (nginx)
sudo ufw allow 3000/tcp   # Metabase (opcional, solo si se expone)
sudo ufw enable
```

El backend no expone puerto público: se accede a través del proxy `/api/` de
nginx en el frontend.

## 7. Primer deploy manual (verificación)

Antes de confiar en el pipeline, probá el build en el server:

```bash
cd ~/cardio-insights
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Verificá:

- Frontend: `http://<IP-o-dominio>/`
- API vía proxy: `http://<IP-o-dominio>/api/v1/health` (o `/docs`)
- Metabase (si se expuso): `http://<IP-o-dominio>:3000`

## 8. Probar el pipeline completo

1. Abrí un Pull Request → deberían correr `backend-tests` y `frontend-tests`.
2. Mergeá a `main` → se ejecuta el job `deploy` por SSH y reconstruye los contenedores.
3. Revisá los logs del deploy en la pestaña **Actions** del repo.

## Notas

- El deploy usa `git reset --hard origin/main`: cualquier cambio local no
  commiteado en el server (excepto archivos ignorados como `backend/.env`) se
  descarta. Mantené la config sensible solo en archivos gitignoreados.
- Los tests de integración con MySQL (`RUN_INTEGRATION_DB_TESTS=1`) no corren en
  CI por defecto; los unitarios usan `REPOSITORY_BACKEND=mock`.
- Para agregar HTTPS, poné un reverse proxy con TLS (Caddy, Traefik o nginx con
  certbot) delante del contenedor `frontend`.
