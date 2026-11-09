#pragma once
#include <stdint.h>
#include <stddef.h>
typedef int esp_err_t;
#define ESP_OK 0
typedef int esp_partition_type_t;
typedef int esp_partition_subtype_t;
typedef uint32_t spi_flash_mmap_handle_t;
#define ESP_PARTITION_TYPE_DATA 1
#define ESP_PARTITION_MMAP_DATA 0
struct esp_partition_t { uint32_t size; };
inline const esp_partition_t* esp_partition_find_first(esp_partition_type_t, esp_partition_subtype_t, const char*) { return nullptr; }
inline esp_err_t esp_partition_mmap(const esp_partition_t*, uint32_t, uint32_t, int, const void**, spi_flash_mmap_handle_t*) { return 1; }
