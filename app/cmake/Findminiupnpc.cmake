find_path(MINIUPNPC_INCLUDE_DIR miniupnpc/miniupnpc.h)
find_library(MINIUPNPC_LIBRARY NAMES miniupnpc)

if(MINIUPNPC_INCLUDE_DIR AND MINIUPNPC_LIBRARY)
    set(miniupnpc_FOUND TRUE)
    if(NOT TARGET miniupnpc::miniupnpc)
        add_library(miniupnpc::miniupnpc UNKNOWN IMPORTED)
        set_target_properties(miniupnpc::miniupnpc PROPERTIES
            IMPORTED_LOCATION "${MINIUPNPC_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${MINIUPNPC_INCLUDE_DIR}")
    endif()
else()
    set(miniupnpc_FOUND FALSE)
endif()
