from zoneinfo import ZoneInfo
from google.cloud import storage
import gzip
from datetime import datetime

BUCKET_NAME = "trading-bot-bucket-epiphane-2026"
SOURCE_PREFIX = "raw/"
DESTINATION_PREFIX = "archive/"


def consolidate():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    now = datetime.now(ZoneInfo("Europe/Paris"))

    destination_name = (
        f"{DESTINATION_PREFIX}"
        f"transactions-{now:%Y-%m}.jsonl.gz"
    )

    # Buffer contenant le JSONL non compressé
    lines = []

    blobs = client.list_blobs(
        BUCKET_NAME,
        prefix=SOURCE_PREFIX
    )

    for blob in blobs:
        if not blob.name.endswith(".jsonl.gz"):
            continue

        print(f"Processing {blob.name}")

        # Téléchargement du .gz
        compressed_data = blob.download_as_bytes()

        # Décompression
        jsonl_data = gzip.decompress(compressed_data)

        lines.append(jsonl_data)

    # Concaténation
    final_jsonl = b"".join(lines)

    # Compression du fichier final
    final_compressed = gzip.compress(final_jsonl)

    # Upload
    destination_blob = bucket.blob(destination_name)
    destination_blob.content_encoding = "gzip"

    destination_blob.upload_from_string(
        final_compressed,
        content_type="application/x-ndjson"
    )

    print(
        f"Created gs://{BUCKET_NAME}/{destination_name}"
    )

    for blob in bucket.list_blobs(prefix="raw/"):
        print(f"Deleting {blob.name}")
        blob.delete()


if __name__ == "__main__":
    consolidate()
