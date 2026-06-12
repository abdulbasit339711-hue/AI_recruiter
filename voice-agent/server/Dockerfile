FROM dailyco/pipecat-base:latest

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Uncomment if you wish to print a summary of the features available in the base image
# ENV PCC_LOG_FEATURES_SUMMARY=true

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy the application code
COPY ./local_bot.py local_bot.py
COPY ./runner.py runner.py

# NOTE: secrets are NOT baked into the image. Inject them at runtime instead, e.g.
#   docker run --env-file .env ...           (compose: `env_file:` / `environment:`)
# or a secrets manager. `.env` is also excluded via .dockerignore so it can never be
# copied into a layer (where `docker history` / image pulls would expose it).