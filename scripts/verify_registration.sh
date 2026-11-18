#!/usr/bin/env bash
# Check the registered files present in this repository against the registration manifest and the seal.
#
#   bash scripts/verify_registration.sh
#
# * outputs/framelease_v4/registration/MANIFEST.sha256 lists every registered file (221 entries, paths relative to
#   the project root, two absolute paths for the source documents). Each entry present in the repository must have
#   the listed sha256; each absent entry is reported as EXTERNAL (see docs/EXTERNAL_FILES.md).
# * outputs/framelease_v4/registration/SEAL.sha256 seals framelease_v4/PROTOCOL.md and the manifest itself.
# * Every other sha256 list of the included registered outputs (the SHA256SUMS of the analysis and the verifications,
#   the MANIFEST.sha256 of the protocol tables, of the test freeze and of each amendment attempt) is checked for the
#   files it lists that are present; the files it lists that are not in this repository are counted, not listed.
# Exit 0: no mismatch. Exit 1: at least one mismatch.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
MANIFEST=outputs/framelease_v4/registration/MANIFEST.sha256
SEAL=outputs/framelease_v4/registration/SEAL.sha256
ok=0; bad=0; ext=0
check_list() {  # $1 = list file, $2 = base directory of its relative paths, $3 = label
    local list=$1 base=$2 label=$3 sha path target actual
    while IFS= read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        sha=${line%%  *}; path=${line#*  }; path=${path#\*}
        if [ "${path:0:1}" = "/" ]; then
            echo "EXTERNAL  $label  $path"; ext=$((ext + 1)); continue
        fi
        target="$base/$path"
        if [ ! -f "$target" ]; then
            echo "EXTERNAL  $label  $path"; ext=$((ext + 1)); continue
        fi
        actual=$(sha256sum "$target" | cut -d' ' -f1)
        if [ "$actual" = "$sha" ]; then ok=$((ok + 1)); else echo "MISMATCH  $label  $path"; bad=$((bad + 1)); fi
    done < "$list"
}
echo "== registration manifest ($MANIFEST)"
check_list "$MANIFEST" . manifest
m_ok=$ok; m_bad=$bad; m_ext=$ext
echo "manifest: $(wc -l < "$MANIFEST") entries; present and identical $m_ok; mismatching $m_bad; external $m_ext"
echo "== seal ($SEAL)"
ok=0; bad=0; ext=0
check_list "$SEAL" . seal
s_ok=$ok; s_bad=$bad
echo "seal: identical $s_ok; mismatching $s_bad"
echo "== sha256 manifests of the included registered outputs"
ok=0; bad=0; ext=0; lists=0
while IFS= read -r list; do
    case "$list" in
        */registration/*) continue ;;
        */test_freeze/MANIFEST.sha256|*/attempt_*/MANIFEST.sha256) base=. ;;
        *) base=$(dirname -- "$list") ;;
    esac
    lists=$((lists + 1))
    check_list "$list" "$base" "$list" > /tmp/.verify_registration.$$ || true
    grep -v '^EXTERNAL' /tmp/.verify_registration.$$ || true
    rm -f /tmp/.verify_registration.$$
done < <(find outputs/framelease_v4 \( -name SHA256SUMS -o -name 'MANIFEST.sha256' \) -type f | sort)
echo "output manifests: $lists lists; present and identical $ok; mismatching $bad; not in this repository $ext"
total_bad=$((m_bad + s_bad + bad))
if [ "$total_bad" -eq 0 ]; then echo "RESULT: OK (no mismatch)"; exit 0; fi
echo "RESULT: $total_bad mismatching file(s)"; exit 1
