#!/bin/bash

adb -a nodaemon server start &

# Service
exec uv run poe start