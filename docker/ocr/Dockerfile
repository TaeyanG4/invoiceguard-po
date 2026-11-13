# B0 OCR engine: Tesseract in an isolated Linux container (no host install). CPU only.
FROM ubuntu:22.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
# Runs tesseract for every container path listed in /job/list.txt, writing TSV next to /out/<name>.tsv
COPY run.sh /usr/local/bin/run-ocr
RUN chmod +x /usr/local/bin/run-ocr
ENTRYPOINT ["/usr/local/bin/run-ocr"]
