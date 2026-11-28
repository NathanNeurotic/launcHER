# OSDMenu Launcher

# Launcher configuration options
option(LAUNCHER_OSDM "Support for handling OSDMenu arguments" ON)
option(LAUNCHER_MMCE "Support for loading ELFs from MMCE" ON)
option(LAUNCHER_USB "Support for loading ELFs from USB" ON)
option(LAUNCHER_ATA "Support for loading ELFs from exFAT internal HDD" ON)
option(LAUNCHER_MX4SIO "Support for loading ELFs from MX4SIO" ON)
option(LAUNCHER_APA "Support for loading ELFs from APA-formatted HDD" ON)
option(LAUNCHER_CDROM "Support for loading PS1 and PS2 CDs/DVDs" ON)
option(LAUNCHER_ILINK "Support for loading ELFs from iLink" OFF)
option(LAUNCHER_UDPBD "Support for loading ELFs from UDPBD" OFF)
option(LAUNCHER_UDPFS "Support for loading ELFs from UDPFS" OFF)
option(LAUNCHER_XFROM "Support for loading ELFs from XFROM" ON)

# Base sources
set(EE_SOURCES
    src/main.c
    src/common.c
    src/init.c
    src/handler_mc.c
    src/handler_quickboot.c
)

# Common files
list(APPEND EE_SOURCES
    ../common/src/history.c
    ../common/src/game_id.c
    ../common/src/cnf.c
    ../common/src/loader.c
    ../common/src/launch_args.c
    ../common/src/dprintf.c
)

# IRX files
set(IRX_FILES
    ppctty.irx
    iomanX.irx
    fileXio.irx
    sio2man.irx
    mcman.irx
    mcserv.irx
)

# ELF files
set(ELF_FILES
    loader.elf
)

set(EE_LIBS
    cdvd
    patches
    kernel
    libdebug.a
    fileXio
    gskit
    dmakit
    mc
    poweroff
    secr
)

# Base modules
set(IRX_SOURCES)
foreach(irx ${IRX_FILES})
  get_filename_component(irx_name ${irx} NAME_WE)
  irx_to_source("$ENV{PS2SDK}/iop/irx/${irx}" irx_source "${irx_name}_irx" "")
  list(APPEND IRX_SOURCES ${irx_source})
endforeach()

# OSDM support
if(LAUNCHER_OSDM)
  list(APPEND EE_SOURCES src/handler_osdm.c)
  list(APPEND IRX_FILES poweroff.irx)
  add_compile_definitions(OSDM)
  set(LAUNCHER_CDROM ON)  # OSDM implies CDROM
endif()

