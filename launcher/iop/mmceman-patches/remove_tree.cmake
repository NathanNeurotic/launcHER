# Removes TREE recursively; succeeds when it is absent (cmake -E rm needs CMake 3.17)
file(REMOVE_RECURSE "${TREE}")
