#!/bin/bash
# Build and push container images to registry
# This script shows how to prepare test containers for use with LISA

set -e

# Configuration - replace with your registry
REGISTRY_URL="${LISA_REGISTRY_URL:-myregistry.azurecr.io}"
REGISTRY_USERNAME="${LISA_REGISTRY_USERNAME}"
REGISTRY_PASSWORD="${LISA_REGISTRY_PASSWORD}"
IMAGE_PREFIX="lisa-tests"
VERSION="${VERSION:-v1.0.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building LISA test containers...${NC}"

# Function to build and push an image
build_and_push() {
    local dockerfile=$1
    local image_name=$2
    local context_dir=${3:-.}
    
    echo -e "${YELLOW}Building ${image_name}...${NC}"
    
    # Build the image
    docker build \
        -f "${dockerfile}" \
        -t "${image_name}:${VERSION}" \
        -t "${image_name}:latest" \
        "${context_dir}"
    
    # Tag for registry
    docker tag "${image_name}:${VERSION}" "${REGISTRY_URL}/${image_name}:${VERSION}"
    docker tag "${image_name}:latest" "${REGISTRY_URL}/${image_name}:latest"
    
    echo -e "${GREEN}Successfully built ${image_name}${NC}"
}

# Login to registry if credentials provided
if [ -n "${REGISTRY_USERNAME}" ] && [ -n "${REGISTRY_PASSWORD}" ]; then
    echo -e "${YELLOW}Logging into registry ${REGISTRY_URL}...${NC}"
    echo "${REGISTRY_PASSWORD}" | docker login "${REGISTRY_URL}" \
        --username "${REGISTRY_USERNAME}" --password-stdin
fi

# Build CPU test container
build_and_push \
    "cpu_test.Dockerfile" \
    "${IMAGE_PREFIX}/cpu" \
    "."

# Build DHCP test container
build_and_push \
    "dhcp_test.Dockerfile" \
    "${IMAGE_PREFIX}/dhcp" \
    "."

# Build network test container (example)
# build_and_push \
#     "network_test.Dockerfile" \
#     "${IMAGE_PREFIX}/network" \
#     "."

# Push to registry if logged in
if [ -n "${REGISTRY_USERNAME}" ]; then
    echo -e "${YELLOW}Pushing images to registry...${NC}"
    
    docker push "${REGISTRY_URL}/${IMAGE_PREFIX}/cpu:${VERSION}"
    docker push "${REGISTRY_URL}/${IMAGE_PREFIX}/cpu:latest"
    
    docker push "${REGISTRY_URL}/${IMAGE_PREFIX}/dhcp:${VERSION}"
    docker push "${REGISTRY_URL}/${IMAGE_PREFIX}/dhcp:latest"
    
    echo -e "${GREEN}Successfully pushed all images to ${REGISTRY_URL}${NC}"
else
    echo -e "${YELLOW}Skipping push - no registry credentials provided${NC}"
fi

# Print summary
echo -e "${GREEN}Build Summary:${NC}"
echo "- CPU Tests: ${IMAGE_PREFIX}/cpu:${VERSION}"
echo "- DHCP Tests: ${IMAGE_PREFIX}/dhcp:${VERSION}"

# Generate example LISA config
cat > container_test_config.yml <<EOF
# Example LISA configuration using pre-built containers
container_registry:
  url: ${REGISTRY_URL}
  username: \${LISA_REGISTRY_USERNAME}
  password: \${LISA_REGISTRY_PASSWORD}

test_containers:
  cpu: ${IMAGE_PREFIX}/cpu:${VERSION}
  dhcp: ${IMAGE_PREFIX}/dhcp:${VERSION}
EOF

echo -e "${GREEN}Generated container_test_config.yml${NC}"