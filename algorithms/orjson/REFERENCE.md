---
skill_id: algorithms.orjson
name: "orjson -- High-Performance JSON Library"
description: "Reference documentation for orjson -- High-Performance JSON Library. Source: orjson-anthropic-3.11.7"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/orjson
anchors:
  - orjson
  - orjson
source_repo: orjson-anthropic-3.11.7
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# orjson -- High-Performance JSON Library

Source: `orjson-anthropic-3.11.7` (606 files)

## README

# orjson

orjson is a fast, correct JSON library for Python. It
[benchmarks](https://github.com/ijl/orjson?tab=readme-ov-file#performance) as the fastest Python
library for JSON and is more correct than the standard json library or other
third-party libraries. It serializes
[dataclass](https://github.com/ijl/orjson?tab=readme-ov-file#dataclass),
[datetime](https://github.com/ijl/orjson?tab=readme-ov-file#datetime),
[numpy](https://github.com/ijl/orjson?tab=readme-ov-file#numpy), and
[UUID](https://github.com/ijl/orjson?tab=readme-ov-file#uuid) instances natively.

[orjson.dumps()](https://github.com/ijl/orjson?tab=readme-ov-file#serialize) is
something like 10x as fast as `json`, serializes
common types and subtypes, has a `default` parameter for the caller to specify
how to serialize arbitrary types, and has a number of flags controlling output.

[orjson.loads()](https://github.com/ijl/orjson?tab=readme-ov-file#deserialize)
is something like 2x as fast as `json`, and is strictly compliant with UTF-8 and
RFC 8259 ("The JavaScript Object Notation (JSON) Data Interchange Format").

Reading from and writing to files, line-delimited JSON files, and so on is
not provided by the library.

orjson supports CPython 3.10, 3.11, 3.12, 3.13, 3.14, and 3.15.

It distributes amd64/x86_64/x64, i686/x86, aarch64/arm64/armv8, arm7,
ppc64le/POWER8, and s390x wheels for Linux, amd64 and aarch64 wheels
for macOS, and amd64, i686, and aarch64 wheels for Windows.

Wheels published to PyPI for amd6

## Diff History
- **v00.33.0**: Ingested from orjson-anthropic-3.11.7