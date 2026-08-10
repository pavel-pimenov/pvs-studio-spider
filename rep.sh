#!/usr/bin/env bash
# Reproduce cmake configure failures for the failing projects (run in container).
set -u
mkdir -p /data/src /data/work /data/repro
cd /data/repro
rm -f results.txt

for slug in "$@"; do
  repo=$(python3 -c "
import yaml, sys
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(p['repo']); break
")
  ref=$(python3 -c "
import yaml, sys
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(p.get('ref','main')); break
")
  cmake_opt=$(python3 -c "
import yaml, shlex
cfg = yaml.safe_load(open('/app/projects.yaml'))
for p in cfg['projects']:
    if p['name'] == '$slug':
        print(' '.join(shlex.quote(o) for o in p.get('cmake_options', []))); break
")
  src=/data/src/$slug
  build=/data/work/$slug/build
  rm -rf "$src" "$build"
  echo "=== $slug (ref=$ref) ===" | tee -a results.txt
  git clone --depth 1 --single-branch --branch "$ref" "$repo" "$src" 2>&1 | tail -3
  if [ ! -d "$src/.git" ]; then
    echo "  [branch $ref missing, falling back to default]" | tee -a results.txt
    rm -rf "$src"
    git clone --depth 1 "$repo" "$src" 2>&1 | tail -3
  fi
  mkdir -p "$build"
  cmake -S "$src" -B "$build" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_TESTING=OFF \
    $cmake_opt > /data/repro/out.log 2>&1
  rc=$?
  echo "  cmake rc=$rc" | tee -a results.txt
  if [ $rc -ne 0 ]; then
    echo "  --- last 25 lines ---" | tee -a results.txt
    tail -25 /data/repro/out.log | sed 's/^/    /' | tee -a results.txt
  else
    echo "  --- cmake OK ---" | tee -a results.txt
  fi
  rm -rf "$src" "$build"
done
echo "DONE"
