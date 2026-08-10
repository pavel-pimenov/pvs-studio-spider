find_path(MAXMINDDB_INCLUDE_DIR maxminddb.h)
find_library(MAXMINDDB_LIBRARY NAMES maxminddb)

if(MAXMINDDB_INCLUDE_DIR AND MAXMINDDB_LIBRARY)
    set(maxminddb_FOUND TRUE)
    if(NOT TARGET maxminddb::maxminddb)
        add_library(maxminddb::maxminddb UNKNOWN IMPORTED)
        set_target_properties(maxminddb::maxminddb PROPERTIES
            IMPORTED_LOCATION "${MAXMINDDB_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${MAXMINDDB_INCLUDE_DIR}")
    endif()
else()
    set(maxminddb_FOUND FALSE)
endif()
