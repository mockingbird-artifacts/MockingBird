# MockingBird

Artifact repository for **MockingBird** — a tool that advances automated in-isolation validation for repository-level code translation.

---

## Getting Started

We provide a [`Dockerfile`](/Dockerfile) that installs all dependencies required to reproduce MockingBird’s results.  
To begin, install [Docker](https://www.docker.com/) and run the following commands to build and launch an interactive container:

```bash
sudo docker build --no-cache -t mockingbird .
sudo docker run -it --gpus all --shm-size=16g mockingbird bash
```

> [!NOTE]
> On macOS with Apple Silicon, add `--platform=linux/amd64` to the `docker build` command.

Once the container is ready, follow the steps below to start translating projects. If you want to reproduce numbers in the paper, please directly go to [Reproduce MockingBird Results](#reproduce-results-in-the-MockingBird-paper) for instructions.

---

### Setting up `deepseek-coder-33b-instruct`

MockingBird directly supports the `deepseek-ai/deepseek-coder-33b-instruct` model served via [Ollama](https://github.com/ollama/ollama).  
Start Ollama and pull the model using:

```bash
nohup ollama serve > ollama.log 2>&1 &
ollama pull deepseek-coder:33b
```

> [!NOTE]
> To use other LLMs (e.g., open-source `Devstral-24b` or proprietary models such as GPT-4), modify `configs/model_configs.yaml` with the appropriate model endpoint and/or API key.

---

### Translating Java Projects with Isolated Method-Level Validation

We provide ten preprocessed Java projects from [AlphaTrans](https://github.com/Intelligent-CAT-Lab/AlphaTrans).  
To translate a project (e.g., `commons-fileupload`) using `deepseek-coder-33b-instruct` at `temperature=0.0`, run:

```bash
bash scripts/generate_mock_tests.sh commons-fileupload
bash scripts/create_project_schema.sh deepseek-coder-33b-instruct 0.0 java_projects/cleaned_final_projects_evosuite_cleaned _evosuite_cleaned commons-fileupload
bash scripts/translate_types.sh commons-fileupload deepseek-coder-33b-instruct 0.0 _evosuite_cleaned description Java Python
bash scripts/create_project_type_map.sh deepseek-coder-33b-instruct 0.0 _evosuite_cleaned commons-fileupload
bash scripts/automated_project_type_inference.sh deepseek-coder-33b-instruct 0.0 _evosuite_cleaned commons-fileupload
bash scripts/create_project_skeleton.sh _evosuite_cleaned deepseek-coder-33b-instruct 0.0 commons-fileupload
bash scripts/translate_fragment.sh commons-fileupload 0.0 deepseek-coder-33b-instruct _evosuite_cleaned
```

> [!NOTE]
> To translate **new projects**, follow [AlphaTrans’s preprocessing pipeline](https://github.com/Intelligent-CAT-Lab/AlphaTrans?tab=readme-ov-file#translate-new-java-projects),  
> then place the resulting project folder under `java_projects/cleaned_final_projects_evosuite`.

`generate_mock_tests.sh` can be CPU-intensive for large projects, while `translate_types.sh` and `translate_fragment.sh` may be GPU-intensive depending on the chosen LLM.

To evaluate translation effectiveness for `commons-fileupload`:

```bash
bash scripts/print_results.sh commons-fileupload 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned _evosuite_cleaned
```

To generate standalone translated Python projects, recompose all translations with:

```bash
bash scripts/recompose.sh commons-fileupload 0.0 deepseek-coder-33b-instruct _evosuite_cleaned
```

---

### Test Coverage Top-Up, Sharded Mock Generation and Run Controls

The mock-test generation stage has three additions over the initial release.

**Sharded generation.** `scripts/generate_mock_tests_sharded.sh` runs `SHARDS` independent workers (default 4), each on its own copy of the project, and merges their mock tests into `data/mock_tests/<project>`:

```bash
SHARDS=4 bash scripts/generate_mock_tests_sharded.sh commons-fileupload
```

**EvoSuite top-up.** After a first generation pass, `scripts/augment_evosuite.sh` lists the classes that still have public or protected methods without any mock test (`src/isolated_validation/evosuite_targets.py`), runs EvoSuite 1.2.0 on them with runtime mocking and the sandbox disabled so that the tests survive `clean_evosuite_tests.py`, renames the new classes to `<X>ES2_ESTest` and places the ones that compile next to the archive's EvoSuite tests (`src/isolated_validation/evosuite_place_tests.py`). Re-run the generation script afterwards so the new tests are cleaned, built and recorded. The script needs Java 8 and downloads `misc/evosuite-1.2.0.jar` and `misc/evosuite-standalone-runtime-1.2.0.jar` from the EvoSuite release when they are missing.

```bash
BUDGET=180 PAR=8 bash scripts/augment_evosuite.sh commons-fileupload deepseek-coder-33b-instruct 0.0 _evosuite_cleaned
bash scripts/generate_mock_tests.sh commons-fileupload
```

**Run controls.** Environment variables read by the generation scripts and `src/isolated_validation/generate_logs.py`:

| Variable | Default | Effect |
|---|---|---|
| `TEST_TIMEOUT` | 900 | seconds allowed per Java test method |
| `MOCKINGBIRD_STABILITY_RUNS` | 2 | each EvoSuite test is executed this many times; a mock test is kept only when every run recorded the same behavior (canonical form in `src/isolated_validation/stability.py`) |
| `MAX_MOCK_TEST_MB` | 10 | mock tests above this size are set aside in `<project>-python__oversized` instead of slowing validation |
| `MAX_LOG_MB` | 2048 | aspect logs above this size are discarded; they cannot yield a usable mock test and fill the disk |
| `MOCKINGBIRD_RESUME` | 1 | an interrupted generation run resumes from its recorded state and re-queues tests whose files are missing |
| `MOCKGEN_QUIET` | 1 | drop Maven's per-test stdout (huge-array tests otherwise produce logs of tens of GB) |

**Changes to the validation pipeline since the initial release.**
- `CustomToStringConverter.java` serializes more JDK types (paths, charsets, NIO buffers, readers and writers, processes, atomics, locks, optionals and map entries), and `LoggingAspect.java` always writes the END record, also when the focal method throws an `Error`, and skips compiler-synthetic static fields. Truncated log chunks are skipped by `log_parser.py` instead of aborting the whole test.
- `mock_helper.py` (identical copies in `src/isolated_validation` and `src/mocking`) consults the per-project context-aware type map `data/type_resolution/<project>/type_mapping.json` first and falls back to the fixed map; `validate_by_mocking.py` exports the map location to the test process (`MOCKINGBIRD_TYPE_MAP`, `MOCKINGBIRD_PROJECT`, `MOCKINGBIRD_ROOT`). Failed comparisons report the mismatching path and both values, Java exception families map to the Python exceptions translations actually raise, and recorded stream positions and non-numeric float payloads no longer crash the helper itself.
- `print_results.py` counts interface methods as non-validatable rather than as successes and reports success both over all methods and over validatable methods; `print_results.sh` writes to stderr so it also works without a terminal.
- `create_schema.py` keeps generic and scoped superclasses; `create_skeleton.py` is idempotent across repeated skeleton passes and emits adapters for library base classes that have no Python counterpart; `recompose.py` substitutes a stub for a non-parseable fragment so one bad translation no longer breaks the import of the whole module; `calculate_coverage.py` skips helper modules that have no schema.
- `run_maven.sh` runs `mvn test` on the build already woven by `generate_logs.py` instead of a full `clean install` per test method, and runs the whole class when the test method is inherited.
- `clean_evosuite_tests.py` handles brace characters inside character literals.

---

## Reproduce Results in the MockingBird Paper

### RQ1: Effectiveness of MockingBird

All experiment artifacts are hosted on [Zenodo](https://zenodo.org/records/20824448). The tarball (approximately 30 GB after compression) includes all outputs generated by the pipeline. Specifically, after loading the image into the container, the `data` folder at the root contains the key pipeline artifacts:

- `data/crawl/` — contains relevant type information crawled from the Java standard library.
- `data/type_resolution/` — stores the results of our RAG-based in-context type mapping.
- `data/mock_tests/` — includes the generated mock tests for in-isolation, method-level validation.
- `data/schemas_evosuite_cleaned/` — contains intermediate pipeline data, including each method's type resolution, current translation results, validation outcomes, and related information.

To reproduce **Table 1** and **Table 2**, run:

```bash
wget https://zenodo.org/record/20824448/files/mockingbird.tar.gz
sudo docker load -i mockingbird.tar.gz  # Docker prints the image name and tag after loading
sudo docker run -it -w /home/tmp/MockingBird/ <image_name> /bin/bash  # <image_name> shall be mockingbird:latest
bash scripts/print_results.sh {project_name} 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned _evosuite_cleaned
```

> [!NOTE]
> Available `{project_name}` values:  
> `commons-cli`, `commons-codec`, `commons-csv`, `commons-exec`, `JavaFastPFOR`,  
> `commons-fileupload`, `commons-graph`, `jansi`, `commons-pool`, `commons-validator`.

---

### RQ2: Reliability of Mocking-Based Isolated Validation

Manual study results are stored as `.tsv` files under [`data/manual_inspection`](/data/manual_inspection).  
Each file corresponds to one manually inspected project:

- **Column 1:** Application-level method name  
- **Column 2:** Graal outcome from [AlphaTrans](https://github.com/Intelligent-CAT-Lab/AlphaTrans)  
- **Column 3:** Mocking-based validation result  
- **Column 4:** Ground truth validation by expert developers  
- **Column 5:** Explanations of false positives/negatives

To reproduce the Venn-diagram between Graal, mocking and manual inspection, please run:

```bash
python3 data/manual_inspection/venn_analysis.py
```

---

### RQ3: Generalizability Across Different Models

Results for `Devstral-24B` experiments are included in this repository.  
To reproduce **Table 4**, run:

```bash
bash scripts/print_results.sh {project_name} 0.0 devstral-24b data/schemas_evosuite_cleaned _evosuite_cleaned
```

---

### RQ4: Ablation Studies

Ablation study results are also included in this repository.  
To reproduce **Table 5**, run:

```bash
bash scripts/print_results.sh {project_name} 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned_no_RAG # w/o RAG-based type resolution
bash scripts/print_results.sh {project_name} 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned_no_mock     # w/o mocking on-the-fly
bash scripts/print_results.sh commons-cli 0.0 deepseek-coder-33b-instruct data/schemas_no_evosuite_cleaned     # w/o Evosuite
```

---
