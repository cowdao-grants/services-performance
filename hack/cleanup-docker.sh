#!/usr/bin/env bash
# Docker Cleanup Script for CoW Performance Testing Suite
#
# This script helps clean up accumulated Docker resources to free disk space.
# Run this periodically if you notice disk usage growing.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "════════════════════════════════════════════════════════════════"
echo " CoW Performance Testing Suite - Docker Cleanup"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Function to confirm action
confirm() {
    local message="$1"
    read -p "${message} (y/N): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Function to show disk usage
show_disk_usage() {
    echo "Current Docker disk usage:"
    docker system df
    echo ""
}

# Show current usage
show_disk_usage

echo "Cleanup Options:"
echo "  1. Stop containers (keeps images and volumes)"
echo "  2. Remove stopped containers"
echo "  3. Remove unused images"
echo "  4. Remove unused volumes (⚠️  data loss)"
echo "  5. Prune build cache"
echo "  6. Full cleanup (⚠️  removes everything except volumes)"
echo "  7. Nuclear option (⚠️  removes EVERYTHING including volumes)"
echo ""

# Option 1: Stop containers
if confirm "Stop all running containers?"; then
    echo "Stopping containers..."
    cd "$PROJECT_ROOT"
    docker-compose down
    echo "✓ Containers stopped"
    echo ""
fi

# Option 2: Remove stopped containers
if confirm "Remove stopped containers?"; then
    echo "Removing stopped containers..."
    docker container prune -f
    echo "✓ Stopped containers removed"
    echo ""
fi

# Option 3: Remove unused images
if confirm "Remove unused Docker images?"; then
    echo "Removing unused images..."
    docker image prune -f
    if confirm "  Also remove dangling images?"; then
        docker image prune -a -f
    fi
    echo "✓ Unused images removed"
    echo ""
fi

# Option 4: Remove unused volumes
if confirm "Remove unused Docker volumes? ⚠️  This may delete data!"; then
    echo "Removing unused volumes..."
    docker volume prune -f
    echo "✓ Unused volumes removed"
    echo ""
fi

# Option 5: Prune build cache
if confirm "Remove Docker build cache?"; then
    echo "Removing build cache..."
    docker builder prune -f
    if confirm "  Also remove all build cache (including in-use)?"; then
        docker builder prune -a -f
    fi
    echo "✓ Build cache removed"
    echo ""
fi

# Option 6: Full cleanup (except volumes)
if confirm "Perform full cleanup (containers, images, cache)? ⚠️  Requires rebuild"; then
    echo "Performing full cleanup..."
    cd "$PROJECT_ROOT"
    docker-compose down
    docker system prune -a -f
    echo "✓ Full cleanup complete"
    echo ""
fi

# Option 7: Nuclear option
if confirm "NUCLEAR: Remove EVERYTHING including volumes? ⚠️  ALL DATA WILL BE LOST!"; then
    if confirm "  Are you ABSOLUTELY sure? This cannot be undone!"; then
        echo "Performing nuclear cleanup..."
        cd "$PROJECT_ROOT"
        docker-compose down -v
        docker system prune -a -f --volumes
        echo "✓ Nuclear cleanup complete - all Docker data removed"
        echo ""
    fi
fi

# Show final usage
echo ""
echo "════════════════════════════════════════════════════════════════"
show_disk_usage

echo "Cleanup complete!"
echo ""
echo "Next steps:"
echo "  - Run 'docker-compose up -d' to restart services"
echo "  - First startup may be slower due to image pulling/building"
echo ""
