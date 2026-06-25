# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
import argparse
import os
import tempfile
import json
import subprocess
import datetime

TMP_PATH_FOR_DATABASES = "/var/tmp/codeql_databases"


def create_database(code_ql_path, config_path, target, source_root, database_path):
    """Create the CodeQL database: init, build with tracing, finalize."""
    os.system(
        f"{code_ql_path} database init --begin-tracing --language=cpp --codescanning-config={config_path} --source-root={source_root} -- {database_path}")

    with open(os.path.join(database_path,
                           "temp/tracingEnvironment/start-tracing.json")) as environment_description:
        necessary_codeql_environment = json.load(environment_description)
        env = _get_merged_environment(necessary_codeql_environment)

        process_coding_standards_config = f"bazel run @codeql_coding_standards//:process_coding_standards_config"
        subprocess.run(process_coding_standards_config + f" -- --working-dir={source_root}", shell=True, env=env,
                       cwd=source_root, check=True)

        bazel_command = f"bazel build --config=codeql --stamp --action_env=CODEQL_SEED_FORCE_RECOMPILE={datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        bazel_command += _get_action_env_extension(necessary_codeql_environment)
        subprocess.run(f"{bazel_command} {target}", shell=True, env=env, cwd=source_root, check=True)

        os.system(f"{code_ql_path} database finalize -j=0 -- {database_path}")


def analyze_database(code_ql_path, database_path, source_root, query_spec=None, output_prefix="codeql", output_dir=None):
    """Run CodeQL analysis on an existing database and generate MISRA compliance reports."""
    if output_dir:
        output_base = output_dir
        os.makedirs(output_base, exist_ok=True)
    else:
        output_base = _get_bazel_info(source_root).get('output_path')

    query_arg = f" {query_spec}" if query_spec else ""

    sarif_path = f"{output_base}/{output_prefix}.sarif"
    csv_path = f"{output_base}/{output_prefix}.csv"

    subprocess.run(
        f"{code_ql_path} database analyze -j=0 {database_path}{query_arg} --format=sarifv2.1.0 --output={sarif_path}",
        shell=True, check=True)
    subprocess.run(
        f"{code_ql_path} database analyze -j=0 {database_path}{query_arg} --format=csv --output={csv_path}",
        shell=True, check=True)

    # Automatically generate MISRA C++ compliance reports
    generate_compliance_reports(database_path, sarif_path, source_root)


