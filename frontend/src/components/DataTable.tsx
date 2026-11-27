import { useMemo, useState } from "react";
import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
}

type SortState = { key: string; direction: "asc" | "desc" } | null;

function compare(left: number | string, right: number | string): number {
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right));
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  initialSort,
  emptyMessage = "No rows to show.",
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  initialSort?: { key: string; direction: "asc" | "desc" };
  emptyMessage?: string;
}) {
  const [sort, setSort] = useState<SortState>(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((candidate) => candidate.key === sort.key);
    if (!column?.sortValue) return rows;
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort(
      (left, right) =>
        compare(column.sortValue!(left), column.sortValue!(right)) * factor,
    );
  }, [columns, rows, sort]);

  function toggleSort(key: string) {
    setSort((current) => {
      if (!current || current.key !== key) return { key, direction: "desc" };
      return {
        key,
        direction: current.direction === "desc" ? "asc" : "desc",
      };
    });
  }

  if (rows.length === 0) {
    return <p className="table-empty">{emptyMessage}</p>;
  }

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => {
              const sortable = Boolean(column.sortValue);
              const active = sort?.key === column.key;
              return (
                <th
                  key={column.key}
                  className={column.align === "right" ? "num" : undefined}
                  aria-sort={
                    active ? (sort?.direction === "asc" ? "ascending" : "descending") : undefined
                  }
                >
                  {sortable ? (
                    <button
                      type="button"
                      className={active ? "sort-button sort-button-active" : "sort-button"}
                      onClick={() => toggleSort(column.key)}
                    >
                      {column.header}
                      <span aria-hidden="true">
                        {active ? (sort?.direction === "asc" ? " ↑" : " ↓") : " ↕"}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((column) => (
                <td key={column.key} className={column.align === "right" ? "num" : undefined}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
