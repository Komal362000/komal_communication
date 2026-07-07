#!/usr/bin/env bash
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
#
# Bundle nightly quality reports into the Pages publish tree.
#
# Usage: bundle_quality_reports.sh <event_name> <workflow_run_id> <repository> [publish_dir]
#
#   event_name       GitHub event name (e.g. workflow_run, push, workflow_dispatch)
#   workflow_run_id  Run ID of the triggering workflow_run event (empty for other events)
#   repository       GitHub repository in owner/repo form
#   publish_dir      Destination directory (default: publish/latest/quality)
#
# Requires GH_TOKEN to be set in the environment.

set -euo pipefail

EVENT_NAME="${1:?event_name required}"
WORKFLOW_RUN_ID="${2:-}"
REPOSITORY="${3:?repository required}"
PUBLISH_DIR="${4:-publish/latest/quality}"

EXPECTED_CODEQL_REPORTS=(
    database_integrity_report.md
    deviations_report.md
    guideline_compliance_summary.md
    guideline_recategorizations_report.md
)

is_placeholder_report() {
    local report_path="${1}"
    grep -Fq "Report not yet available" "${report_path}"
}

download_run_artifact() {
    local run_id="${1}"
    local destination_dir="${2}"

    gh run download "${run_id}" \
        --name nightly-quality-reports \
        --dir "${destination_dir}" \
        --repo "${REPOSITORY}"
}

restore_report_from_previous_run() {
    local report_name="${1}"
    local target_path="${2}"
    local candidate_run_ids="${3}"

    for candidate_run_id in ${candidate_run_ids}; do
        [[ "${candidate_run_id}" == "${RUN_ID}" ]] && continue

        local fallback_dir
        fallback_dir=$(mktemp -d)
        if download_run_artifact "${candidate_run_id}" "${fallback_dir}" >/dev/null 2>&1; then
            local fallback_report
            fallback_report=$(find "${fallback_dir}" -name "${report_name}" -type f -print -quit 2>/dev/null || true)
            if [[ -n "${fallback_report}" ]] && ! is_placeholder_report "${fallback_report}"; then
                cp "${fallback_report}" "${target_path}"
                echo "Restored ${report_name} from nightly run ${candidate_run_id}"
                rm -rf "${fallback_dir}"
                return 0
            fi
        fi
        rm -rf "${fallback_dir}"
    done

    return 1
}

mkdir -p "${PUBLISH_DIR}"

if [[ "${EVENT_NAME}" == "workflow_run" ]]; then
    # Triggered by nightly — download the fresh artifact directly.
    RUN_ID="${WORKFLOW_RUN_ID}"
else
    # Other triggers — restore from the latest successful nightly run so
    # quality reports are preserved in every Pages deployment.
    RUN_ID=$(gh api \
        "repos/${REPOSITORY}/actions/workflows/nightly_quality.yml/runs?status=success&per_page=1" \
        --jq '.workflow_runs[0].id // empty' 2>/dev/null || true)
fi

if [[ -n "${RUN_ID}" ]]; then
    # Download to a temp dir and then copy the contents to the destination.
    TEMP_DIR=$(mktemp -d)
    if gh run download "${RUN_ID}" \
            --name nightly-quality-reports \
            --dir "${TEMP_DIR}" \
            --repo "${REPOSITORY}"; then
        ARTIFACT_DIR="${TEMP_DIR}/nightly-quality-reports"
        # gh CLI typically extracts into ARTIFACT_DIR, but some versions place
        # files directly in TEMP_DIR.  Also, ARTIFACT_DIR may be created but
        # left empty if the artifact contained no files — cp -r "dir/." fails
        # in that case.  Use whichever location actually has content.
        if [[ -d "${ARTIFACT_DIR}" ]] && \
                [[ -n "$(find "${ARTIFACT_DIR}" -maxdepth 1 -mindepth 1 2>/dev/null)" ]]; then
            SRC_DIR="${ARTIFACT_DIR}"
        else
            SRC_DIR="${TEMP_DIR}"
        fi
        if [[ -n "$(find "${SRC_DIR}" -maxdepth 1 -mindepth 1 2>/dev/null)" ]]; then
            cp -r "${SRC_DIR}/." "${PUBLISH_DIR}/"
            echo "Quality reports bundled into ${PUBLISH_DIR}/"
        else
            echo "::warning::Quality artifact downloaded but no files found — skipping."
        fi

        if [[ "${EVENT_NAME}" == "workflow_run" ]]; then
            FALLBACK_RUN_IDS=$(gh api \
                "repos/${REPOSITORY}/actions/workflows/nightly_quality.yml/runs?status=success&per_page=20" \
                --jq '.workflow_runs[].id' 2>/dev/null || true)

            for report_name in "${EXPECTED_CODEQL_REPORTS[@]}"; do
                report_path="${PUBLISH_DIR}/${report_name}"
                if [[ -f "${report_path}" ]] && ! is_placeholder_report "${report_path}"; then
                    continue
                fi

                if restore_report_from_previous_run "${report_name}" "${report_path}" "${FALLBACK_RUN_IDS}"; then
                    continue
                fi

                title=$(echo "${report_name%.md}" | sed 's/_/ /g' | sed 's/\b\(.\)/\u\1/g')
                cat > "${report_path}" <<EOF
# ${title}

> Report not yet available — will be generated on the next successful CodeQL nightly run.

This report is expected to be produced by the analysis_report tool as part of
the MISRA C++ compliance analysis pipeline.
EOF
            done
        fi
    else
        echo "Quality artifact not available for run ${RUN_ID} — skipping."
    fi
    rm -rf "${TEMP_DIR}"
else
    echo "No successful nightly run found — quality reports not included."
fi
