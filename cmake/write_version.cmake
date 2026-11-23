# Generate a one-line build identifier for the distributable launcher.
# Run at build time so incremental builds do not retain a stale configure-time SHA.
if(NOT DEFINED LAUNCHER_SOURCE_DIR OR NOT DEFINED LAUNCHER_VERSION_FILE)
  message(FATAL_ERROR "LAUNCHER_SOURCE_DIR and LAUNCHER_VERSION_FILE are required")
endif()

set(launcher_version "")

# Tagged releases use their public version; rolling builds use the source commit.
if(DEFINED ENV{GITHUB_REF} AND "$ENV{GITHUB_REF}" MATCHES "^refs/tags/(v[0-9][0-9A-Za-z._-]*)$")
  set(launcher_version "${CMAKE_MATCH_1}")
elseif(DEFINED ENV{GITHUB_SHA} AND "$ENV{GITHUB_SHA}" MATCHES "^[0-9a-fA-F]+$")
  string(LENGTH "$ENV{GITHUB_SHA}" sha_length)
  if(sha_length GREATER_EQUAL 12)
    string(SUBSTRING "$ENV{GITHUB_SHA}" 0 12 launcher_version)
  endif()
endif()

if(launcher_version STREQUAL "")
  find_program(GIT_EXECUTABLE git)
  if(GIT_EXECUTABLE)
    execute_process(
      COMMAND "${GIT_EXECUTABLE}" -C "${LAUNCHER_SOURCE_DIR}" rev-parse --short=12 HEAD
      OUTPUT_VARIABLE launcher_version
      OUTPUT_STRIP_TRAILING_WHITESPACE
      ERROR_QUIET
      RESULT_VARIABLE git_result
    )
    if(NOT git_result EQUAL 0)
      set(launcher_version "")
    endif()
  endif()
endif()

# Source archives without Git history are still buildable. CI rejects this
# fallback so published packages always identify a specific build.
if(launcher_version STREQUAL "")
  set(launcher_version "unknown")
  message(WARNING "No Git revision available: writing version=unknown")
endif()

file(WRITE "${LAUNCHER_VERSION_FILE}" "version=${launcher_version}\n")
