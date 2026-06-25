# Quality Tools

This document provides instructions for developers on how to execute the quality tools available in Score (Clang-Tidy, CodeQL, Coverage, Sanitizers, Copyright Checker, and C++, Bazel Files Formatter) locally.

## Clang-Tidy

Clang-Tidy performs static analysis using a set of checks configured in the root [`.clang-tidy`](../.clang-tidy) file. It is integrated into Bazel via `@aspect_rules_lint` and uses the LLVM toolchain's clang-tidy binary.

### Running Clang-Tidy

```bash
bazel test --config=clang-tidy //...
```

To run on a specific target:

```bash
bazel test --config=clang-tidy //score/message_passing:client_connection_test
```

The enabled check groups are: `bugprone-*`, `cert-*`, `clang-analyzer-*`, `cppcoreguidelines-*`, `fuchsia-*`, `google-*`, `hicpp-*`, `misc-*`, `modernize-*`, `performance-*`, and `readability-*`. The checks are organized into AUTOSAR severity-one, AUTOSAR severity-two, CERT, and QNX categories — see the [`.clang-tidy`](../.clang-tidy) file for the full list.

> **Note:** Only `clang-analyzer-*` findings are treated as errors. All other check groups produce warnings.

## CodeQL (MISRA C++)

CodeQL performs MISRA C++ compliance checking using the `codeql/misra-cpp-coding-standards` query pack (version pinned in [`quality/static_analysis/config.yaml`](static_analysis/config.yaml)). The analysis builds a CodeQL database from the Bazel build and runs the configured queries against it.

The script supports two reusable phases that can be run independently:

1. **Database creation** — compiles the codebase with CodeQL tracing and produces a reusable database.
2. **Analysis** — runs CodeQL queries against an existing database.

### Running CodeQL (all-in-one)

```bash
bazel run //quality/static_analysis:codeql_lint -- --target=//...
```

To analyze a specific target:

```bash
bazel run //quality/static_analysis:codeql_lint -- --target=//score/message_passing/...
```

### Running CodeQL in phases

Create the database once:

```bash
bazel run //quality/static_analysis:codeql_lint -- \
  --phase create-database \
  --database-path /var/tmp/codeql_databases/codeql_db \
  --target //score/...
```

Run quick analysis (uses incremental queries from config.yaml):

```bash
bazel run //quality/static_analysis:codeql_lint -- \
  --phase analyze-database \
  --database-path /var/tmp/codeql_databases/codeql_db
```

Run full analysis with a specific query pack (e.g. for nightly):

```bash
bazel run //quality/static_analysis:codeql_lint -- \
  --phase analyze-database \
  --database-path /var/tmp/codeql_databases/codeql_db \
  --query-spec "codeql/misra-cpp-coding-standards@2.52.0" \
  --output-prefix codeql-nightly
```

The `--phase` argument accepts `create-database`, `analyze-database`, or `all` (default, original behavior). The `--query-spec` argument allows specifying a different query pack or suite for the analysis step. The `--output-prefix` argument controls the output file names.

Results are written to the Bazel output directory (`bazel info output_path`):

- `codeql.sarif` — SARIF v2.1.0 format
- `codeql.csv` — CSV format

The query configuration is defined in [`quality/static_analysis/config.yaml`](static_analysis/config.yaml).

### Automatic Compliance Report Generation

When CodeQL analysis completes, MISRA C++ compliance reports are **automatically generated** and saved to `quality/static_analysis/codeql_reports/`.

Reports are automatically generated for all analysis modes:
- `--phase all` (default)
- `--phase analyze-database` (when analyzing existing database)

The complete pipeline creates:

1. **CodeQL Database** — Analyzed code structure
   - Location: `/var/tmp/codeql_databases/tmp[random_name]/`

2. **SARIF File** — Machine-readable analysis results (JSON)
   - Location: `bazel-out/codeql.sarif`

3. **Markdown Reports** — Human-readable compliance documents (4 files)
   - Location: `quality/static_analysis/codeql_reports/`

