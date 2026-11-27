import { useState } from "react";

import type { DatePreset, FilterField, FilterRequest, FilterState } from "../api/types";
import { useSession } from "../context/session";

const SELECTION_KEY: Record<
  FilterField,
  "categories" | "regions" | "products" | "statuses"
> = {
  category: "categories",
  region: "regions",
  product: "products",
  status: "statuses",
};

const FIELD_LABEL: Record<FilterField, string> = {
  category: "Categories",
  region: "Regions",
  product: "Products",
  status: "Statuses",
};

function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  function toggle(value: string) {
    onChange(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value],
    );
  }

  return (
    <details className="multiselect">
      <summary>
        <span>{label}</span>
        <span className="multiselect-count">
          {selected.length === 0 ? "All" : selected.length}
        </span>
      </summary>
      <div className="multiselect-panel">
        <div className="multiselect-head">
          <span>{options.length} options</span>
          {selected.length > 0 ? (
            <button type="button" className="link-button" onClick={() => onChange([])}>
              Clear
            </button>
          ) : null}
        </div>
        {options.length === 0 ? (
          <p className="muted">No values in this dataset.</p>
        ) : (
          options.map((option) => (
            <label key={option} className="check-row">
              <input
                type="checkbox"
                checked={selected.includes(option)}
                onChange={() => toggle(option)}
              />
              <span>{option}</span>
            </label>
          ))
        )}
      </div>
    </details>
  );
}

export function FilterBar() {
  const {
    meta,
    filters,
    filterState,
    filterSummary,
    applyFilters,
    resetFilters,
    busy,
  } = useSession();
  const [draft, setDraft] = useState<FilterState | null>(filterState);

  if (!meta || !filters || !draft) return null;

  function setSelection(field: FilterField, values: string[]) {
    setDraft((current) =>
      current ? { ...current, [SELECTION_KEY[field]]: values } : current,
    );
  }

  function setPreset(preset: DatePreset) {
    setDraft((current) => {
      if (!current) return current;
      const range = filters?.presets[preset];
      return {
        ...current,
        preset,
        ...(range ? { start_date: range[0], end_date: range[1] } : {}),
      };
    });
  }

  async function handleApply() {
    if (!draft) return;
    const request: FilterRequest = {
      categories: draft.categories,
      regions: draft.regions,
      products: draft.products,
      statuses: draft.statuses,
    };
    if (draft.preset === "custom") {
      request.start_date = draft.start_date;
      request.end_date = draft.end_date;
    } else {
      request.preset = draft.preset;
    }
    await applyFilters(request).catch(() => undefined);
  }

  async function handleReset() {
    await resetFilters().catch(() => undefined);
  }

  return (
    <section className="filter-bar" aria-label="Global filters">
      <div className="filter-bar-head">
        <div>
          <p className="eyebrow">Filtering</p>
          <p className="filter-summary">{filterSummary || "All dates"}</p>
        </div>
        <div className="filter-actions">
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void handleReset()}
            disabled={busy}
          >
            Reset
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={() => void handleApply()}
            disabled={busy}
          >
            {busy ? "Applying…" : "Apply filters"}
          </button>
        </div>
      </div>

      <div className="filter-grid">
        <label className="field">
          <span>Date range</span>
          <select
            value={draft.preset}
            onChange={(event) => setPreset(event.target.value as DatePreset)}
          >
            {meta.filters.presets.map((preset) => (
              <option key={preset.key} value={preset.key}>
                {preset.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>From</span>
          <input
            type="date"
            value={draft.start_date}
            min={filters.bounds[0]}
            max={filters.bounds[1]}
            onChange={(event) =>
              setDraft((current) =>
                current
                  ? { ...current, preset: "custom", start_date: event.target.value }
                  : current,
              )
            }
          />
        </label>

        <label className="field">
          <span>To</span>
          <input
            type="date"
            value={draft.end_date}
            min={filters.bounds[0]}
            max={filters.bounds[1]}
            onChange={(event) =>
              setDraft((current) =>
                current
                  ? { ...current, preset: "custom", end_date: event.target.value }
                  : current,
              )
            }
          />
        </label>

        {meta.filters.fields.map((field) => (
          <MultiSelect
            key={field}
            label={FIELD_LABEL[field]}
            options={filters.options[field] ?? []}
            selected={draft[SELECTION_KEY[field]]}
            onChange={(values) => setSelection(field, values)}
          />
        ))}
      </div>
    </section>
  );
}
