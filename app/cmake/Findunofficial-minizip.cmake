find_path(MINIZIP_INCLUDE_DIR minizip/zip.h)
find_library(MINIZIP_LIBRARY NAMES minizip)

if(MINIZIP_INCLUDE_DIR AND MINIZIP_LIBRARY)
    set(unofficial-minizip_FOUND TRUE)
    if(NOT TARGET unofficial::minizip::minizip)
        add_library(unofficial::minizip::minizip UNKNOWN IMPORTED)
        set_target_properties(unofficial::minizip::minizip PROPERTIES
            IMPORTED_LOCATION "${MINIZIP_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${MINIZIP_INCLUDE_DIR}")
    endif()
else()
    set(unofficial-minizip_FOUND FALSE)
endif()