def generate_compliance_reports(database_path, sarif_path, source_root):
    """Generate MISRA C++ compliance reports directly from SARIF file.

    Parses SARIF JSON and creates markdown reports without external dependencies.
    """
    reports_dir = os.path.join(source_root, "quality/static_analysis/codeql_reports")

    try:
        print(f"\n✓ Generating MISRA C++ compliance reports from SARIF analysis...")

        # Create reports directory
        os.makedirs(reports_dir, exist_ok=True)

        # Parse SARIF file
        if not os.path.exists(sarif_path):
            print(f"⚠️  SARIF file not found at {sarif_path}")
            return

        with open(sarif_path, 'r') as f:
            sarif_data = json.load(f)

        # Extract results from SARIF
        results_by_rule = {}
        total_issues = 0

        if "runs" in sarif_data and len(sarif_data["runs"]) > 0:
            run = sarif_data["runs"][0]

            # Collect results by rule ID
            if "results" in run:
                for result in run["results"]:
                    rule_id = result.get("ruleId", "UNKNOWN")
                    message = result.get("message", {}).get("text", "No description")
                    severity = result.get("level", "warning")
                    location = result.get("locations", [{}])[0].get("physicalLocation", {}).get("artifactLocation", {}).get("uri", "unknown")

                    if rule_id not in results_by_rule:
                        results_by_rule[rule_id] = []

                    results_by_rule[rule_id].append({
                        "message": message,
                        "severity": severity,
                        "location": location
                    })
                    total_issues += 1

        # Generate detailed findings report
        findings_report = os.path.join(reports_dir, "findings_report.md")
        with open(findings_report, 'w') as f:
            f.write("# CodeQL MISRA C++ Findings Report\n\n")
            f.write(f"**Analysis Date:** {datetime.datetime.now().isoformat()}\n")
            f.write(f"**Total Issues Found:** {total_issues}\n")
            f.write(f"**Rules Triggered:** {len(results_by_rule)}\n\n")

            f.write("## Issues by Rule\n\n")
            for rule_id in sorted(results_by_rule.keys()):
                issues = results_by_rule[rule_id]
                f.write(f"### {rule_id} ({len(issues)} issues)\n\n")
                for issue in issues[:10]:  # Show first 10 per rule
                    f.write(f"- **Severity:** {issue['severity']}\n")
                    f.write(f"  **File:** {issue['location']}\n")
                    f.write(f"  **Message:** {issue['message']}\n\n")
                if len(issues) > 10:
                    f.write(f"- ... and {len(issues) - 10} more issues\n\n")

        # Generate compliance summary report
        summary_report = os.path.join(reports_dir, "guideline_compliance_summary.md")
        with open(summary_report, 'w') as f:
            f.write("# MISRA C++ Compliance Summary\n\n")
            f.write(f"**Generated:** {datetime.datetime.now().isoformat()}\n\n")
            f.write("## Analysis Results\n\n")
            f.write(f"- **Total Issues:** {total_issues}\n")
            f.write(f"- **Rules Triggered:** {len(results_by_rule)}\n")
            f.write(f"- **Database Location:** {database_path}\n")
            f.write(f"- **SARIF File:** {sarif_path}\n\n")

            # Severity breakdown
            severity_counts = {"error": 0, "warning": 0, "note": 0}
            for issues in results_by_rule.values():
                for issue in issues:
                    severity = issue["severity"].lower()
                    if severity in severity_counts:
                        severity_counts[severity] += 1

            f.write("## Severity Breakdown\n\n")
            f.write(f"- **Errors:** {severity_counts['error']}\n")
            f.write(f"- **Warnings:** {severity_counts['warning']}\n")
            f.write(f"- **Notes:** {severity_counts['note']}\n\n")

            if total_issues == 0:
                f.write("✅ **Status:** COMPLIANT - No MISRA C++ violations found!\n")
            else:
                f.write(f"⚠️  **Status:** {total_issues} issues require review\n")

            f.write(f"\n## Top Rules Triggered\n\n")
            top_rules = sorted(results_by_rule.items(), key=lambda x: len(x[1]), reverse=True)[:5]
            for rule_id, issues in top_rules:
                f.write(f"- {rule_id}: {len(issues)} occurrences\n")

        # Generate SARIF metadata report
        metadata_report = os.path.join(reports_dir, "analysis_metadata.md")
        with open(metadata_report, 'w') as f:
            f.write("# CodeQL Analysis Metadata\n\n")
            f.write(f"**SARIF Version:** {sarif_data.get('version', 'unknown')}\n")
            f.write(f"**Analysis Tool:** CodeQL\n")
            f.write(f"**Language:** C/C++\n")
            f.write(f"**Standards:** MISRA C++ 2023\n\n")
            f.write(f"**Reports Generated:**\n")
            f.write(f"- Findings Report: findings_report.md\n")
            f.write(f"- Compliance Summary: guideline_compliance_summary.md\n")
            f.write(f"- Analysis Metadata: analysis_metadata.md\n")
            f.write(f"- Detailed Results: codeql_analysis_results.md\n\n")
            f.write(f"**Raw Data Files:**\n")
            f.write(f"- SARIF: {sarif_path}\n")
            f.write(f"- Database: {database_path}\n")

        # Generate detailed results table
        results_report = os.path.join(reports_dir, "codeql_analysis_results.md")
        with open(results_report, 'w') as f:
            f.write("# Detailed CodeQL Analysis Results\n\n")
            f.write("| Rule ID | Severity | Location | Message |\n")
            f.write("|---------|----------|----------|----------|\n")

            all_issues = []
            for rule_id, issues in results_by_rule.items():
                for issue in issues:
                    all_issues.append((rule_id, issue))

            # Sort by severity, then rule
            severity_order = {"error": 0, "warning": 1, "note": 2}
            all_issues.sort(key=lambda x: (severity_order.get(x[1]["severity"].lower(), 3), x[0]))

            for rule_id, issue in all_issues[:100]:  # Limit to 100 rows
                f.write(f"| {rule_id} | {issue['severity']} | {issue['location']} | {issue['message'][:50]}... |\n")

            if len(all_issues) > 100:
                f.write(f"\n... and {len(all_issues) - 100} more results in SARIF file\n")

        print(f"✓ Compliance reports generated at: {reports_dir}")
        print(f"  - findings_report.md")
        print(f"  - guideline_compliance_summary.md")
        print(f"  - analysis_metadata.md")
        print(f"  - codeql_analysis_results.md")

        # Display summary
        with open(summary_report, 'r') as f:
            lines = f.readlines()
            print("\n" + "="*60)
            for line in lines[:20]:
                print(line.rstrip())
            print("="*60 + "\n")

    except Exception as e:
        print(f"⚠️  Error generating compliance reports: {e}")
        import traceback
        traceback.print_exc()
        print("   Database and SARIF analysis completed successfully")



