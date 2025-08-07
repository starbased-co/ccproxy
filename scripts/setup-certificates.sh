#!/bin/bash

# Setup mitmproxy certificates for system trust

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Setting up mitmproxy certificates${NC}"
echo "===================================="
echo ""

MITM_DIR="$HOME/.mitmproxy"
CERT_FILE="$MITM_DIR/mitmproxy-ca-cert.pem"

# Check if certificate exists
if [ ! -f "$CERT_FILE" ]; then
    echo -e "${YELLOW}Certificate not found. Generating...${NC}"
    mitmdump -s /dev/null &
    MITM_PID=$!
    sleep 3
    kill $MITM_PID 2>/dev/null || true
    
    if [ ! -f "$CERT_FILE" ]; then
        echo -e "${RED}Failed to generate certificate${NC}"
        exit 1
    fi
fi

echo "Certificate found at: $CERT_FILE"
echo ""

# Detect OS and install certificate
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Installing certificate on Arch Linux..."
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then 
        SUDO=""
    else
        SUDO="sudo"
    fi
    
    # For Arch Linux, install to the ca-certificates trust store
    # Arch uses /etc/ca-certificates/trust-source/anchors/ for custom certificates
    echo "Installing to Arch Linux trust store..."
    $SUDO cp "$CERT_FILE" /etc/ca-certificates/trust-source/anchors/mitmproxy-ca-cert.crt
    $SUDO trust extract-compat
    
    # Alternative method using update-ca-trust if available
    if command -v update-ca-trust &> /dev/null; then
        $SUDO update-ca-trust
    fi
    
    # Also add to Node.js extra CA if needed
    if command -v node &> /dev/null; then
        export NODE_EXTRA_CA_CERTS="$CERT_FILE"
        echo ""
        echo "For Node.js applications, add to your shell profile (~/.zshrc or ~/.bashrc):"
        echo "  export NODE_EXTRA_CA_CERTS=\"$CERT_FILE\""
    fi
    
    # For Chromium-based browsers on Arch
    if [ -d "$HOME/.pki/nssdb" ]; then
        echo ""
        echo "Adding to Chromium certificate store..."
        certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "mitmproxy" -i "$CERT_FILE" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ Certificate installed on Arch Linux${NC}"
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Installing certificate on macOS..."
    
    # Add to system keychain
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CERT_FILE"
    
    echo -e "${GREEN}✓ Certificate installed on macOS${NC}"
    
else
    echo -e "${YELLOW}Manual installation required for your OS${NC}"
    echo "Certificate location: $CERT_FILE"
fi

echo ""
echo "Next steps:"
echo "1. Restart any running applications (including Claude)"
echo "2. Test with: ./scripts/test-proxy-connection.sh"
echo "3. Run Claude with: ./scripts/claude-proxy.sh"