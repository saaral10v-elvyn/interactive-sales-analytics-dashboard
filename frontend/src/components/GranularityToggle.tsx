import type { Granularity } from "../api/types";

export function GranularityToggle({
  value,
  onChange,
}: {
  value: Granularity;
  onChange: (value: Granularity) => void;
}) {
  const options: { value: Granularity; label: string }[] = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "monthly", label: "Monthly" },
  ];

  return (
    <div className="segmented" role="group" aria-label="Trend granularity">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? "segmented-active" : undefined}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
