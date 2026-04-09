---
skill_id: algorithms.blobfile
name: "BlobFile -- Cloud File IO Library"
description: "Reference documentation for BlobFile -- Cloud File IO Library. Source: blobfile-master"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/blobfile
anchors:
  - blobfile
  - blobfile
source_repo: blobfile-master
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# BlobFile -- Cloud File IO Library

Source: `blobfile-master` (35 files)

## README

# blobfile

This is a library that provides a Python-like interface for reading local and remote files (only from blob storage), with an API similar to `open()` as well as some of the `os.path` and `shutil` functions.  `blobfile` supports local paths, Google Cloud Storage paths (`gs://<bucket>`), and Azure Blob Storage paths (`az://<account>/<container>` or `https://<account>.blob.core.windows.net/<container>/`).

The main function is `BlobFile`, which lets you open local and remote files that act more or less like local ones.  There are also a few additional functions such as `basename`, `dirname`, and `join`, which mostly do the same thing as their `os.path` namesakes, only they also support GCS paths and ABS paths.

This library is inspired by TensorFlow's [`gfile`](https://www.tensorflow.org/api_docs/python/tf/io/gfile/GFile) but does not have exactly the same interface.

## Installation

```sh
pip install blobfile
```

## Usage

```py
# write a file, then read it back

import blobfile as bf

with bf.BlobFile("gs://my-bucket-name/cats", "wb") as f:
    f.write(b"meow!")

print("exists:", bf.exists("gs://my-bucket-name/cats"))

with bf.BlobFile("gs://my-bucket-name/cats", "rb") as f:
    print("contents:", f.read())
```

There are also some [examples processing many blobs in parallel](docs/parallel_examples.md).

Here are the functions in `blobfile`:

* `BlobFile` - like `open()` but works with remote paths too, data can be streamed to/fro

## Diff History
- **v00.33.0**: Ingested from blobfile-master