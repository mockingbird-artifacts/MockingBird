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
Translating a project end to end has three steps: generate the mock-test oracles from the Java project, translate it fragment by fragment with isolated validation, and report the results.

**Step 1 — generate mock tests.** For a project (e.g., `commons-fileupload`):

```bash
bash scripts/generate_mock_tests.sh commons-fileupload
```

For large projects, `scripts/generate_mock_tests_sharded.sh` runs `SHARDS` independent workers (default 4), each on its own copy of the project, and merges their mock tests into `data/mock_tests/<project>`:

```bash
SHARDS=4 bash scripts/generate_mock_tests_sharded.sh commons-fileupload
```

If classes still have public or protected methods without any mock test after the first pass, `scripts/augment_evosuite.sh` tops up coverage: it runs EvoSuite 1.2.0 on exactly those classes (with runtime mocking and the sandbox disabled so the tests survive `clean_evosuite_tests.py`), names the new classes `<X>ES2_ESTest`, and places the ones that compile next to the archive's EvoSuite tests. Re-run the generation script afterwards so the new tests are cleaned, built and recorded (needs Java 8; the EvoSuite jars are downloaded on demand):

```bash
BUDGET=180 PAR=8 bash scripts/augment_evosuite.sh commons-fileupload deepseek-coder-33b-instruct 0.0 _evosuite_cleaned
bash scripts/generate_mock_tests.sh commons-fileupload
```

Bodyless Java methods (interface, abstract, empty body) get one *static* mock test each, written from the schema alone (`src/isolated_validation/generate_static_mock_tests.py`, driver stage `static`): it checks that the translated module imports, the class defines the method under the skeleton's name with the same arity, the body stays trivial, and calling the stub does nothing. These follow the same `…_mocker_<n>_<Class>_<method>.py` convention, so the validator treats them like dynamic mock tests and `print_results.py` reports them separately.

Generation honors these environment variables (defaults in parentheses): `TEST_TIMEOUT` (900) seconds per Java test method; `MOCKINGBIRD_STABILITY_RUNS` (2) runs per EvoSuite test, keeping a mock test only when every run recorded the same behavior; `MAX_MOCK_TEST_MB` (10) discards oversized mock tests (`MOCKINGBIRD_KEEP_OVERSIZED=1` keeps them aside); `MAX_LOG_MB` (2048) caps aspect logs, truncated while the test runs by `scripts/log_cap_guard.sh`; `MOCKINGBIRD_RESUME` (1) resumes an interrupted run and re-queues tests whose files are missing; `MOCKGEN_QUIET` (1) drops Maven's per-test stdout; `SUREFIRE_XMX` (16g) sizes each forked test JVM so concurrent shards fit in RAM; `KEEP_SHARD_DIRS` (0) keeps per-shard copies after the merge.

**Step 2 — translate with isolated method-level validation.** To translate the project using `deepseek-coder-33b-instruct` at `temperature=0.0`:

```bash
bash scripts/create_project_schema.sh deepseek-coder-33b-instruct 0.0 java_projects/cleaned_final_projects_evosuite_cleaned _evosuite_cleaned commons-fileupload
bash scripts/translate_types.sh commons-fileupload deepseek-coder-33b-instruct 0.0 _evosuite_cleaned description Java Python
bash scripts/create_project_type_map.sh deepseek-coder-33b-instruct 0.0 _evosuite_cleaned commons-fileupload
bash scripts/automated_project_type_inference.sh deepseek-coder-33b-instruct 0.0 _evosuite_cleaned commons-fileupload
bash scripts/create_project_skeleton.sh _evosuite_cleaned deepseek-coder-33b-instruct 0.0 commons-fileupload
bash scripts/translate_fragment.sh commons-fileupload 0.0 deepseek-coder-33b-instruct _evosuite_cleaned
```

Alternatively, `scripts/run_project.sh` drives all stages for a project with stage markers and resume; its `validate` stage re-queues and re-translates, with the full harness, fragments whose mock tests were not yet eligible when they were first translated (a test is eligible only once every focal method it touches is translated, so resumed or out-of-order runs would otherwise leave such fragments without a verdict).

