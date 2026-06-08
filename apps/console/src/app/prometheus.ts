// Minimal parser for the Prometheus text exposition format — enough to read the
// AgentForge counters/histograms the Ops dashboard cares about. Not a general
// implementation: it ignores HELP/TYPE lines and exemplars.

export interface Sample {
  name: string;
  labels: Record<string, string>;
  value: number;
}

/** Parse exposition text into a flat list of samples. */
export function parsePrometheus(text: string): Sample[] {
  const samples: Sample[] = [];
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;

    const brace = line.indexOf('{');
    let name: string;
    let labels: Record<string, string> = {};
    let rest: string;

    if (brace >= 0) {
      const close = line.indexOf('}', brace);
      name = line.slice(0, brace);
      labels = parseLabels(line.slice(brace + 1, close));
      rest = line.slice(close + 1).trim();
    } else {
      const sp = line.indexOf(' ');
      name = line.slice(0, sp);
      rest = line.slice(sp + 1).trim();
    }

    const value = Number(rest.split(/\s+/)[0]);
    if (!Number.isNaN(value)) samples.push({ name, labels, value });
  }
  return samples;
}

function parseLabels(body: string): Record<string, string> {
  const labels: Record<string, string> = {};
  // key="value" pairs, comma-separated; values may contain escaped quotes.
  const re = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(body))) {
    labels[m[1]] = m[2].replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  }
  return labels;
}

/** Sum of all samples for a metric name (optionally filtered by labels). */
export function sum(samples: Sample[], name: string, match: Record<string, string> = {}): number {
  return samples
    .filter((s) => s.name === name && Object.entries(match).every(([k, v]) => s.labels[k] === v))
    .reduce((acc, s) => acc + s.value, 0);
}

/** Value of a single sample with the exact label set, or 0 if absent. */
export function value(samples: Sample[], name: string, labels: Record<string, string>): number {
  const hit = samples.find(
    (s) =>
      s.name === name &&
      Object.entries(labels).every(([k, v]) => s.labels[k] === v) &&
      Object.keys(s.labels).length === Object.keys(labels).length,
  );
  return hit ? hit.value : 0;
}

/** All distinct values of one label across samples of a metric. */
export function labelValues(samples: Sample[], name: string, label: string): string[] {
  const seen = new Set<string>();
  for (const s of samples) {
    if (s.name === name && s.labels[label] !== undefined) seen.add(s.labels[label]);
  }
  return [...seen].sort();
}
