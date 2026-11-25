#!/bin/sh
# Build a throwaway git repository with the kit, a few sources and the Grok bridge: make_fixture.sh <kit dir> <bridge> <target dir>
set -e
kit=$1; bridge=$2; target=$3
rm -rf "$target"; mkdir -p "$target"; cp -r "$kit" "$target/proj"; cd "$target/proj"
mkdir -p src/main/java/com/example/service src/test/java/com/example/service src/acceptanceTest/resources/features \
  src/acceptanceTest/java/com/example/service/acceptance gauntlet/adapters/grok .grok/hooks
echo 'package com.example.service; public class App {}' > src/main/java/com/example/service/App.java
echo 'package com.example.service; class AppTest {}' > src/test/java/com/example/service/AppTest.java
printf '# language: ru\nФункция: пример\n' > src/acceptanceTest/resources/features/a.feature
echo 'package com.example.service.acceptance; class Steps {}' > src/acceptanceTest/java/com/example/service/acceptance/Steps.java
echo '# agents' > AGENTS.md; echo '[permission]' > .grok/config.toml
cp "$bridge" gauntlet/adapters/grok/
git init -q -b main .; git -c user.email=t@t -c user.name=t add -A; git -c user.email=t@t -c user.name=t commit -q -m base
git update-ref refs/remotes/origin/main HEAD; git switch -q -c step-1
