#!/bin/sh
# usage: run-ocr <psm>
set -eu
PSM="${1:-4}"
tesseract --version | head -1
while IFS= read -r path; do
  [ -z "$path" ] && continue
  name=$(basename "$path" .png)
  [ -s "/out/$name.tsv" ] && continue
  OMP_THREAD_LIMIT=1 tesseract "$path" "/out/$name" --psm "$PSM" -c preserve_interword_spaces=1 tsv >/dev/null 2>&1 || echo "FAIL $name"
done < /job/list.txt
echo done
