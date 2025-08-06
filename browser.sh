#!/usr/bin/env sh
[ $# -eq 0 ] && { echo "Usage: $0 <url>"; exit 1; }

for i in $(seq 1 30); do
    curl --output /dev/null --silent --fail "$1" && {
        open "$1" 2>/dev/null || xdg-open "$1" 2>/dev/null || start "$1" 2>/dev/null
        exit 0
    }
    sleep 1
done

echo "\nServer not available after 30 attempts: $1"
exit 1

