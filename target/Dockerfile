# The sandbox every proof of concept runs in.
#
# One image per version of the target library, so the same payload can be
# run against the vulnerable release and the patched one. Dependencies are
# installed at build time; at run time the container has no network, no
# secrets, a read-only filesystem and a small writable /tmp.
#
#   docker build --build-arg PYYAML_VERSION=5.3.1 -t proveit-target:vulnerable target/
#   docker build --build-arg PYYAML_VERSION=5.4   -t proveit-target:patched    target/
#
# Python 3.9 is end of life. It is used on purpose: the image exists to hold
# an intentionally old library (PyYAML 5.3.1 is from 2020) inside an isolated
# container, and it is pinned by digest so every build is the same image.
FROM python:3.9-slim@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b

ARG PYYAML_VERSION
RUN test -n "$PYYAML_VERSION" \
    && pip install --no-cache-dir --disable-pip-version-check "pyyaml==${PYYAML_VERSION}" \
    && python -c "import yaml; print('pyyaml', yaml.__version__)"

COPY harness.py child.py /harness/

# Never run a stranger's input as root.
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/harness/harness.py"]
