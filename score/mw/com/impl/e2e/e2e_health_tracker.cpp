/********************************************************************************
 * Copyright (c) 2026 Contributors to the Eclipse Foundation
 *
 * See the NOTICE file(s) distributed with this work for additional
 * information regarding copyright ownership.
 *
 * This program and the accompanying materials are made available under the
 * terms of the Apache License Version 2.0 which is available at
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * SPDX-License-Identifier: Apache-2.0
 ********************************************************************************/
#include "score/mw/com/impl/e2e/e2e_health_tracker.h"

#include <score/assert.hpp>

#include <limits>

namespace score::mw::com::impl::e2e
{| H2n["sequence:\nkDisabled"]
      H1y --> D3{HistoricalHealthTrackingEnabled\nAND at least one check above enabled?}
      H1n --> D3
      H2y --> D3
      H2n --> D3
      D3 -->|Yes| E[Hysteresis check] --> G1["historical_health:\nkOk / kError"]
      D3 -->|No| G2["historical_health:\nkDisabled"]
      H1y --> I["SamplePtr::GetE2EResult()\nreturns E2EResult{data_integrity, sequence,\nhistorical_health, summary}"]
      H1n --> I
      H2y --> I
      H2n --> I
      G1 --> I
      G2 --> I
      I --> J["summary field\nreduced-view consumer\nchecks only this"]
      I --> K["data_integrity / sequence / historical_health fields\ndetailed-view consumer inspects\nindividually for full diagnostics"]
  ```

  ## 3. Design rationale

  The error classes are kept separate (`data_integrity`, `sequence`,
  `historical_health`) so each underlying concept stays easy to reason about;
  `summary` is provided purely as a simplification for callers that just want
  to know whether a sample is "fine to use".


void ValidateHealthTrackerConfiguration(const HealthTrackerConfiguration& config) noexcept
{
    SCORE_LANGUAGE_FUTURECPP_PRECONDITION_PRD_MESSAGE(config.error_threshold >= 1U,
                                                       "error_threshold must be at least 1");
    SCORE_LANGUAGE_FUTURECPP_PRECONDITION_PRD_MESSAGE(
        config.recovery_threshold < config.error_threshold,
        "recovery_threshold must be strictly less than error_threshold");
}

HistoricalHealthStatus UpdateHistoricalHealth(const DataIntegrityStatus data_integrity,
                                              const SequenceStatus sequence,
                                              const HealthTrackerConfiguration& config,
                                              HealthContext& context) noexcept
{
    ValidateHealthTrackerConfiguration(config);

    if (!config.enabled)
    {
        return HistoricalHealthStatus::kDisabled;
    }

    const bool data_integrity_failed{data_integrity == DataIntegrityStatus::kError};
    const bool sequence_failed{(sequence == SequenceStatus::kErrorRepeated) ||
                                (sequence == SequenceStatus::kErrorGapExceedsThreshold)};
    const bool this_sample_failed{data_integrity_failed || sequence_failed};

    if (this_sample_failed)
    {
        if (context.error_counter < std::numeric_limits<std::uint8_t>::max())
        {
            ++context.error_counter;
        }
    }
    else if (context.error_counter > 0U)
    {
        --context.error_counter;
    }

    if (context.error_counter >= config.error_threshold)
    {
        context.is_currently_error = true;
    }
    else if (context.error_counter <= config.recovery_threshold)
    {
        context.is_currently_error = false;
    }

    return context.is_currently_error ? HistoricalHealthStatus::kError : HistoricalHealthStatus::kOk;
}

}  // namespace score::mw::com::impl::e2e
