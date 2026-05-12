import { useEffect, useRef, useState } from "react";

interface SelectOption {
  label: string;
  value: string;
}

interface CustomSelectProps {
  onChange(value: string): void;
  options: SelectOption[];
  value: string;
}

export function CustomSelect({ onChange, options, value }: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedLabel = options.find((o) => o.value === value)?.label ?? value;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="agt-custom-select" ref={containerRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className="agt-custom-select__trigger"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span>{selectedLabel}</span>
        <svg aria-hidden="true" fill="none" height="8" viewBox="0 0 12 8" width="12" xmlns="http://www.w3.org/2000/svg">
          <path d="M1 1l5 5 5-5" stroke="#888" strokeLinecap="round" strokeWidth="1.5" />
        </svg>
      </button>
      {open && (
        <div className="agt-custom-select__list">
          {options.map((opt) => (
            <button
              className={`agt-custom-select__option${opt.value === value ? " agt-custom-select__option--active" : ""}`}
              key={opt.value}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              type="button"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
