#pragma once

// Single-process compatibility layer for the pinned upstream baseline.
// It preserves the upstream source snapshot while replacing only MPI transport.

#include <cstdio>
#include <cstring>

using MPI_Comm = int;
using MPI_Datatype = int;
using MPI_Op = int;
using MPI_Info = int;
using MPI_Offset = long long;
using MPI_File = std::FILE *;

inline constexpr MPI_Comm MPI_COMM_WORLD = 0;
inline constexpr MPI_Datatype MPI_DOUBLE = 1;
inline constexpr MPI_Datatype MPI_UINT64_T = 2;
inline constexpr MPI_Op MPI_SUM = 1;
inline constexpr MPI_Info MPI_INFO_NULL = 0;
inline constexpr int MPI_MODE_CREATE = 1;
inline constexpr int MPI_MODE_WRONLY = 2;
#define MPI_STATUS_IGNORE nullptr

inline int MPI_Init(int *, char ***) { return 0; }
inline int MPI_Finalize() { return 0; }
inline int MPI_Comm_rank(MPI_Comm, int *rank) {
    *rank = 0;
    return 0;
}
inline int MPI_Comm_size(MPI_Comm, int *size) {
    *size = 1;
    return 0;
}
inline int MPI_Bcast(void *, int, MPI_Datatype, int, MPI_Comm) { return 0; }
inline int MPI_Reduce(
    const void *send,
    void *receive,
    int count,
    MPI_Datatype datatype,
    MPI_Op,
    int,
    MPI_Comm
) {
    const std::size_t width = datatype == MPI_DOUBLE ? sizeof(double) : sizeof(unsigned long long);
    std::memcpy(receive, send, static_cast<std::size_t>(count) * width);
    return 0;
}
inline int MPI_File_open(
    MPI_Comm,
    const char *filename,
    int,
    MPI_Info,
    MPI_File *file
) {
    *file = std::fopen(filename, "r+b");
    if (*file == nullptr) {
        *file = std::fopen(filename, "w+b");
    }
    return *file == nullptr ? 1 : 0;
}
inline int MPI_File_write_at(
    MPI_File file,
    MPI_Offset offset,
    const void *data,
    int count,
    MPI_Datatype datatype,
    void *
) {
    if (std::fseek(file, static_cast<long>(offset), SEEK_SET) != 0) {
        return 1;
    }
    const std::size_t width = datatype == MPI_DOUBLE ? sizeof(double) : sizeof(unsigned long long);
    return std::fwrite(data, width, static_cast<std::size_t>(count), file) == static_cast<std::size_t>(count) ? 0 : 1;
}
inline int MPI_File_close(MPI_File *file) {
    const int status = std::fclose(*file);
    *file = nullptr;
    return status;
}
