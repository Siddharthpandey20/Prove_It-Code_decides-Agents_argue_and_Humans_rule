# The sandbox every proof of concept runs in.
#
# One image per version of the target library, so the same PoC can be run
# against the vulnerable release and the patched one. Dependencies are
# installed at build time; at run time the container has no network, no
# secrets, a read-only filesystem and a small writable /tmp.
#
#   docker build --build-arg PYYAML_VERSION=5.3.1 -t proveit-target:vulnerable target/
#   docker build --build-arg PYYAML_VERSION=5.4   -t proveit-target:patched    target/
FROM python:3.9-slim

ARG PYYAML_VERSION
# PyYAML 5.4 has no ARM64 wheel and its source build needs Cython 0.x.
RUN test -n "$PYYAML_VERSION" \
    && pip install --no-cache-dir --disable-pip-version-check 'Cython<3' wheel \
    && pip install --no-cache-dir --disable-pip-version-check --no-build-isolation "pyyaml==${PYYAML_VERSION}" \
    && python -c "import yaml; print('pyyaml', yaml.__version__)"

COPY harness.py /harness/harness.py

# Never run a stranger's code as root.
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/harness/harness.py"]
