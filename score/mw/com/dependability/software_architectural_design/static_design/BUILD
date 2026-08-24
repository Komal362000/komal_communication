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
load("@score_tooling//bazel/rules/rules_score:rules_score.bzl", "architectural_design")

architectural_design(
    name = "software_architectural_design",
    static = [
        "overall.puml",
        "binding_independent.puml",
        "lola_binding.puml",
        "someip_binding.puml",
        "mock_binding.puml",
    ],
    dynamic = [
        "e2e_error_handling_dynamic.puml",
    ],
    internal_api = [
        "e2e_error_handling_internal_api.puml",
    ],
    # Matches the maturity level of the parent dependable_element (mw_com): this SEooC's
    # architecture is still under active development, so validation findings against the
    # new/evolving E2E diagrams are recorded as warnings rather than failing the build.
    maturity = "development",
    visibility = ["//score/mw/com/dependability:__subpackages__"],
)
