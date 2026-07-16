#!/usr/bin/env sh
set -eu

repo="${AGENT_IMAGE_OPT_REPOSITORY:-ckken/agent-skills}"
release_base="${AGENT_IMAGE_OPT_RELEASE_BASE_URL:-https://github.com/${repo}/releases/latest/download}"
install_dir="${AGENT_IMAGE_OPT_INSTALL_DIR:-${HOME}/.local/bin}"

os="$(uname -s)"
arch="$(uname -m)"

case "$os" in
  Darwin)
    platform="apple-darwin"
    ;;
  Linux)
    platform="unknown-linux-gnu"
    ;;
  *)
    echo "agent-image-opt: unsupported operating system: $os" >&2
    echo "Build from source with: make -C tools/agent-image-opt install-local" >&2
    exit 1
    ;;
esac

case "$arch" in
  arm64|aarch64)
    architecture="aarch64"
    ;;
  x86_64|amd64)
    architecture="x86_64"
    ;;
  *)
    echo "agent-image-opt: unsupported architecture: $arch" >&2
    echo "Build from source with: make -C tools/agent-image-opt install-local" >&2
    exit 1
    ;;
esac

asset="agent-image-opt-${architecture}-${platform}.tar.gz"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

echo "Downloading ${asset} from the latest agent-image-opt release..." >&2
curl -fsSL "${release_base}/${asset}" -o "${tmp_dir}/${asset}"
curl -fsSL "${release_base}/SHA256SUMS" -o "${tmp_dir}/SHA256SUMS"

expected="$(
  awk -v asset="$asset" '$2 == asset { print $1 }' "${tmp_dir}/SHA256SUMS"
)"

if [ -z "$expected" ]; then
  echo "agent-image-opt: checksum entry not found for ${asset}" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "${tmp_dir}/${asset}" | awk '{ print $1 }')"
elif command -v shasum >/dev/null 2>&1; then
  actual="$(shasum -a 256 "${tmp_dir}/${asset}" | awk '{ print $1 }')"
else
  echo "agent-image-opt: sha256sum or shasum is required" >&2
  exit 1
fi

if [ "$actual" != "$expected" ]; then
  echo "agent-image-opt: checksum verification failed for ${asset}" >&2
  exit 1
fi

tar -xzf "${tmp_dir}/${asset}" -C "$tmp_dir"
mkdir -p "$install_dir"
install -m 755 "${tmp_dir}/agent-image-opt" "${install_dir}/agent-image-opt"

echo "Installed agent-image-opt to ${install_dir}/agent-image-opt" >&2
"${install_dir}/agent-image-opt" --json doctor