#### Run CodeQL with Automatic Reports (Recommended)

**Analyze a specific target with full automatic report generation:**

```bash
bazel run //quality/static_analysis:codeql_lint -- --target=//score/message_passing
```

This single command automatically:
1. Creates CodeQL database
2. Generates SARIF file (JSON with findings)
3. Generates 4 Markdown reports from SARIF

#### Generated Reports

The following markdown files are automatically created in `quality/static_analysis/codeql_reports/`:

- **guideline_compliance_summary.md** — Executive summary
  - Total issues found
  - Rules triggered
  - Severity breakdown
  - Top violations

- **findings_report.md** — Detailed findings
  - Issues organized by rule
  - File location, severity, message for each issue

- **codeql_analysis_results.md** — Markdown table
  - Machine-readable table format
  - Rule ID, Severity, Location, Message columns

- **analysis_metadata.md** — Analysis information
  - Tool version (CodeQL)
  - Standards (MISRA C++ 2023)
  - Links to raw data files

#### View Reports

**View the main compliance summary:**

```bash
cat quality/static_analysis/codeql_reports/guideline_compliance_summary.md
```

**View detailed findings:**

```bash
cat quality/static_analysis/codeql_reports/findings_report.md
```

**View all results as a table:**

```bash
cat quality/static_analysis/codeql_reports/codeql_analysis_results.md
```

#### What Happens on Subsequent Runs

When you run the command again:
- **Database** — Recreated fresh (ensures latest analysis)
- **SARIF** — Overwritten with new findings
- **Reports** — Deleted and regenerated with new data

#### Important Notes

- **Always specify --target** — Without it, the database will be empty and reports will show 0 issues (false negatives)
- **Reports auto-generate** — No separate command needed; they're created automatically as part of the pipeline
- **All three artifacts created** — Database, SARIF, and Reports are generated in one command


## Coverage

Code coverage is generated using LLVM's source-based coverage instrumentation. The instrumentation filter is configured in [`quality/coverage.bazelrc`](coverage.bazelrc) to cover `//score/message_passing` and `//score/mw/com` while excluding test and benchmark code.

### Running Coverage

> **Note:** The commands below assume `--combined_report=lcov` is set, which enables
> a combined LCOV report across all test targets. This flag is already configured in
> [`quality/coverage.bazelrc`](coverage.bazelrc) (imported from the repository root `.bazelrc`).

```bash
bazel coverage //...
```

To run coverage for a specific target:

```bash
bazel coverage --combined_report=lcov //score/message_passing:client_connection_test_linux
```

When [`quality/coverage.bazelrc`](coverage.bazelrc) is active, the combined LCOV report is written to
`bazel-out/_coverage/_coverage_report.dat`.

To generate an HTML report from the LCOV data:

```bash
genhtml --ignore-errors inconsistent bazel-out/_coverage/_coverage_report.dat --output-directory coverage_html
```

Then open `coverage_html/index.html` in a browser.

## Sanitizers

Address, undefined behavior, leak, and thread sanitizers are also available:

| Config | Sanitizers Enabled |
|--------|--------------------|
| `--config=asan` / `--config=ubsan` / `--config=lsan` | AddressSanitizer + UBSan + LeakSanitizer |
| `--config=tsan` | ThreadSanitizer |

> **Note:** `--config=asan`, `--config=ubsan`, and `--config=lsan` are all aliases
> for the same `asan_ubsan_lsan` configuration defined in `quality/sanitizer/sanitizer.bazelrc`.
> Each enables the identical set of sanitizers (ASan + UBSan + LSan).

### Running Sanitizers

```bash
bazel test --config=asan //...
bazel test --config=tsan //...
```

## Linting

### Copyright Checker

```bash
# Check Sources
bazel run //:copyright.check

# Fix Sources
bazel run //:copyright.fix
```

### C++ and Bazel Files Formatter

```bash
# Check Sources
bazel run //:format.check

# Fix Sources
bazel run //:format
```