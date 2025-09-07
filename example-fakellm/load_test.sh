#!/bin/bash

# Load test script for Ray Serve autoscaling
SERVICE_URL="http://localhost:8000/fake"
DURATION=300   # seconds (5 minutes)
USERS=20        # number of concurrent users

echo "Starting load test..."
echo "Target: $SERVICE_URL"
echo "Configuration:"
echo "- Concurrent users: $USERS"
echo "- Duration: ${DURATION}s"
echo "- Each user sends requests continuously"
echo ""

start_time=$(date +%s)

# Function: single user continuously sending requests
send_requests() {
    local user_id=$1
    local request_id=0
    while [ $(($(date +%s) - start_time)) -lt $DURATION ]; do
        request_id=$((request_id + 1))
        req_start=$(date +%s.%3N)
        response=$(curl -s -X POST $SERVICE_URL \
            -H "Content-Type: application/json" \
            -d "{\"prompt\": \"User $user_id request $request_id\"}" \
            -w "%{http_code}")
        req_end=$(date +%s.%3N)
        duration=$(echo "$req_end - $req_start" | bc 2>/dev/null || echo "N/A")
        echo "[User $user_id] Request $request_id: HTTP $response - ${duration}s"
    done
}

# Launch N users in background
for u in $(seq 1 $USERS); do
    send_requests $u &
done

# Wait for all background jobs
wait

echo "Load test completed!"
echo "Monitor scaling with: kubectl get pods -w"
echo "Check Ray dashboard: http://localhost:8265"