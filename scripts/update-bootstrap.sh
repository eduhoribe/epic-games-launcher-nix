#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")/.."
pin=bootstrap.json

url=$(jq --exit-status --raw-output '.url' "$pin")
download=$(nix store prefetch-file --refresh --json "$url")
deb=$(jq --exit-status --raw-output '.storePath' <<< "$download")
hash=$(jq --exit-status --raw-output '.hash' <<< "$download")

package=$(dpkg-deb --field "$deb" Package)
architecture=$(dpkg-deb --field "$deb" Architecture)
if [[ "$package" != epic-games-launcher || "$architecture" != amd64 ]]; then
    printf 'Expected the epic-games-launcher amd64 Debian package, got %s %s\n' \
        "$package" "$architecture" >&2
    exit 1
fi
version=$(dpkg-deb --field "$deb" Version)
dpkg --validate-version "$version"

updated_pin=$(mktemp "${pin}.XXXXXX")
trap 'rm -f -- "$updated_pin"' EXIT
jq --arg version "$version" --arg hash "$hash" \
    '.version = $version | .hash = $hash' "$pin" > "$updated_pin"
if ! cmp -s -- "$pin" "$updated_pin"; then
    mv -- "$updated_pin" "$pin"
fi
