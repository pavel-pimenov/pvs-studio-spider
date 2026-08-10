#!/usr/bin/env bash
# Validate the planned fixes: configure each project with the proposed options.
# Usage: validate.sh [slug ...]
set -u
mkdir -p /data/work

for slug in "$@"; do
  repo=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(p['repo']); break
")
  ref=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(p.get('ref','main')); break
")
  opts=$(python3 -c "
import yaml, shlex
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(' '.join(shlex.quote(o) for o in p.get('cmake_options', []))); break
")
  cmake_src=$(python3 -c "
import yaml
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(p.get('cmake_src', '')); break
")
  src=/data/src/$slug
  build=/data/work/$slug/build
  rm -rf "$src" "$build"
  echo "=== $slug (ref=$ref) ==="
  git clone --depth 1 --single-branch --branch "$ref" "$repo" "$src" >/dev/null 2>&1
  if [ ! -d "$src/.git" ]; then
    rm -rf "$src"
    echo "  [branch $ref missing, default branch]"
    git clone --depth 1 "$repo" "$src" >/dev/null 2>&1
  fi
  mkdir -p "$build"
  cmake -S "$src/$cmake_src" -B "$build" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_TESTING=OFF \
    -DCMAKE_PROJECT_INCLUDE=/tmp/cm_fix.cmake \
    $opts > /tmp/val_$slug.log 2>&1
  rc=$?
  echo "  configure rc=$rc"
  if [ $rc -ne 0 ]; then
    grep -m2 -A6 "CMake Error" /tmp/val_$slug.log | head -14
  fi
  rm -rf "$src" "$build"
done
echo DONE
