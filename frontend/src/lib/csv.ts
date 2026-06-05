// src/lib/csv.ts
/**
 * Convert an array of objects to CSV and trigger a download.
 * Keys of the first object are used as header columns.
 */
export function downloadCSV(filename: string, data: Record<string, any>[]) {
  if (!data.length) {
    console.warn('downloadCSV: no data to export');
    return;
  }
  const header = Object.keys(data[0]);
  const rows = data.map((row) =>
    header.map((field) => {
      const val = row[field];
      if (val === null || val === undefined) return '';
      // Escape commas, quotes, newlines
      const str = String(val).replace(/"/g, '""');
      return /[",\n]/.test(str) ? `"${str}"` : str;
    }).join(',')
  );
  const csvContent = [header.join(','), ...rows].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.setAttribute('download', filename);
  a.click();
  URL.revokeObjectURL(url);
}
