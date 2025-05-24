#!/usr/bin/env bash
# DocVault installation helper script
# This script helps set up the 'dv' command for easy access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the absolute path to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
VENV_DV="$PROJECT_DIR/.venv/bin/dv"

echo -e "${BLUE}DocVault Installation Helper${NC}"
echo "=============================="
echo ""

# Check if .venv/bin/dv exists
if [ ! -f "$VENV_DV" ]; then
    echo -e "${RED}Error: DocVault is not installed in the virtual environment.${NC}"
    echo "Please run 'uv pip install -e .' or 'pip install -e .' first."
    exit 1
fi

echo -e "${GREEN}Found DocVault at: $VENV_DV${NC}"
echo ""

# Detect shell
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    bash)
        RC_FILES=("$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile")
        ;;
    zsh)
        RC_FILES=("$HOME/.zshrc" "$HOME/.zprofile")
        ;;
    fish)
        RC_FILES=("$HOME/.config/fish/config.fish")
        ;;
    *)
        echo -e "${YELLOW}Warning: Unsupported shell '$SHELL_NAME'${NC}"
        RC_FILES=("$HOME/.profile")
        ;;
esac

# Find the appropriate RC file
RC_FILE=""
for file in "${RC_FILES[@]}"; do
    if [ -f "$file" ]; then
        RC_FILE="$file"
        break
    fi
done

if [ -z "$RC_FILE" ]; then
    RC_FILE="${RC_FILES[0]}"
    echo -e "${YELLOW}No shell configuration file found. Will create: $RC_FILE${NC}"
fi

echo "Choose installation method:"
echo "1) Add alias to shell configuration (recommended)"
echo "2) Create wrapper script in ~/bin"
echo "3) Create wrapper script in /usr/local/bin (requires sudo)"
echo "4) Show manual instructions"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        # Add alias to shell configuration
        ALIAS_LINE="alias dv='$VENV_DV'"
        
        # Check if alias already exists
        if grep -q "alias dv=" "$RC_FILE" 2>/dev/null; then
            echo -e "${YELLOW}An alias for 'dv' already exists in $RC_FILE${NC}"
            read -p "Do you want to update it? (y/n): " update
            if [ "$update" = "y" ] || [ "$update" = "Y" ]; then
                # Remove old alias
                sed -i.bak "/alias dv=/d" "$RC_FILE"
                echo "" >> "$RC_FILE"
                echo "# DocVault command" >> "$RC_FILE"
                echo "$ALIAS_LINE" >> "$RC_FILE"
                echo -e "${GREEN}✓ Updated alias in $RC_FILE${NC}"
            else
                echo "Keeping existing alias."
            fi
        else
            echo "" >> "$RC_FILE"
            echo "# DocVault command" >> "$RC_FILE"
            echo "$ALIAS_LINE" >> "$RC_FILE"
            echo -e "${GREEN}✓ Added alias to $RC_FILE${NC}"
        fi
        
        echo ""
        echo "To use the 'dv' command, either:"
        echo "  1. Restart your terminal, or"
        echo "  2. Run: source $RC_FILE"
        ;;
        
    2)
        # Create wrapper in ~/bin
        mkdir -p "$HOME/bin"
        WRAPPER_PATH="$HOME/bin/dv"
        
        cat > "$WRAPPER_PATH" << EOF
#!/usr/bin/env bash
# DocVault wrapper script
exec "$VENV_DV" "\$@"
EOF
        
        chmod +x "$WRAPPER_PATH"
        echo -e "${GREEN}✓ Created wrapper script at $WRAPPER_PATH${NC}"
        
        # Check if ~/bin is in PATH
        if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
            echo ""
            echo -e "${YELLOW}Note: $HOME/bin is not in your PATH.${NC}"
            echo "Add this line to your $RC_FILE:"
            echo '  export PATH="$HOME/bin:$PATH"'
        fi
        ;;
        
    3)
        # Create wrapper in /usr/local/bin
        WRAPPER_PATH="/usr/local/bin/dv"
        
        echo "Creating wrapper script at $WRAPPER_PATH (requires sudo)..."
        sudo tee "$WRAPPER_PATH" > /dev/null << EOF
#!/usr/bin/env bash
# DocVault wrapper script
exec "$VENV_DV" "\$@"
EOF
        
        sudo chmod +x "$WRAPPER_PATH"
        echo -e "${GREEN}✓ Created wrapper script at $WRAPPER_PATH${NC}"
        echo "The 'dv' command should now be available system-wide."
        ;;
        
    4)
        # Show manual instructions
        echo ""
        echo "Manual Installation Instructions:"
        echo "================================="
        echo ""
        echo "Option 1 - Add an alias (recommended):"
        echo "  Add this line to your shell configuration file ($RC_FILE):"
        echo "    alias dv='$VENV_DV'"
        echo ""
        echo "Option 2 - Create a wrapper script:"
        echo "  Create a file at ~/bin/dv or /usr/local/bin/dv with:"
        echo "    #!/usr/bin/env bash"
        echo "    exec \"$VENV_DV\" \"\$@\""
        echo "  Then make it executable:"
        echo "    chmod +x <path-to-script>"
        echo ""
        echo "Option 3 - Use the direct path:"
        echo "  $VENV_DV"
        ;;
        
    *)
        echo -e "${RED}Invalid choice. Exiting.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Installation helper completed!${NC}"
echo ""
echo "Next steps:"
echo "  1. Initialize the database: dv init-db"
echo "  2. Add your first document: dv add <url>"
echo "  3. Search documents: dv search <query>"