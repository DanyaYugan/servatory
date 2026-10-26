export function portsText(item) {
  if (!item.ports || !item.ports.length) return "портов нет";
  return item.ports
    .map((port) =>
      port.public
        ? `${port.public} → ${port.private}/${port.type}`
        : `${port.private}/${port.type}`,
    )
    .join("  ·  ");
}

export function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${bytes} Б`;
}