# MMCE support
if(LAUNCHER_MMCE)
  list(APPEND IRX_FILES mmceman.irx)
  add_compile_definitions(MMCE)
  set(SIO2MAN ON)

  # Build mmceman from the submodule, with the same file-system fixes RiptOPL ships to Ember
  # (Open-PS2-Loader .github/scripts/install_coherent_mmce.sh, same pin and patches).
  # Ember lists games/<folder> to pick its .cue/.bin through this driver. Unpatched, a
  # listing opened while the card's descriptor 0 is free (the normal case right after
  # launcHER's IOP reset) returns 0 for its first entry, which reads as end of directory,
  # so Ember sees an empty game folder. The patches are applied to a copy in the build
  # directory; the submodule checkout stays clean. A patch that stops applying fails the build.
  set(MMCEMAN_IRX "${CMAKE_CURRENT_BINARY_DIR}/mmceman.irx")
  set(MMCEMAN_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/iop/mmceman/mmceman")
  set(MMCEMAN_WORK_DIR "${CMAKE_CURRENT_BINARY_DIR}/mmceman-src")
  set(MMCEMAN_PATCH_DIR "${CMAKE_CURRENT_SOURCE_DIR}/iop/mmceman-patches")
  # Order matters: the same order RiptOPL applies them in
  set(MMCEMAN_PATCHES
      "${MMCEMAN_PATCH_DIR}/mmceman-fs-close-fd-leak.patch"
      "${MMCEMAN_PATCH_DIR}/mmceman-fs-open-enoent.patch"
      "${MMCEMAN_PATCH_DIR}/mmceman-fs-dopen-enoent.patch"
      "${MMCEMAN_PATCH_DIR}/mmceman-fs-dread-eof.patch"
      "${MMCEMAN_PATCH_DIR}/mmceman-fs-dread-entry.patch")
  set(MMCEMAN_APPLY_COMMANDS)
  foreach(patch ${MMCEMAN_PATCHES})
    # The copy sits inside launcHER's own work tree, where git apply would silently skip every
    # path ("Skipped patch") and exit 0. The ceiling stops git from finding that repository.
    list(APPEND MMCEMAN_APPLY_COMMANDS COMMAND ${CMAKE_COMMAND} -E chdir "${MMCEMAN_WORK_DIR}"
         ${CMAKE_COMMAND} -E env "GIT_CEILING_DIRECTORIES=${CMAKE_CURRENT_BINARY_DIR}" git apply --verbose "${patch}")
  endforeach()
  file(GLOB MMCEMAN_SOURCES "${MMCEMAN_SRC_DIR}/src/*" "${MMCEMAN_SRC_DIR}/include/*" "${MMCEMAN_SRC_DIR}/Makefile")
  add_custom_command(
        OUTPUT ${MMCEMAN_IRX}
        COMMAND ${CMAKE_COMMAND} "-DTREE=${MMCEMAN_WORK_DIR}" -P "${MMCEMAN_PATCH_DIR}/remove_tree.cmake"
        COMMAND ${CMAKE_COMMAND} -E make_directory "${MMCEMAN_WORK_DIR}"
        COMMAND ${CMAKE_COMMAND} -E copy_directory "${MMCEMAN_SRC_DIR}" "${MMCEMAN_WORK_DIR}/mmceman"
        ${MMCEMAN_APPLY_COMMANDS}
        COMMAND ${CMAKE_COMMAND} -E make_directory "${MMCEMAN_WORK_DIR}/mmceman/obj"
        COMMAND ${CMAKE_COMMAND} -E chdir "${MMCEMAN_WORK_DIR}/mmceman" ${CMAKE_MAKE_PROGRAM}
        COMMAND ${CMAKE_COMMAND} -E copy
            "${MMCEMAN_WORK_DIR}/mmceman/irx/mmceman.irx"
            ${MMCEMAN_IRX}
        DEPENDS ${MMCEMAN_SOURCES} ${MMCEMAN_PATCHES}
        COMMENT "Building mmceman (with RiptOPL file-system patches)"
        VERBATIM
    )
endif()

# USB support
if(LAUNCHER_USB)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  list(APPEND IRX_FILES usbd_mini.irx usbmass_bd_mini.irx)
  add_compile_definitions(USB)
  set(BDM ON)
endif()

# APA support
if(LAUNCHER_APA)
  list(APPEND EE_SOURCES src/handler_pfs.c src/handler_patinfo.c ../common/src/patinfo.c)
  list(APPEND IRX_FILES ps2hdd-osd.irx ps2fs.irx secrsif.irx)
  add_compile_definitions(APA)
  set(LAUNCHER_ATA ON)  # APA implies ATA
  set(DEV9 ON)
endif()

# ATA support
if(LAUNCHER_ATA)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  list(APPEND IRX_FILES ata_bd.irx)
  add_compile_definitions(ATA)
  set(BDM ON)
  set(DEV9 ON)
endif()

# MX4SIO support
if(LAUNCHER_MX4SIO)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  list(APPEND IRX_FILES mx4sio_bd_mini.irx)
  add_compile_definitions(MX4SIO)
  set(SIO2MAN ON)
  set(BDM ON)
endif()

# iLink support
if(LAUNCHER_ILINK)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  list(APPEND IRX_FILES iLinkman.irx IEEE1394_bd_mini.irx)
  add_compile_definitions(ILINK)
  set(BDM ON)
endif()

# UDPBD support
if(LAUNCHER_UDPBD)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  add_compile_definitions(UDPBD)
  set(BDM ON)
  set(SMAP ON)

  list(APPEND IRX_FILES udpbd.irx)
  add_custom_target(udpbd
        COMMAND ${CMAKE_COMMAND} -E chdir "${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/udpbd" ${CMAKE_MAKE_PROGRAM}
        COMMENT "Building udpbd"
    )
endif()

# UDPFS support
if(LAUNCHER_UDPFS)
  list(APPEND EE_SOURCES src/handler_udpfs.c)
  add_compile_definitions(UDPFS)
  set(SMAP ON)

  list(APPEND IRX_FILES udpfs_ioman.irx)
  add_custom_target(udpfs_ioman
        COMMAND ${CMAKE_COMMAND} -E chdir "${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/udpfs" ${CMAKE_MAKE_PROGRAM} UDPFS_IOMAN=1
        COMMENT "Building udpfs_ioman"
    )
endif()

# CDROM support
if(LAUNCHER_CDROM)
  list(APPEND EE_SOURCES src/handler_cdrom.c)
  list(APPEND IRX_FILES xparam.irx)
  list(APPEND ELF_FILES ps1vn.elf)
  add_compile_definitions(CDROM)
endif()

# XFROM support
if(LAUNCHER_XFROM)
  set(DEV9 ON)
  list(APPEND IRX_FILES extflash.irx xfromman.irx)
  add_compile_definitions(XFROM)
endif()

if (SMAP)
  set(DEV9 ON)
  list(APPEND IRX_FILES smap.irx ministack.irx)

  add_custom_target(smap
        COMMAND ${CMAKE_COMMAND} -E chdir "${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/smap" ${CMAKE_MAKE_PROGRAM}
        COMMENT "Building smap"
    )
  add_custom_target(ministack
        COMMAND ${CMAKE_COMMAND} -E chdir "${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/ministack" ${CMAKE_MAKE_PROGRAM}
        COMMENT "Building ministack"
    )
endif()

# Driver dependencies
if(DEV9)
  list(APPEND IRX_FILES ps2dev9.irx)
endif()

if(BDM)
  list(APPEND EE_SOURCES src/handler_bdm.c)
  list(APPEND IRX_FILES bdm.irx bdmfs_fatfs.irx)
endif()

if(ENABLE_PRINTF)
  add_compile_definitions(ENABLE_PRINTF)
  if (USE_EESIO)
    add_compile_definitions(USE_EESIO)
  endif()
endif()

# Process all IRX files
foreach(irx ${IRX_FILES})
  get_filename_component(irx_name ${irx} NAME_WE)
  string(REPLACE "-" "_" irx_name_clean ${irx_name})

  if(irx_name STREQUAL "udpbd")
    # udpbd is not a part of PS2SDK
    irx_to_source("${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/udpbd/irx/udpbd.irx" irx_source "udpbd_irx" "")
  elseif(irx_name STREQUAL "smap")
    # smap is not a part of PS2SDK
    irx_to_source("${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/smap/irx/smap.irx" irx_source "smap_irx" "")
  elseif(irx_name STREQUAL "ministack")
    # ministack is not a part of PS2SDK
    irx_to_source("${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/ministack/irx/ministack.irx" irx_source "ministack_irx" "")
  elseif(irx_name STREQUAL "udpfs_ioman")
    # udpfs_ioman is not a part of PS2SDK
    irx_to_source("${CMAKE_CURRENT_SOURCE_DIR}/iop/udpfs/udpfs/irx/udpfs_ioman.irx" irx_source "udpfs_ioman_irx" "")
  elseif(irx_name STREQUAL "mmceman")
    # mmceman is built from submodule
    irx_to_source("${MMCEMAN_IRX}" irx_source "mmceman_irx" "")
  else()
    irx_to_source("$ENV{PS2SDK}/iop/irx/${irx}" irx_source "${irx_name_clean}_irx" "")
  endif()

  list(APPEND IRX_SOURCES ${irx_source})
endforeach()


# Convert ELF files to sources
elf_to_source(loader loader_source "loader_elf" "")
list(APPEND ELF_SOURCES ${loader_source})
if("ps1vn.elf" IN_LIST ELF_FILES)
  elf_to_source(ps1vn ps1vn_source "ps1vn_elf" "")
  list(APPEND ELF_SOURCES ${ps1vn_source})
endif()

# Resource files
set(RES_FILES
    icon_A.sys
    icon_C.sys
    icon_J.sys
)

set(RES_SOURCES)
foreach(res ${RES_FILES})
  get_filename_component(res_name ${res} NAME_WE)
  bin2c_source("${CMAKE_SOURCE_DIR}/common/res/${res}" res_source "${res_name}_sys")
  list(APPEND RES_SOURCES ${res_source})
endforeach()

# Create executable
add_executable(launcher_unc ${EE_SOURCES} ${IRX_SOURCES} ${ELF_SOURCES} ${RES_SOURCES})

# Add dependencies on IOP modules built via Makefiles
if(LAUNCHER_UDPBD)
  add_dependencies(launcher_unc udpbd)
endif()

if(LAUNCHER_UDPFS)
  add_dependencies(launcher_unc udpfs_ioman)
endif()

if(SMAP)
  add_dependencies(launcher_unc smap ministack)
endif()

# Add dependencies on ELF targets
add_dependencies(launcher_unc loader)
if("ps1vn.elf" IN_LIST ELF_FILES)
  add_dependencies(launcher_unc ps1vn)
endif()

target_include_directories(launcher_unc PRIVATE
    ../common/include
    include
)

target_compile_options(launcher_unc PRIVATE
    -Os
    -G0
    -Wall
)

# Use the default linker script
target_link_options(launcher_unc PRIVATE
    -T$ENV{PS2SDK}/ee/startup/linkfile
)

link_newlib_nano(launcher_unc
    cdvd
    patches
    kernel
    libdebug.a
    fileXio
    gskit
    dmakit
    mc
    poweroff
    secr
    cglue
    pthread
    pthreadglue
)

if(DEBUG)
  set(launcher_link_flags "")
else()
  set(launcher_link_flags "-s")
endif()
set_target_properties(launcher_unc PROPERTIES
    LINK_FLAGS "${launcher_link_flags}"
)

# Pack ELF
add_custom_target(launcher ALL
    DEPENDS launcher_unc
    COMMAND ${PS2_PACKER} "$<TARGET_FILE:launcher_unc>" "${CMAKE_CURRENT_BINARY_DIR}/launcher.elf"
    COMMENT "Packing launcher.elf"
)

set_target_properties(launcher PROPERTIES
    OUTPUT_NAME "launcher"
)

set_target_properties(launcher_unc PROPERTIES
    OUTPUT_NAME "launcher_unc"
    RUNTIME_OUTPUT_NAME "launcher_unc.elf"
)
