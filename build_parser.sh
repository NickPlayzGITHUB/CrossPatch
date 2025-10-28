#!/usr/bin/env bash
# build_parser.sh
# Helper to publish the CrossPatchParser project for different platforms.
# Usage:
#   ./build_parser.sh [self-contained|framework] [rid]
# Examples:
#   ./build_parser.sh self-contained linux-x64
#   ./build_parser.sh framework

set -euo pipefail
MODE=${1:-self-contained}
RID=${2:-linux-x64}
CONFIG=Release
PROJECT="tools/CrossPatchParser/CrossPatchParser.csproj"
OUTDIR="tools/CrossPatchParser/bin/Release/net8.0/publish"

echo "Build mode: $MODE"
echo "RID: $RID"

if ! command -v dotnet >/dev/null 2>&1; then
  echo "dotnet not found in PATH. Please install the .NET SDK/runtime to build."
  exit 1
fi

if [ "$MODE" = "self-contained" ]; then
  echo "Publishing self-contained single-file executable for $RID"
  dotnet publish "$PROJECT" -c $CONFIG -f net8.0 -r $RID --self-contained true -p:PublishSingleFile=true -o "$OUTDIR"
  echo "Published to $OUTDIR"
  exit 0
elif [ "$MODE" = "framework" ]; then
  echo "Publishing framework-dependent build (DLL)."
  dotnet publish "$PROJECT" -c $CONFIG -f net8.0 -o "$OUTDIR"
  echo "Published to $OUTDIR"
  exit 0
else
  echo "Unknown mode: $MODE"
  echo "Usage: $0 [self-contained|framework] [rid]"
  exit 2
fi
