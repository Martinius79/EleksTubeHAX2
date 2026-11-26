# SPDX-License-Identifier: GPL-3.0-or-later
# Host unit tests (ESP-IDF "linux" target + Unity), see D-014 and tools/host_test.py.
cmake_minimum_required(VERSION 3.22)

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../../components")
set(COMPONENTS main)  # plus everything main REQUIRES

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# AddressSanitizer + UBSan: out-of-bounds accesses abort the test run instead of passing
# silently (a decoder that overruns a row buffer may still report the expected error).
# No alignment check: miniz.h enables unaligned loads on x86 only (off on the chips).
idf_build_set_property(COMPILE_OPTIONS "-fsanitize=address,undefined;-fno-omit-frame-pointer;-fno-sanitize-recover=all;-fno-sanitize=alignment" APPEND)
idf_build_set_property(LINK_OPTIONS "-fsanitize=address,undefined" APPEND)

project(host_tests)
