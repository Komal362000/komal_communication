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
#include "score/mw/com/impl/e2e/e2e_profile_stub.h"

#include <gtest/gtest.h>

#include <array>
#include <cstddef>
#include <cstdint>

namespace score::mw::com::impl::e2e
{
namespace
{

constexpr ProfileConfiguration kConfiguration{0x3AU, 2U};
constexpr std::array<std::byte, 3U> kPayload{std::byte{0x01U}, std::byte{0x02U}, std::byte{0x03U}};

using Header = std::array<std::byte, kProfileStubHeaderSize>;

score::cpp::span<std::byte> AsWritableSpan(Header& header) noexcept
{
    return {header.data(), header.size()};
}

score::cpp::span<const std::byte> AsReadOnlySpan(const Header& header) noexcept
{
    return {header.data(), header.size()};
}

score::cpp::span<const std::byte> PayloadSpan() noexcept
{
    return {kPayload.data(), kPayload.size()};
}

TEST(E2eProfileStubTest, ProtectAndCheckValidFrameProducesOkStatuses)
{
    Header header{};
    ProtectContext protect_context{};
    CheckContext check_context{};

    ASSERT_TRUE(ProtectMessage(AsWritableSpan(header), PayloadSpan(), kConfiguration, protect_context));

    const auto outcome = CheckMessage(AsReadOnlySpan(header), PayloadSpan(), kConfiguration, check_context);

    EXPECT_EQ(outcome.data_integrity, DataIntegrityStatus::kOk);
    EXPECT_EQ(outcome.sequence, SequenceStatus::kOk);
    EXPECT_EQ(protect_context.next_counter, 1U);
}

TEST(E2eProfileStubTest, CheckTamperedHeaderReportsDataIntegrityErrorAndRetainsSequenceState)
{
    Header header{};
    ProtectContext protect_context{};
    CheckContext check_context{};

    ASSERT_TRUE(ProtectMessage(AsWritableSpan(header), PayloadSpan(), kConfiguration, protect_context));
    header[2U] ^= std::byte{0x01U};

    const auto outcome = CheckMessage(AsReadOnlySpan(header), PayloadSpan(), kConfiguration, check_context);

    EXPECT_EQ(outcome.data_integrity, DataIntegrityStatus::kError);
    EXPECT_EQ(outcome.sequence, SequenceStatus::kOk);
    EXPECT_FALSE(check_context.has_last_counter);
}

TEST(E2eProfileStubTest, CheckSameValidFrameTwiceReportsRepeatedCounter)
{
    Header header{};
    ProtectContext protect_context{};
    CheckContext check_context{};

    ASSERT_TRUE(ProtectMessage(AsWritableSpan(header), PayloadSpan(), kConfiguration, protect_context));
    ASSERT_EQ(CheckMessage(AsReadOnlySpan(header), PayloadSpan(), kConfiguration, check_context).sequence,
              SequenceStatus::kOk);

    const auto outcome = CheckMessage(AsReadOnlySpan(header), PayloadSpan(), kConfiguration, check_context);

    EXPECT_EQ(outcome.data_integrity, DataIntegrityStatus::kOk);
    EXPECT_EQ(outcome.sequence, SequenceStatus::kErrorRepeated);
}

TEST(E2eProfileStubTest, CheckSkippedCounterWithinConfiguredThresholdReportsGapWithinThreshold)
{
    Header first_header{};
    Header ignored_header{};
    Header checked_header{};
    ProtectContext protect_context{};
    CheckContext check_context{};

    ASSERT_TRUE(ProtectMessage(AsWritableSpan(first_header), PayloadSpan(), kConfiguration, protect_context));
    ASSERT_TRUE(ProtectMessage(AsWritableSpan(ignored_header), PayloadSpan(), kConfiguration, protect_context));
    ASSERT_TRUE(ProtectMessage(AsWritableSpan(checked_header), PayloadSpan(), kConfiguration, protect_context));
    ASSERT_EQ(CheckMessage(AsReadOnlySpan(first_header), PayloadSpan(), kConfiguration, check_context).sequence,
              SequenceStatus::kOk);

    const auto outcome = CheckMessage(AsReadOnlySpan(checked_header), PayloadSpan(), kConfiguration, check_context);

    EXPECT_EQ(outcome.data_integrity, DataIntegrityStatus::kOk);
    EXPECT_EQ(outcome.sequence, SequenceStatus::kOkGapWithinThreshold);
}

TEST(E2eProfileStubTest, CheckSkippedCounterBeyondConfiguredThresholdReportsGapError)
{
    constexpr ProfileConfiguration kStrictConfiguration{0x3AU, 1U};
    Header first_header{};
    Header ignored_header{};
    Header checked_header{};
    ProtectContext protect_context{};
    CheckContext check_context{};

    ASSERT_TRUE(ProtectMessage(AsWritableSpan(first_header), PayloadSpan(), kStrictConfiguration, protect_context));
    ASSERT_TRUE(ProtectMessage(AsWritableSpan(ignored_header), PayloadSpan(), kStrictConfiguration, protect_context));
    ASSERT_TRUE(ProtectMessage(AsWritableSpan(checked_header), PayloadSpan(), kStrictConfiguration, protect_context));
    ASSERT_EQ(CheckMessage(AsReadOnlySpan(first_header), PayloadSpan(), kStrictConfiguration, check_context).sequence,
              SequenceStatus::kOk);

    const auto outcome =
        CheckMessage(AsReadOnlySpan(checked_header), PayloadSpan(), kStrictConfiguration, check_context);

    EXPECT_EQ(outcome.data_integrity, DataIntegrityStatus::kOk);
    EXPECT_EQ(outcome.sequence, SequenceStatus::kErrorGapExceedsThreshold);
}

TEST(E2eProfileStubTest, ProtectRejectsHeaderWithIncorrectSize)
{
    std::array<std::byte, kProfileStubHeaderSize - 1U> too_small_header{};
    ProtectContext protect_context{};

    const bool result = ProtectMessage(
        {too_small_header.data(), too_small_header.size()}, PayloadSpan(), kConfiguration, protect_context);

    EXPECT_FALSE(result);
    EXPECT_EQ(protect_context.next_counter, 0U);
}

}  // namespace
}  // namespace score::mw::com::impl::e2e