> [!NOTE]
> To translate **new projects**, follow [AlphaTrans's preprocessing pipeline](https://github.com/Intelligent-CAT-Lab/AlphaTrans?tab=readme-ov-file#translate-new-java-projects),
> then place the resulting project folder under `java_projects/cleaned_final_projects_evosuite`.

`generate_mock_tests.sh` can be CPU-intensive for large projects, while `translate_types.sh` and `translate_fragment.sh` may be GPU-intensive depending on the chosen LLM.

**Step 3 — evaluate and recompose.** To evaluate translation effectiveness:

```bash
bash scripts/print_results.sh commons-fileupload 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned _evosuite_cleaned
```

To generate standalone translated Python projects, recompose all translations with:

```bash
bash scripts/recompose.sh commons-fileupload 0.0 deepseek-coder-33b-instruct _evosuite_cleaned
```

---

## Reproduce Results in the MockingBird Paper

### RQ1: Effectiveness of MockingBird

All experiment artifacts are hosted on [Zenodo](https://zenodo.org/records/24457168). The tarball (approximately 30--45 GB after compression) includes all outputs generated by the pipeline. Specifically, after loading the image into the container, the `data` folder at the root contains the key pipeline artifacts:

- `data/crawl/` — contains relevant type information crawled from the Java standard library.
- `data/type_resolution/` — stores the results of our RAG-based in-context type mapping.
- `data/mock_tests/` — includes the generated mock tests for in-isolation, method-level validation.
- `data/schemas_evosuite_cleaned/` — contains intermediate pipeline data, including each method's type resolution, current translation results, validation outcomes, and related information.

The image also ships the RQ4 ablation schema trees (`rq4-noRAG`, `rq4-noOTF`, `rq4-noES`) and the I/O-only validation tree (`ds-ioonly`) used below.

To reproduce **Table 1** (effectiveness) and **Table 3** (test translation), run:

```bash
for p in aa ab ac ad ae; do wget "https://zenodo.org/record/24457168/files/mockingbird.tar.gz.part-$p"; done
cat mockingbird.tar.gz.part-* > mockingbird.tar.gz && rm mockingbird.tar.gz.part-*
sudo bash scripts/load_image.sh mockingbird.tar.gz   # docker-imports the flattened image as mockingbird:latest
sudo docker run -it -w /home/tmp/MockingBird/ mockingbird:latest /bin/bash
bash scripts/print_results.sh {project_name} 0.0 deepseek-coder-33b-instruct data/schemas_evosuite_cleaned _evosuite_cleaned
```

To reproduce **Table 2** (line/branch coverage of developer tests vs. the EvoSuite-augmented suite; JaCoCo under JDK 11):

```bash
JDK_HOME=$JAVA_HOME bash scripts/run_coverage_comparison.sh
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

Results for `Devstral-24B` experiments are included in the artifact image.  
To reproduce **Table 6**, run:

```bash
bash scripts/print_results.sh {project_name} 0.0 devstral-24b data/schemas_evosuite_cleaned _evosuite_cleaned
```

---

### RQ4: Ablation Studies

Each ablation arm removes one component of the pipeline and re-translates the ten projects from scratch; the arms differ from the full pipeline only in the switches below, so they always run the current workflow.

**w/o RAG-TR** (no retrieval-augmented translation): set `MOCKINGBIRD_NO_ICL=1` so the translation prompts are built without the in-context retrieval pool, and use AlphaTrans's fixed type mapping (skip `automated_project_type_inference.sh`):

```bash
export MOCKINGBIRD_NO_ICL=1
bash scripts/translate_fragment.sh {project_name} 0.0 {model} _evosuite_cleaned
```

**w/o OTF** (no mocking during iterative refinement): translate with `scripts/translate_fragment_nootf.sh` (syntax checks only in the loop), then apply mock validation once as the final verdict:

```bash
bash scripts/translate_fragment_nootf.sh {project_name} 0.0 {model} _evosuite_cleaned
python3 scripts/revalidate_fragments_isolated.py {project_name} {model}
```

**w/o ES** (no EvoSuite-generated tests): set `MOCKINGBIRD_NO_ES_TESTS=1` so validation only uses mock tests recorded from developer-written tests. Methods covered solely by EvoSuite tests become non-validatable:

```bash
export MOCKINGBIRD_NO_ES_TESTS=1
bash scripts/translate_fragment.sh {project_name} 0.0 {model} _evosuite_cleaned
```

The translated ablation schemas are included in this repository; to recompute an arm's verdicts with the current validator without re-translating, run the final-verdict pass over the stored schemas (set `MOCKINGBIRD_NO_ES_TESTS=1` first for the w/o-ES arm) and print the results:

```bash
python3 scripts/revalidate_fragments_isolated.py {project_name} {arm_model_dir}
bash scripts/print_results.sh {project_name} 0.0 {arm_model_dir} data/schemas_evosuite_cleaned _evosuite_cleaned
```

---

**I/O-only vs. full-snapshot validation** (Table 8): re-validate the translated projects with the oracle trimmed to return values, arguments, and exceptions (receiver-state and static-field snapshot checks skipped), then print the results:

```bash
export MOCKINGBIRD_IO_ONLY=1
python3 scripts/revalidate_fragments_isolated.py {project_name} ds-ioonly
bash scripts/print_results.sh {project_name} 0.0 ds-ioonly data/schemas_evosuite_cleaned _evosuite_cleaned
```

Comparing against the full-snapshot results of RQ1 per project gives the masked-false-positive counts reported in the paper.
