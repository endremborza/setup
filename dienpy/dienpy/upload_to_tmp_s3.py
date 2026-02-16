import os
import subprocess
import sys

BUCKET = os.environ["TMP_S3_BUCKET"]


def upload():
    print(sys.argv)
    fname = sys.argv[1]
    comm = ["aws", "s3", "cp", fname, f"s3://{BUCKET}"]
    if ".json" in fname:
        comm.extend(["--content-type", "application/json"])
    if fname.endswith(".gz"):
        comm.extend(["--content-encoding", "gzip"])

    pubcomm = [
        "aws",
        "s3api",
        "put-object-acl",
        "--bucket",
        BUCKET,
        "--key",
        fname,
        "--acl",
        "public-read",
    ]
    subprocess.run(comm)
    subprocess.run(pubcomm)

    print(f"https://{BUCKET}.s3.amazonaws.com/{fname}")


if __name__ == "__main__":
    upload()
