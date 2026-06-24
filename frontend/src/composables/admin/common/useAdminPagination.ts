export function useAdminPagination(pageSize = 10) {
  function totalPages(total: number) {
    return Math.max(1, Math.ceil(total / pageSize));
  }

  function pageSlice<T>(items: T[], page: number) {
    const currentPage = Math.min(Math.max(1, page), totalPages(items.length));
    const start = (currentPage - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }

  return {
    pageSize,
    pageSlice,
    totalPages
  };
}
