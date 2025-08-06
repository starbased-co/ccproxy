#!/usr/bin/env zsh

# Get the directory of this script
SCRIPT_DIR="${0:A:h}"

# Check if test-convo.txt exists
if [[ ! -f "$SCRIPT_DIR/test-convo.txt" ]]; then
    echo "Error: test-convo.txt not found in $SCRIPT_DIR"
    exit 1
fi

# Read the prompts from the file into an array (skip empty lines)
prompts=()
while IFS= read -r line; do
    if [[ -n "$line" ]]; then
        prompts+=("$line")
    fi
done < "$SCRIPT_DIR/test-convo.txt"

# Check if we have at least 3 prompts
if [[ ${#prompts[@]} -lt 3 ]]; then
    echo "Error: Need at least 3 prompts in test-convo.txt, found ${#prompts[@]}"
    exit 1
fi

echo "Starting automated Claude conversation test..."
echo "Will send 3 prompts from test-convo.txt"
echo "----------------------------------------"

# Create a temporary directory for the test
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
echo "Working directory: $TEST_DIR"
echo "----------------------------------------"

# Create an expect script for automating the conversation
cat > automated_conversation.exp << 'EOF'
#!/usr/bin/expect -f

set timeout 30
set script_dir [lindex $argv 0]

# Read prompts from file
set fp [open "$script_dir/test-convo.txt" r]
set prompts {}
while {[gets $fp line] >= 0} {
    if {[string length $line] > 0} {
        lappend prompts $line
    }
}
close $fp

# Start claude-mitm.zsh
spawn $script_dir/claude-mitm.zsh

# Set up logging for debugging
log_user 1

# Initial wait for any output
sleep 2

# Wait for and handle the security prompt first
expect {
    timeout { 
        puts "Timeout waiting for security prompt"
        exit 1
    }
    -re "Do you trust the files.*Yes.*proceed.*No.*exit.*Enter to confirm.*Esc to exit" {
        puts "\nDetected security prompt - sending '1' for Yes"
        send "1"
        expect {
            "Enter to confirm" {
                puts "Sending Enter to confirm"
                send "\r"
            }
            timeout {
                puts "Timeout waiting for Enter prompt"
                send "\r"
            }
        }
    }
}

# Wait for Claude to be ready - increased timeout for longer waits
set timeout 180

# Clear the screen and wait for the prompt to stabilize
sleep 5

# Send first 3 prompts with longer delays to ensure processing
for {set i 0} {$i < 3 && $i < [llength $prompts]} {incr i} {
    set prompt [lindex $prompts $i]
    set turn [expr $i + 1]
    
    puts "\n\nTurn $turn: Sending prompt: $prompt"
    puts "----------------------------------------"
    
    # Send the prompt
    send "$prompt\r"
    
    # Wait longer for Claude to process and respond
    # First prompt may take longer due to initialization
    if {$i == 0} {
        sleep 30
    } else {
        sleep 25
    }
    
    puts "----------------------------------------"
}

# Exit Claude
puts "\nSending exit command..."
send "/exit\r"
expect {
    timeout { puts "Timeout during exit" }
    eof { puts "Claude exited" }
}

wait
EOF

chmod +x automated_conversation.exp

# Check if expect is installed
if ! command -v expect &> /dev/null; then
    echo "Error: 'expect' is not installed. Please install it first."
    echo "On Ubuntu/Debian: sudo apt-get install expect"
    echo "On macOS: brew install expect"
    echo "On Arch: sudo pacman -S expect"
    exit 1
fi

# Run the expect script
expect automated_conversation.exp "$SCRIPT_DIR"

# Show captured files
echo -e "\nCaptured files:"
ls -la *_request.txt *_response.txt 2>/dev/null || echo "No request/response files found"

# Copy files to a directory in the original working directory
OUTPUT_DIR="$OLDPWD/mitm_captures_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# Copy all request and response files
if ls *_request.txt *_response.txt 2>/dev/null 1>&2; then
    cp *_request.txt *_response.txt "$OUTPUT_DIR/" 2>/dev/null
    echo -e "\nFiles copied to: $OUTPUT_DIR"
    echo "Contents:"
    ls -la "$OUTPUT_DIR"
else
    echo "Warning: No request/response files found to copy"
fi

echo -e "\nTest complete. Temporary files in: $TEST_DIR"
echo "Captured files copied to: $OUTPUT_DIR"