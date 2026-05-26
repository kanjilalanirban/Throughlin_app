interface Props {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}

export default function PageHeader({ title, subtitle, right }: Props) {
  return (
    <header className="mb-6 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {right && <div>{right}</div>}
    </header>
  );
}
