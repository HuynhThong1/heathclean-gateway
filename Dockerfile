# The service is stateless and writes nothing to disk, so the image only needs
# the interpreter, five dependencies and `app/`.
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /srv

# Copied before `app/` so a code change does not reinstall dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Nothing here needs root, and a container that cannot write to its own image
# is one less thing to reason about.
RUN useradd --create-home --uid 10001 gateway
USER gateway

EXPOSE 8000

# No --reload: it watches the filesystem for a source tree that never changes
# in a built image, and a redeploy is a new container anyway.
#
# One worker is right for this workload. Every request spends its time awaiting
# a hosted model over HTTP, which async already overlaps; more workers would
# multiply memory without touching the bottleneck.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