def main():
    parser = argparse.ArgumentParser(
        description="Run CodeQL linting operations"
    )
    parser.add_argument(
        "--codeql_path",
        help="Path to the CodeQL binary"
    )
    parser.add_argument(
        "--config_path"
    )
    parser.add_argument(
        "--target",
        nargs="+",
        help="Bazel target pattern(s) to build during tracing. Multiple targets can be supplied."
    )
    parser.add_argument(
        "--phase",
        choices=["create-database", "analyze-database", "all"],
        default="all",
        help="Phase to run: create-database, analyze-database, or all (default)"
    )
    parser.add_argument(
        "--database-path",
        help="Path to store/load the CodeQL database. "
             "Required for create-database and analyze-database phases."
    )
    parser.add_argument(
        "--query-spec",
        help="Query pack/suite spec for codeql database analyze "
             "(e.g. codeql/misra-cpp-coding-standards@2.52.0). "
             "If omitted, uses defaults from codescanning config."
    )
    parser.add_argument(
        "--output-prefix",
        default="codeql",
        help="Prefix for output file names (default: codeql)"
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for output files. If omitted, uses bazel info output_path."
    )

    args = parser.parse_args()
    code_ql_path = args.codeql_path
    config_path = args.config_path
    target = " ".join(args.target) if args.target else ""
    source_root = os.environ["BUILD_WORKING_DIRECTORY"]

    if args.phase == "create-database":
        database_path = args.database_path
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        create_database(code_ql_path, config_path, target, source_root, database_path)

    elif args.phase == "analyze-database":
        database_path = args.database_path
        analyze_database(code_ql_path, database_path, source_root,
                         query_spec=args.query_spec, output_prefix=args.output_prefix,
                         output_dir=args.output_dir)

    elif args.phase == "all":
        os.makedirs(TMP_PATH_FOR_DATABASES, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP_PATH_FOR_DATABASES) as database_location:
            create_database(code_ql_path, config_path, target, source_root, database_location)
            analyze_database(code_ql_path, database_location, source_root,
                             query_spec=args.query_spec, output_prefix=args.output_prefix,
                             output_dir=args.output_dir)


def _get_action_env_extension(necessary_codeql_environment):
    action_env_extension = ""
    for env_var in necessary_codeql_environment:
        action_env_extension += f" --action_env={env_var}"
    return action_env_extension


def _get_merged_environment(necessary_codeql_environment):
    env = os.environ.copy()
    for env_var in necessary_codeql_environment:
        if env_var in env:
            env[env_var] = f"{necessary_codeql_environment[env_var]}:{env[env_var]}"
        else:
            env[env_var] = necessary_codeql_environment[env_var]
    return env


def _get_bazel_info(source_root):
    result = subprocess.run(
        "bazel info",
        shell=True,
        cwd=source_root,
        capture_output=True,
        text=True,
        check=True
    )

    # Parse the output into a dictionary
    bazel_info = {}
    for line in result.stdout.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            bazel_info[key.strip()] = value.strip()
    return bazel_info


if __name__ == "__main__":
    main()
