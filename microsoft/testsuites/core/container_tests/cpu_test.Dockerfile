# CPU Test Container - Pre-built with all dependencies
# Build once, push to registry, use everywhere

FROM ubuntu:22.04

LABEL maintainer="LISA Team"
LABEL description="Pre-built CPU testing container with all dependencies"

ENV DEBIAN_FRONTEND=noninteractive

# Install all CPU testing dependencies at build time
RUN apt-get update && apt-get install -y \
    # Basic tools
    procps \
    coreutils \
    util-linux \
    # CPU information tools
    cpuid \
    dmidecode \
    hwloc \
    numactl \
    # Stress testing tools
    stress-ng \
    cpuburn \
    # Performance tools
    linux-tools-generic \
    sysstat \
    # Build tools for custom tests
    gcc \
    make \
    # Monitoring tools
    htop \
    dstat \
    # Python for test scripts
    python3 \
    python3-pip \
    # Debugging tools
    strace \
    gdb \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for test automation
RUN pip3 install --no-cache-dir \
    psutil \
    numpy \
    pytest \
    pyyaml

# Copy pre-built test scripts and tools
COPY cpu_tests/ /opt/cpu_tests/
COPY scripts/cpu_validation.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/cpu_validation.sh

# Copy custom CPU testing binaries if any
# COPY bin/custom_cpu_test /usr/local/bin/

# Set up test directories
RUN mkdir -p /workspace /results

# Environment variables for tests
ENV TEST_DIR=/opt/cpu_tests
ENV RESULT_DIR=/results

WORKDIR /workspace

# Health check to verify container is ready
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD which stress-ng && which cpuid || exit 1

# Default command shows available tests
CMD ["ls", "-la", "/opt/cpu_tests/"]