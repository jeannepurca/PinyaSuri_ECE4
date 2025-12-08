#!/bin/bash
# PinyaSuri Startup Script
# Convenient script to run the system with proper environment

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           PinyaSuri Drone System Launcher             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "pinyasuri_env" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv pinyasuri_env
    source pinyasuri_env/bin/activate
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Setup complete${NC}"
else
    # Activate virtual environment
    source pinyasuri_env/bin/activate
fi

# Run system check
echo -e "\n${BLUE}Running system checks...${NC}"
python3 system_check.py

if [ $? -ne 0 ]; then
    echo -e "\n${RED}✗ System check failed${NC}"
    echo -e "${YELLOW}Please fix the issues above before running${NC}"
    exit 1
fi

# Menu
echo -e "\n${BLUE}Select mode:${NC}"
echo "1) Test Flight (ground testing)"
echo "2) Real Mission (main_improved.py)"
echo "3) Original Main (main.py)"
echo "4) Exit"
echo -n "Choice [1-4]: "
read choice

case $choice in
    1)
        echo -e "\n${GREEN}Starting test flight...${NC}"
        python3 test_flight.py
        ;;
    2)
        echo -e "\n${GREEN}Starting real mission...${NC}"
        echo -e "${YELLOW}Make sure mission is uploaded to Pixhawk!${NC}"
        sleep 2
        python3 main_improved.py
        ;;
    3)
        echo -e "\n${GREEN}Starting original main...${NC}"
        echo -e "${YELLOW}Make sure mission is uploaded to Pixhawk!${NC}"
        sleep 2
        python3 main.py
        ;;
    4)
        echo -e "${BLUE}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Deactivate on exit
deactivate
