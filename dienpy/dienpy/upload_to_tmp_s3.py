"""Upload a file to the $TMP_S3_BUCKET temporary S3 bucket."""

import os
import subprocess
import sys


def main() -> None:
    bucket = os.environ["TMP_S3_BUCKET"]
    fname = sys.argv[1]
    comm = ["aws", "s3", "cp", fname, f"s3://{bucket}"]
    if ".json" in fname:
        comm.extend(["--content-type", "application/json"])
    if fname.endswith(".gz"):
        comm.extend(["--content-encoding", "gzip"])

    pubcomm = [
        "aws",
        "s3api",
        "put-object-acl",
        "--bucket",
        bucket,
        "--key",
        fname,
        "--acl",
        "public-read",
    ]
    subprocess.run(comm)
    subprocess.run(pubcomm)

    print(f"https://{bucket}.s3.amazonaws.com/{fname}")


if __name__ == "__main__":
    main()
