# SPDX-License-Identifier: GPL-3.0-or-later
set(srcs "etf.c" "etf_source.c")

# tinfl lives in the ROM of every supported chip; the linux target (host tests) gets the same
# public-domain miniz 1.14 code, compiled against the ROM header.
if(IDF_TARGET STREQUAL "linux")
    list(APPEND srcs "third_party/miniz_tinfl_v114.c")
endif()

idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES esp_rom)

if(IDF_TARGET STREQUAL "linux")
    # The ROM miniz.h hardcodes Xtensa options and redefines them on x86 (a warning GCC cannot
    # disable selectively). As a system include directory its warnings are suppressed; GCC then
    # ignores the duplicate -I entry for the same directory.
    target_include_directories(${COMPONENT_LIB} SYSTEM PRIVATE "${IDF_PATH}/components/esp_rom/include")
    # unmodified third-party code
    set_source_files_properties("third_party/miniz_tinfl_v114.c" PROPERTIES COMPILE_OPTIONS
        "-Wno-misleading-indentation;-Wno-unused-but-set-variable;-Wno-implicit-fallthrough;-Wno-sign-compare")
endif()
