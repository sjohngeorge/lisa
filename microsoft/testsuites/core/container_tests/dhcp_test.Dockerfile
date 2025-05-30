# DHCP Test Container
# Contains all dependencies for DHCP testing without installing on the host

FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages for DHCP testing
RUN apt-get update && apt-get install -y \
    # DHCP clients and tools
    isc-dhcp-client \
    dhcpcd5 \
    # Network analysis tools
    tcpdump \
    iproute2 \
    net-tools \
    iputils-ping \
    dnsutils \
    # System tools
    systemd \
    procps \
    # Debugging tools
    strace \
    vim \
    less \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Add a test script for DHCP validation
COPY dhcp_test.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/dhcp_test.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]