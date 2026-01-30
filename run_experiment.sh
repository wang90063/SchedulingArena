#!/bin/bash
#
# SchedulingArena Experiment Runner
# 
# Usage:
#   ./run_experiment.sh [config_file] [options]
#
# Examples:
#   ./run_experiment.sh examples/config_example.json
#   ./run_experiment.sh examples/config_example.json --output results/
#   ./run_experiment.sh  # Run default baseline experiments
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE=""
OUTPUT_DIR=""
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config|-c)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [config_file] [options]"
            echo ""
            echo "Options:"
            echo "  -c, --config FILE    Path to JSON config file"
            echo "  -o, --output DIR     Output directory for results (optional)"
            echo "  -v, --verbose        Verbose output"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 examples/config_example.json"
            echo "  $0 examples/config_example.json --output results/"
            echo "  $0  # Run default baseline experiments"
            exit 0
            ;;
        *)
            if [[ -z "$CONFIG_FILE" ]]; then
                CONFIG_FILE="$1"
            else
                echo -e "${RED}Error: Unknown option $1${NC}" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if scheduling-arena command exists
if ! command -v scheduling-arena &> /dev/null; then
    echo -e "${RED}Error: scheduling-arena command not found.${NC}" >&2
    echo "Please install the package first: pip install -e ." >&2
    exit 1
fi

# Print header
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SchedulingArena Experiment Runner${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Create output directory if specified
if [[ -n "$OUTPUT_DIR" ]]; then
    mkdir -p "$OUTPUT_DIR"
    echo -e "${YELLOW}Output directory: $OUTPUT_DIR${NC}"
    echo ""
fi

# Run experiments
if [[ -n "$CONFIG_FILE" ]]; then
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}" >&2
        exit 1
    fi
    
    echo -e "${YELLOW}Running experiments from: $CONFIG_FILE${NC}"
    echo ""
    
    if [[ -n "$OUTPUT_DIR" ]]; then
        # Redirect output to file if output directory is specified
        OUTPUT_FILE="$OUTPUT_DIR/experiment_$(date +%Y%m%d_%H%M%S).log"
        scheduling-arena --config "$CONFIG_FILE" 2>&1 | tee "$OUTPUT_FILE"
        echo ""
        echo -e "${GREEN}Results saved to: $OUTPUT_FILE${NC}"
    else
        scheduling-arena --config "$CONFIG_FILE"
    fi
else
    echo -e "${YELLOW}Running default baseline experiments...${NC}"
    echo ""
    
    if [[ -n "$OUTPUT_DIR" ]]; then
        OUTPUT_FILE="$OUTPUT_DIR/baseline_$(date +%Y%m%d_%H%M%S).log"
        scheduling-arena 2>&1 | tee "$OUTPUT_FILE"
        echo ""
        echo -e "${GREEN}Results saved to: $OUTPUT_FILE${NC}"
    else
        scheduling-arena
    fi
fi

echo ""
echo -e "${GREEN}Experiment completed!${NC}"
