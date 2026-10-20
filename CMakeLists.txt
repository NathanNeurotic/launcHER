# launcHER standalone build
cmake_minimum_required(VERSION 3.13)

include($ENV{PS2SDK}/ps2dev.cmake)
set(BIN2C "$ENV{PS2SDK}/bin/bin2c")
set(PS2_PACKER "$ENV{PS2DEV}/bin/ps2-packer")

include(${CMAKE_SOURCE_DIR}/cmake/functions.cmake)

# Remove the default linkfile from CMAKE_EXE_LINKER_FLAGS_INIT.
# Individual targets add their own linker scripts.
string(REGEX REPLACE "-T[^ ]*linkfile[^ ]*" "" CLEANED_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS_INIT}")
string(REGEX REPLACE "  +" " " CLEANED_LINKER_FLAGS "${CLEANED_LINKER_FLAGS}")
string(STRIP "${CLEANED_LINKER_FLAGS}" CLEANED_LINKER_FLAGS)
set(CMAKE_EXE_LINKER_FLAGS_INIT "${CLEANED_LINKER_FLAGS}")

project(launcHER C ASM)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(ENABLE_PRINTF "Enable printf debugging output" OFF)
option(USE_EESIO "Use EE SIO for debugging" ON)
option(DEBUG "Disable stripping ELFs (keeps debug symbols)" ON)
option(LAUNCHER_BOOT_TRACE "Show persistent boot-stage diagnostics and stop on errors" ON)
option(LAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF "Stop after verified POPS preflight instead of entering Sony code" OFF)
set(LAUNCHER_BOOT_TRACE_RECOVERY_ELF "" CACHE STRING "Optional installed ELF to relaunch after a diagnostic error")
if(LAUNCHER_BOOT_TRACE)
    add_compile_definitions(LAUNCHER_BOOT_TRACE)
    if(LAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF)
        add_compile_definitions(LAUNCHER_BOOT_TRACE_STOP_BEFORE_HANDOFF)
    endif()
    if(LAUNCHER_BOOT_TRACE_RECOVERY_ELF)
        add_compile_definitions(LAUNCHER_BOOT_TRACE_RECOVERY_ELF="${LAUNCHER_BOOT_TRACE_RECOVERY_ELF}")
    endif()
endif()

# Standalone Ember launcher profile. Keep the storage transports Ember can use,
# and drop the OSDMenu/HOSDMenu/MBR/CD/DVD/XFROM pieces from this fork's build.
set(LAUNCHER_OSDM OFF CACHE BOOL "OSDMenu handler" FORCE)
set(LAUNCHER_MMCE ON CACHE BOOL "MMCE support" FORCE)
set(LAUNCHER_USB ON CACHE BOOL "USB support" FORCE)
set(LAUNCHER_ATA ON CACHE BOOL "exFAT HDD support" FORCE)
set(LAUNCHER_MX4SIO ON CACHE BOOL "MX4SIO support" FORCE)
set(LAUNCHER_APA ON CACHE BOOL "APA HDD support" FORCE)
set(LAUNCHER_CDROM OFF CACHE BOOL "CD/DVD support" FORCE)
set(LAUNCHER_ILINK ON CACHE BOOL "i.Link support" FORCE)
set(LAUNCHER_UDPBD ON CACHE BOOL "UDPBD support" FORCE)
set(LAUNCHER_UDPFS ON CACHE BOOL "UDPFS support" FORCE)
set(LAUNCHER_SMB ON CACHE BOOL "SMBv1 filesystem support" FORCE)
set(LAUNCHER_XFROM OFF CACHE BOOL "XFROM support" FORCE)

# Only the embedded ELF loader and standalone launcher are required.
add_subdirectory(utils/loader)
add_subdirectory(launcher)

# Distributable: launcher, editable configuration, and build identifier.
add_custom_target(launcHER ALL
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/release"
    COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_BINARY_DIR}/launcher/launcher.elf" "${CMAKE_BINARY_DIR}/release/launcHER.elf"
    COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/examples/launcHER.CNF" "${CMAKE_BINARY_DIR}/release/launcHER.CNF"
    COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/launcher/iop/smbman/SMB-NOTICES.txt" "${CMAKE_BINARY_DIR}/release/SMB-NOTICES.txt"
    COMMAND ${CMAKE_COMMAND}
        "-DLAUNCHER_SOURCE_DIR=${CMAKE_SOURCE_DIR}"
        "-DLAUNCHER_VERSION_FILE=${CMAKE_BINARY_DIR}/release/version.txt"
        -P "${CMAKE_SOURCE_DIR}/cmake/write_version.cmake"
    DEPENDS launcher
    COMMENT "Packaging launcHER.elf, launcHER.CNF and version.txt"
)
